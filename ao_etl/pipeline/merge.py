"""Phase MERGE - Fusion et mise à jour des enregistrements.

Responsabilités :
- Créer les nouvelles lignes CSV pour les nouveaux marchés
- Mettre à jour les lignes existantes si nécessaire
- Préserver les colonnes _manual
- Calculer les colonnes finales selon la règle : final = manual si non vide, sinon auto
- Produire le dataset final prêt pour l'export
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime

from .reconcile import ReconciliationResult, ReconciliationStatus
from ao_etl.models.market import MarketData


@dataclass
class MergeResult:
    """Résultat de la phase merge."""
    final_rows: List[Dict] = field(default_factory=list)
    fieldnames: List[str] = field(default_factory=list)
    new_count: int = 0
    updated_count: int = 0
    preserved_count: int = 0
    
    def get_new_rows(self) -> List[Dict]:
        """Retourne les nouvelles lignes (match_status = 'new')."""
        return [r for r in self.final_rows if r.get('match_status') == 'new']


def marketdata_to_csv_row(data: MarketData, 
                          discovered_file,
                          fieldnames: List[str]) -> Dict:
    """Convertit un objet MarketData en ligne CSV.
    
    Args:
        data: Données extraites
        discovered_file: Fichier découvert associé
        fieldnames: Colonnes CSV attendues
        
    Returns:
        Dictionnaire représentant une ligne CSV
    """
    # Déterminer la plateforme
    from ao_etl.models.market import SourceType
    if data.source_type == SourceType.MARCHES_ONLINE:
        plateforme = "Marchés Online"
    elif data.source_type == SourceType.FRANCE_MARCHES:
        plateforme = "France Marchés"
    elif data.source_type == SourceType.BOAMP_XML:
        plateforme = "BOAMP"
    elif data.source_type == SourceType.PLACE_NUMERIC:
        plateforme = "PLACE"
    else:
        plateforme = "Standard"
    
    # Construire la ligne de base
    row = {
        'Référence': data.reference or discovered_file.reference_derived or '-',
        'Intitulé synthétique': data.title or '-',
        'Type d\'AO': '-',
        'Type': '-',
        'Fonction publique': '-',
        'Acheteur_auto': data.buyer or '-',
        'Acheteur_manual': '',
        'Acheteur_clean': data.buyer or '-',
        'Localisation_auto': data.location or '-',
        'Localisation_manual': '',
        'Localisation': data.location or '-',
        'Localisation_clean': data.location or '-',
        'Date_limite_auto': str(data.date_limite) if data.date_limite else '-',
        'Date_limite_manual': '',
        'Date limite de remise des offres': str(data.date_limite) if data.date_limite else '-',
        'Durée initiale du marché': '-',
        'Reconduction(s)': '-',
        'Estimation_auto': data.estimation_eur or '-',
        'Estimation_manual': '',
        'Estimation du marché': data.estimation_eur or '-',
        'URL source HTTPS': data.url_source or '-',
        'Plateforme': plateforme,
        'match_status': 'new',
        'match_source': discovered_file.filename,
        'review_needed': 'oui' if not data.buyer else '',
        'extraction_notes': '; '.join(data.extraction_notes) if data.extraction_notes else 'Ajouté via pipeline unifié',
        'source_type': data.source_type.value if data.source_type else 'UNKNOWN',
    }
    
    # Compléter les colonnes manquantes
    for field in fieldnames:
        if field not in row:
            row[field] = '-'
    
    return row


def apply_manual_overrides(row: Dict) -> Dict:
    """Applique la règle : final = manual si non vide, sinon auto.
    
    Triplets à traiter :
    - Acheteur_auto / Acheteur_manual / Acheteur
    - Localisation_auto / Localisation_manual / Localisation
    - Date_limite_auto / Date_limite_manual / Date limite
    - Estimation_auto / Estimation_manual / Estimation du marché
    """
    triplets = [
        ('Acheteur_auto', 'Acheteur_manual', 'Acheteur'),
        ('Localisation_auto', 'Localisation_manual', 'Localisation'),
        ('Date_limite_auto', 'Date_limite_manual', 'Date limite de remise des offres'),
        ('Estimation_auto', 'Estimation_manual', 'Estimation du marché'),
    ]
    
    for auto_field, manual_field, final_field in triplets:
        manual_value = row.get(manual_field, '')
        auto_value = row.get(auto_field, '')
        
        # Convertir en string si nécessaire (pour les nombres comme estimation_eur)
        if not isinstance(manual_value, str):
            manual_value = str(manual_value) if manual_value else ''
        if not isinstance(auto_value, str):
            auto_value = str(auto_value) if auto_value else ''
        
        manual_value = manual_value.strip()
        auto_value = auto_value.strip()
        
        if manual_value and manual_value != '-':
            row[final_field] = manual_value
        elif auto_value and auto_value != '-':
            row[final_field] = auto_value
        else:
            row[final_field] = '-'
    
    return row


def merge(result: ReconciliationResult,
          extracted_data_map: Dict) -> MergeResult:
    """Fusionne les données extraites avec le CSV existant.
    
    Args:
        result: Résultat de la réconciliation
        extracted_data_map: Dict mapping discovered_file → MarketData
        
    Returns:
        MergeResult avec les lignes finales
    """
    merge_result = MergeResult()
    merge_result.fieldnames = result.csv_fieldnames.copy()
    
    # Ajouter les colonnes requises si manquantes
    required_cols = ['source_type', 'match_status', 'review_needed']
    for col in required_cols:
        if col not in merge_result.fieldnames:
            merge_result.fieldnames.append(col)
    
    # 1. Préserver les lignes CSV existantes (même sans fichier associé)
    csv_rows_preserved = []
    for idx, row in enumerate(result.csv_rows):
        # Cette ligne a-t-elle un fichier associé ?
        has_file = any(
            item.csv_row_index == idx 
            for item in result.items 
            if item.csv_row_index is not None
        )
        
        if not has_file:
            # Ligne CSV sans fichier - la préserver telle quelle
            csv_rows_preserved.append(row)
            merge_result.preserved_count += 1
        else:
            # Ligne avec fichier - sera traitée ci-dessous
            pass
    
    # 2. Traiter les items réconciliés
    for item in result.items:
        if item.status == ReconciliationStatus.MATCHED and item.csv_row:
            # Ligne existante avec fichier - potentiellement mise à jour
            row = item.csv_row.copy()
            
            # Si on a extrait de nouvelles données et que les champs auto sont vides
            extracted = extracted_data_map.get(item.discovered.filename)
            if extracted:
                if not row.get('Acheteur_auto') or row['Acheteur_auto'] == '-':
                    row['Acheteur_auto'] = extracted.buyer or '-'
                if not row.get('Localisation_auto') or row['Localisation_auto'] == '-':
                    row['Localisation_auto'] = extracted.location or '-'
            
            # Recalculer les colonnes finales
            row = apply_manual_overrides(row)
            merge_result.final_rows.append(row)
            merge_result.updated_count += 1
            
        elif item.status == ReconciliationStatus.NEW_MARKET:
            # Nouveau marché - créer une nouvelle ligne
            extracted = extracted_data_map.get(item.discovered.filename)
            if extracted:
                row = marketdata_to_csv_row(extracted, item.discovered, merge_result.fieldnames)
                row = apply_manual_overrides(row)
                merge_result.final_rows.append(row)
                merge_result.new_count += 1
            else:
                # Pas de données extraites - créer une ligne minimale
                row = {
                    'Référence': item.discovered.reference_derived,
                    'Intitulé synthétique': '-',
                    'match_status': 'new',
                    'match_source': item.discovered.filename,
                    'review_needed': 'oui',
                    'extraction_notes': 'Données non extraites',
                    'source_type': item.discovered.category.value.upper(),
                }
                for field in merge_result.fieldnames:
                    if field not in row:
                        row[field] = '-'
                row = apply_manual_overrides(row)
                merge_result.final_rows.append(row)
                merge_result.new_count += 1
                
        elif item.status == ReconciliationStatus.ALIAS:
            # Alias - ignorer pour l'instant (pourrait être traité différemment)
            pass
            
        elif item.status == ReconciliationStatus.COLLISION:
            # Collision - logguer et ignorer
            pass
    
    # 3. Ajouter les lignes CSV préservées (sans fichier)
    merge_result.final_rows.extend(csv_rows_preserved)
    
    return merge_result


def print_merge_summary(result: MergeResult) -> None:
    """Affiche un résumé du merge."""
    print(f"\n[MERGE] Fusion terminée")
    print("-" * 60)
    print(f"  Lignes préservées:     {result.preserved_count:>3}")
    print(f"  Lignes mises à jour:   {result.updated_count:>3}")
    print(f"  Nouvelles lignes:       {result.new_count:>3}")
    print(f"  Total lignes finales:  {len(result.final_rows):>3}")
    
    new_rows = result.get_new_rows()
    if new_rows:
        print(f"\n  Détail nouvelles lignes:")
        for row in new_rows[:5]:
            ref = row.get('Référence', '-')[:25]
            buyer = row.get('Acheteur_auto', '-')[:20]
            print(f"    - {ref:<25} acheteur: {buyer}")
        if len(new_rows) > 5:
            print(f"    ... et {len(new_rows) - 5} autres")
