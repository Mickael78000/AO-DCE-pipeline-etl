#!/usr/bin/env python3
"""
Script pour exécuter le pipeline avec enrichissement depuis fichiers .txt.
Usage:
    python run_pipeline_txt_enrich.py [--llm] [--limit N]
    
Note: Ce script nécessite le virtual environment activé.
    Utilisez: source venv/bin/activate
    Ou exécutez via: ./run_full_pipeline.sh
"""

import argparse
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

# Vérification du virtual environment (optionnel mais recommandé)
try:
    from ao_etl.utils.venv_check import ensure_venv_activated
    ensure_venv_activated()
except ImportError:
    pass

from ao_etl.pipeline import (
    run_pipeline, EnrichTxtConfig, EnrichLLMConfig, NormalizeConfig, EnrichUrlConfig
)


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline ETL avec enrichissement depuis fichiers .txt"
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Activer la phase de complément LLM (nécessite une clé API)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limiter le nombre de lignes pour la phase LLM (pour les tests)"
    )
    parser.add_argument(
        "--html-dir",
        type=Path,
        default=Path("data/raw/html"),
        help="Répertoire contenant les fichiers HTML et .txt"
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=Path("data/output/final-v4-complete.csv"),
        help="Fichier CSV d'entrée"
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("data/output/final-v4-complete.csv"),
        help="Fichier CSV de sortie principal"
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("PIPELINE ETL - Enrichissement depuis fichiers .txt")
    print("=" * 70)
    print()
    
    # Configuration des phases
    enrich_txt_config = EnrichTxtConfig(enabled=True)
    normalize_config = NormalizeConfig(enabled=True)
    url_config = EnrichUrlConfig(enabled=True)
    
    enrich_llm_config = None
    if args.llm:
        enrich_llm_config = EnrichLLMConfig(
            enabled=True,
            backend='ollama',
            max_rows=args.limit
        )
        print("Phase LLM (Ollama): ACTIVÉE")
        if args.limit:
            print(f"  Limite: {args.limit} lignes")
    else:
        print("Phase LLM: désactivée (utiliser --llm pour activer)")
    
    print("Phase NORMALIZE: ACTIVÉE")
    print("Phase URL: ACTIVÉE")
    
    print()
    print(f"HTML/Texte dir: {args.html_dir}")
    print(f"Input CSV: {args.input_csv}")
    print(f"Output CSV: {args.output_csv}")
    print()
    
    # Exécuter le pipeline
    result = run_pipeline(
        html_dir=args.html_dir,
        input_csv=args.input_csv,
        output_csv=args.output_csv,
        verbose=True,
        enrich_txt_config=enrich_txt_config,
        enrich_llm_config=enrich_llm_config,
        normalize_config=normalize_config,
        url_config=url_config,
    )
    
    # Afficher le résumé
    print()
    print("=" * 70)
    print("RÉSUMÉ FINAL")
    print("=" * 70)
    print(f"Pipeline succès: {result.success}")
    print(f"Total lignes: {result.total_rows}")
    print(f"Validation: {'OK' if result.validation_passed else 'ÉCHEC'}")
    
    if result.enrich_txt_csv:
        print()
        print(f"Fichier enrichi (.txt): {result.enrich_txt_csv}")
        if result.enrich_txt_stats:
            stats = result.enrich_txt_stats
            print(f"  - Lignes enrichies: {stats.get('enriched_rows', 0)}/{stats.get('total_rows', 0)}")
            print(f"  - Fichiers .txt utilisés: {stats.get('txt_files_used', 0)}")
            print(f"  - Lots trouvés: {stats.get('lots_found', 0)}")
            print(f"  - CPV identifiés: {stats.get('cpv_found', 0)}")
            print(f"  - Montants complétés: {stats.get('montants_enriched', 0)}")
    
    if result.enrich_llm_csv:
        print()
        print(f"Fichier enrichi (LLM): {result.enrich_llm_csv}")
        if result.enrich_llm_stats:
            stats = result.enrich_llm_stats
            print(f"  - Lignes complétées: {stats.get('llm_enriched_rows', 0)}")
            print(f"  - Type d'AO complétés: {stats.get('type_ao_filled', 0)}")
            print(f"  - Type complétés: {stats.get('type_filled', 0)}")
            print(f"  - Fonction publique complétés: {stats.get('fonction_publique_filled', 0)}")
    
    if result.normalize_csv:
        print()
        print(f"Fichier normalisé: {result.normalize_csv}")
        if result.normalize_stats:
            stats = result.normalize_stats
            print(f"  - Lignes normalisées: {stats.get('normalized_rows', 0)}")
            print(f"  - Type d'AO complétés: {stats.get('type_ao_filled', 0)}")
            print(f"  - Fonction publique complétés: {stats.get('fonction_publique_filled', 0)}")
    
    if result.url_csv:
        print()
        print(f"Fichier avec URLs: {result.url_csv}")
        if result.url_stats:
            stats = result.url_stats
            print(f"  - URLs reconstruites: {stats.get('urls_reconstructed', 0)}")
            print(f"  - URLs déjà présentes: {stats.get('urls_already_present', 0)}")
    
    print("=" * 70)
    
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
