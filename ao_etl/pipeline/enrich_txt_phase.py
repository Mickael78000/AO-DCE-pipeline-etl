"""
Phase d'enrichissement exclusivement depuis les fichiers .txt.
Remplace la logique HTML par une lecture directe des descriptifs texte.
"""

import logging
import csv
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from ao_etl.enrich_from_txt import enrich_from_txt_file, find_txt_file
from ao_etl.enrich_descriptif import enrich_csv_row
from ao_etl.normalize_fields import normalize_fonction_publique, validate_and_fix_row

log = logging.getLogger(__name__)


@dataclass
class EnrichTxtResult:
    """Résultat de la phase d'enrichissement depuis .txt."""
    total_rows: int
    enriched_rows: int
    errors: List[str] = field(default_factory=list)
    new_columns: List[str] = field(default_factory=list)
    lots_found: int = 0
    cpv_found: int = 0
    montants_enriched: int = 0
    txt_files_used: int = 0


@dataclass
class EnrichTxtConfig:
    """Configuration pour la phase d'enrichissement .txt."""
    enabled: bool = True
    output_csv: Optional[Path] = None


def run_enrich_txt_phase(
    input_csv: Path,
    html_dir: Path,
    output_csv: Path,
) -> Dict[str, Any]:
    """
    Exécute la phase d'enrichissement depuis les fichiers .txt.
    
    Args:
        input_csv: Fichier CSV d'entrée (final-v4-complete.csv)
        html_dir: Répertoire contenant les fichiers .txt
        output_csv: Fichier CSV de sortie (final-v4-complete.csv mis à jour)
        
    Returns:
        Statistiques de l'enrichissement
    """
    log.info(f"Enrichissement depuis les fichiers .txt dans {html_dir}")
    
    # Lire le CSV d'entrée
    rows = []
    fieldnames = []
    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    
    log.info(f"{len(rows)} lignes à enrichir depuis .txt")
    
    # Nouvelles colonnes à ajouter
    new_columns = [
        'cpv_principal',
        'cpv_supplementaires',
        'nombre_lots',
        'lots_detail',
        'criteres_attribution',
        'duree_reelle',
        'options_reconduction',
        'departements_publication',
        'annonce_numero',
        'conflits_detectes',
        "Type d'AO",
        'Type',
        'Fonction publique',
    ]
    
    # Ajouter les nouvelles colonnes
    for col in new_columns:
        if col not in fieldnames:
            fieldnames.append(col)
    
    result = EnrichTxtResult(
        total_rows=len(rows),
        enriched_rows=0,
        new_columns=new_columns,
    )
    
    # Indexer tous les fichiers .txt disponibles
    log.info("Indexation des fichiers .txt...")
    txt_files = list(html_dir.glob("*_descriptif.txt"))
    log.info(f"{len(txt_files)} fichiers .txt trouvés")
    
    # Enrichir chaque ligne
    for i, row in enumerate(rows):
        try:
            reference = row.get('Référence', '')
            if not reference:
                continue
            
            # Trouver le fichier .txt correspondant
            txt_file = find_txt_file(reference, html_dir)
            
            if txt_file:
                result.txt_files_used += 1
                
                # Enrichir depuis le fichier .txt
                enrichi = enrich_from_txt_file(txt_file)
                if enrichi:
                    row = enrich_csv_row(row, enrichi)
                    result.enriched_rows += 1
                    
                    if enrichi.lots:
                        result.lots_found += len(enrichi.lots)
                    if enrichi.cpv_principal:
                        result.cpv_found += 1
                    if enrichi.montant_estime:
                        result.montants_enriched += 1
                    
                    # Remplir directement les colonnes finales si absentes ou '-'
                    # Type d'AO (procedure_type)
                    type_ao_current = row.get("Type d'AO", '')
                    if (not type_ao_current or type_ao_current == '-') and enrichi.procedure_type:
                        row["Type d'AO"] = enrichi.procedure_type
                    
                    # Fonction publique (activite acheteur) — normalisée vers taxonomie stricte
                    fonc_current = row.get('Fonction publique', '')
                    if (not fonc_current or fonc_current == '-') and enrichi.acheteur_activite:
                        row['Fonction publique'] = normalize_fonction_publique(enrichi.acheteur_activite)
            else:
                log.warning(f"Fichier .txt non trouvé pour {reference}")
                
        except Exception as e:
            error_msg = f"Erreur ligne {i} ({reference}): {e}"
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
    
    # Validation finale : toutes les colonnes contractuelles dans leur taxonomie
    rows = [validate_and_fix_row(row) for row in rows]

    # Écrire le CSV enrichi
    with open(output_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=final_fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    log.info(f"CSV enrichi écrit: {output_csv}")
    log.info(f"Fichiers .txt utilisés: {result.txt_files_used}/{result.total_rows}")
    log.info(f"Lignes enrichies: {result.enriched_rows}/{result.total_rows}")
    log.info(f"Lots trouvés: {result.lots_found}, CPV trouvés: {result.cpv_found}")
    
    return {
        'total_rows': result.total_rows,
        'enriched_rows': result.enriched_rows,
        'txt_files_used': result.txt_files_used,
        'lots_found': result.lots_found,
        'cpv_found': result.cpv_found,
        'montants_enriched': result.montants_enriched,
        'new_columns': result.new_columns,
        'errors': result.errors,
        'output_csv': str(output_csv),
    }


def print_enrich_txt_summary(stats: Dict[str, Any]) -> None:
    """Affiche le résumé de la phase d'enrichissement .txt."""
    print()
    print("=" * 70)
    print("ENRICHISSEMENT DEPUIS FICHIERS .TXT - Résumé")
    print("=" * 70)
    print(f"Lignes traitées:      {stats.get('total_rows', 0)}")
    print(f"Fichiers .txt utilisés: {stats.get('txt_files_used', 0)}")
    print(f"Lignes enrichies:     {stats.get('enriched_rows', 0)}")
    print(f"Lots trouvés:         {stats.get('lots_found', 0)}")
    print(f"CPV identifiés:       {stats.get('cpv_found', 0)}")
    print(f"Montants complétés:   {stats.get('montants_enriched', 0)}")
    print(f"Nouvelles colonnes:   {len(stats.get('new_columns', []))}")
    if stats.get('errors'):
        print(f"Erreurs:              {len(stats['errors'])}")
    print(f"Fichier sortie:       {stats.get('output_csv', 'N/A')}")
    print("=" * 70)
