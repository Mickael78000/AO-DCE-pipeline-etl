"""
Phase de normalisation finale - Mapping canonique des champs.
Applique une table de mapping pour combler les manques restants avant export.

Mapping canonique:
- procedure_type -> "Type d'AO"
- nature_marche -> "Type"
- acheteur_activite -> "Fonction publique"
"""

import logging
import csv
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from ao_etl.normalize_fields import validate_and_fix_row

log = logging.getLogger(__name__)


@dataclass
class NormalizeResult:
    """Résultat de la phase de normalisation."""
    total_rows: int
    normalized_rows: int = 0
    type_ao_filled: int = 0
    type_filled: int = 0
    fonction_publique_filled: int = 0
    errors: List[str] = field(default_factory=list)


@dataclass
class NormalizeConfig:
    """Configuration pour la phase de normalisation."""
    enabled: bool = True
    output_csv: Optional[Path] = None


def normalize_row(row: Dict[str, Any]) -> bool:
    """
    Normalise une ligne selon la table de mapping canonique.
    
    Returns:
        True si des modifications ont été apportées
    """
    updated = False
    
    # Mapping canonique: procedure_type -> "Type d'AO"
    # Seule source autorisée : procedure_type (parsing déterministe)
    # Le champ legacy type_ao (LLM) est ignoré.
    type_ao = row.get("Type d'AO", '')
    if not type_ao or type_ao == '-':
        proc_type = row.get('procedure_type', '')
        if proc_type and proc_type != '-':
            row["Type d'AO"] = proc_type
            updated = True
    
    # Mapping canonique: nature_marche -> "Type"
    type_val = row.get('Type', '')
    if not type_val or type_val == '-':
        # Essayer nature_marche
        nature = row.get('nature_marche', '')
        if nature and nature != '-':
            row['Type'] = nature
            updated = True
    
    # Mapping canonique: acheteur_activite -> "Fonction publique"
    fonc = row.get('Fonction publique', '')
    if not fonc or fonc == '-':
        # Essayer acheteur_activite
        activite = row.get('acheteur_activite', '')
        if activite and activite != '-':
            row['Fonction publique'] = activite
            updated = True
    
    return updated


def run_normalize_phase(
    input_csv: Path,
    output_csv: Path,
) -> Dict[str, Any]:
    """
    Exécute la phase de normalisation finale.
    
    Args:
        input_csv: Fichier CSV d'entrée
        output_csv: Fichier CSV de sortie normalisé
        
    Returns:
        Statistiques de la normalisation
    """
    log.info(f"Phase de normalisation finale: {input_csv} -> {output_csv}")
    
    # Lire le CSV d'entrée
    rows = []
    fieldnames = []
    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    
    log.info(f"{len(rows)} lignes à normaliser")
    
    result = NormalizeResult(total_rows=len(rows))
    
    # Normaliser chaque ligne
    for i, row in enumerate(rows):
        try:
            # Vérifier les champs actuels
            type_ao_before = row.get("Type d'AO", '')
            type_before = row.get('Type', '')
            fonc_before = row.get('Fonction publique', '')
            
            # Appliquer la normalisation déterministe
            if normalize_row(row):
                result.normalized_rows += 1

            # Validation finale — impose la taxonomie stricte sur toutes les colonnes
            validate_and_fix_row(row)

            # Compter les champs remplis (après validation)
            if (not type_ao_before or type_ao_before == '-') and row.get("Type d'AO") and row.get("Type d'AO") != '-':
                result.type_ao_filled += 1
            if (not type_before or type_before == '-') and row.get('Type') and row.get('Type') != '-':
                result.type_filled += 1
            if (not fonc_before or fonc_before == '-') and row.get('Fonction publique') and row.get('Fonction publique') != '-':
                result.fonction_publique_filled += 1
                    
        except Exception as e:
            error_msg = f"Erreur normalisation ligne {i}: {e}"
            log.error(error_msg)
            result.errors.append(error_msg)
    
    # S'assurer que toutes les lignes ont les mêmes clés
    all_new_keys = set()
    for row in rows:
        all_new_keys.update(row.keys())
    
    final_fieldnames = list(fieldnames)
    for key in all_new_keys:
        if key not in final_fieldnames:
            final_fieldnames.append(key)
    
    # Écrire le CSV normalisé
    with open(output_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=final_fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    log.info(f"CSV normalisé écrit: {output_csv}")
    log.info(f"Lignes normalisées: {result.normalized_rows}/{result.total_rows}")
    log.info(f"Type d'AO complétés: {result.type_ao_filled}")
    log.info(f"Type complétés: {result.type_filled}")
    log.info(f"Fonction publique complétés: {result.fonction_publique_filled}")
    
    return {
        'total_rows': result.total_rows,
        'normalized_rows': result.normalized_rows,
        'type_ao_filled': result.type_ao_filled,
        'type_filled': result.type_filled,
        'fonction_publique_filled': result.fonction_publique_filled,
        'errors': result.errors,
        'output_csv': str(output_csv),
    }


def print_normalize_summary(stats: Dict[str, Any]) -> None:
    """Affiche le résumé de la phase de normalisation."""
    print()
    print("=" * 70)
    print("NORMALISATION FINALE - Résumé")
    print("=" * 70)
    print(f"Lignes traitées:          {stats.get('total_rows', 0)}")
    print(f"Lignes normalisées:       {stats.get('normalized_rows', 0)}")
    print(f"Type d'AO complétés:      {stats.get('type_ao_filled', 0)}")
    print(f"Type complétés:           {stats.get('type_filled', 0)}")
    print(f"Fonction publique:        {stats.get('fonction_publique_filled', 0)}")
    if stats.get('errors'):
        print(f"Erreurs:                  {len(stats['errors'])}")
    print(f"Fichier sortie:           {stats.get('output_csv', 'N/A')}")
    print("=" * 70)
