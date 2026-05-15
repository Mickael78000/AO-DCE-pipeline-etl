#!/usr/bin/env python3
"""Point d'entrée CLI pour le pipeline ETL unifié.

Usage:
    python run_pipeline.py [options]
    
Exemples:
    python run_pipeline.py
    python run_pipeline.py --html-dir html_ao --input AO.csv --output AO-final.csv
"""

import argparse
import sys
from pathlib import Path

# Ajouter le répertoire courant au path pour les imports
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ao_etl.pipeline import run_pipeline, PipelineResult, ConsolidationConfig


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline ETL unifié pour AO-DCE",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Séquence du pipeline:
  1. DISCOVERY    - Découverte des fichiers HTML
  2. RECONCILE    - Réconciliation avec CSV existant
  3. EXTRACT      - Extraction des données via ao_etl.sources
  4. MERGE        - Fusion et mise à jour
  5. VALIDATE     - Validation qualité
  6. EXPORT       - Export CSV et rapports
  7. [CONSOLIDATE]- Consolidation LLM (optionnel, --consolidate)
  8. [CLASSIFY]   - Classification acheteurs (optionnel, --classify-buyers)
  9. [ENRICH]     - Enrichissement juridique (optionnel, --enrich-juridique) [REGEX]
  10. [EXCEL]     - Export Excel formaté (optionnel, --excel)

Exemples:
  python run_pipeline.py --consolidate --enrich-juridique --excel
  python run_pipeline.py --enrich-juridique --excel-only
  python run_pipeline.py --full (toutes les phases optionnelles)
        """
    )
    
    # Détection automatique des chemins (nouvelle structure vs legacy)
    default_html = Path('data/raw/html') if Path('data/raw/html').exists() else Path('html_ao')
    default_input = Path('data/input/AO-completed.csv') if Path('data/input/AO-completed.csv').exists() else Path('AO-completed.csv')
    
    parser.add_argument(
        '--html-dir', '-d',
        type=Path,
        default=default_html,
        help="Répertoire contenant les fichiers HTML (auto-détection: data/raw/html ou html_ao)"
    )
    
    parser.add_argument(
        '--input', '-i',
        type=Path,
        default=default_input,
        help="Fichier CSV d'entrée (auto-détection: data/input/AO-completed.csv ou AO-completed.csv)"
    )
    
    # Détection du dossier de sortie par défaut
    default_output_dir = Path('data/output') if Path('data/output').exists() else Path('.')
    default_output = default_output_dir / 'AO-pipeline-v2.csv'
    
    parser.add_argument(
        '--output', '-o',
        type=Path,
        default=default_output,
        help="Fichier CSV de sortie (défaut: data/output/AO-pipeline-v2.csv ou AO-pipeline-output.csv)"
    )
    
    parser.add_argument(
        '--report', '-r',
        type=Path,
        default=None,
        help="Fichier de rapport JSON (défaut: <output>.json)"
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help="Mode silencieux (moins de logs)"
    )
    
    parser.add_argument(
        '--extractor-version',
        choices=['legacy', 'v2'],
        default=None,
        help="Version de l'extracteur HTML (legacy=défaut prudent, v2=nouvelle architecture). Prime sur AO_EXTRACTOR_VERSION."
    )

    parser.add_argument(
        '--consolidate',
        action='store_true',
        help="Active la phase 7 : consolidation LLM des champs métier."
    )
    parser.add_argument(
        '--consolidate-backend',
        default='',
        metavar='BACKEND',
        help="Backend LLM : openai | anthropic | ollama (défaut: AO_LLM_BACKEND env)."
    )
    parser.add_argument(
        '--consolidate-model',
        default='',
        metavar='MODEL',
        help="Modèle LLM (défaut: AO_LLM_MODEL env ou défaut du backend)."
    )
    parser.add_argument(
        '--consolidate-limit',
        type=int,
        default=None,
        metavar='N',
        help="Limite la consolidation aux N premières lignes (debug/test)."
    )
    parser.add_argument(
        '--consolidate-output',
        type=Path,
        default=None,
        help="CSV métier de sortie (défaut: <output_dir>/final-v3-consolidated.csv)."
    )
    parser.add_argument(
        '--consolidate-json-dir',
        type=Path,
        default=None,
        help="Répertoire de sortie des JSONs individuels par marché."
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Phase 7 en simulation : préserve les champs déterministes, n'appelle pas le LLM."
    )

    # Phase 8: Classification acheteurs
    parser.add_argument(
        '--classify-buyers',
        action='store_true',
        help="Active la phase 8 : classification des acheteurs."
    )

    # Phase 9: Enrichissement juridique (REGEX-based)
    parser.add_argument(
        '--enrich-juridique',
        action='store_true',
        help="Active la phase 9 : enrichissement juridique avec regex (MAPA, négociée, JOUE, défense)."
    )
    parser.add_argument(
        '--enrich-output',
        type=Path,
        default=None,
        help="CSV juridique de sortie (défaut: <output_dir>/final-v4-juridique.csv)."
    )

    # Phase 10: Export Excel
    parser.add_argument(
        '--excel',
        action='store_true',
        help="Active la phase 10 : export Excel formaté avec styles et résumé."
    )
    parser.add_argument(
        '--excel-output',
        type=Path,
        default=None,
        help="Fichier Excel de sortie (défaut: <output_dir>/final-v4-juridique.xlsx)."
    )

    # Mode complet (toutes les phases)
    parser.add_argument(
        '--full',
        action='store_true',
        help="Active toutes les phases optionnelles (consolidate, classify, enrich, excel)."
    )

    args = parser.parse_args()
    
    # Vérifications
    if not args.html_dir.exists():
        print(f"✗ Erreur: Répertoire HTML introuvable: {args.html_dir}")
        return 1
    
    if not args.input.exists():
        print(f"⚠ Avertissement: CSV d'entrée introuvable: {args.input}")
        print(f"  Le pipeline créera un nouveau CSV avec uniquement les fichiers HTML.")
    
    # Définir la version d'extracteur via CLI (prime sur env)
    if args.extractor_version:
        os.environ['AO_EXTRACTOR_VERSION'] = args.extractor_version
    
    # Exécution
    print(f"\n{'='*70}")
    print("PIPELINE ETL AO-DCE v2.0")
    print(f"{'='*70}\n")
    
    if not args.quiet:
        env_version = os.environ.get('AO_EXTRACTOR_VERSION', 'legacy')
        print(f"Extracteur: {env_version}")
        print()
    
    # Mode --full active toutes les phases
    if args.full:
        args.consolidate = True
        args.classify_buyers = True
        args.enrich_juridique = True
        args.excel = True

    output_dir = args.output.parent

    # Phase 7: Consolidation
    consolidation_config = None
    if args.consolidate or getattr(args, 'dry_run', False):
        consolidation_config = ConsolidationConfig(
            enabled=True,
            backend=args.consolidate_backend,
            model=args.consolidate_model,
            limit=args.consolidate_limit,
            dry_run=getattr(args, 'dry_run', False),
            output_csv=args.consolidate_output,
            json_dir=args.consolidate_json_dir or (output_dir / 'final-v3-consolidated'),
        )

    # Phase 8: Classification acheteurs
    from ao_etl.classification import BuyerClassificationConfig
    buyer_classification_config = None
    if args.classify_buyers:
        buyer_classification_config = BuyerClassificationConfig(enabled=True)

    # Phase 9: Enrichissement juridique (REGEX)
    from ao_etl.pipeline.enrich_juridique import EnrichJuridiqueConfig
    enrich_juridique_config = None
    if args.enrich_juridique:
        enrich_juridique_config = EnrichJuridiqueConfig(
            enabled=True,
            output_csv=args.enrich_output,
        )

    # Phase 10: Export Excel
    from ao_etl.pipeline.excel_export import ExcelExportConfig
    excel_export_config = None
    if args.excel:
        excel_export_config = ExcelExportConfig(
            enabled=True,
            output_excel=args.excel_output,
        )

    result = run_pipeline(
        html_dir=args.html_dir,
        input_csv=args.input,
        output_csv=args.output,
        report_path=args.report,
        verbose=not args.quiet,
        consolidation_config=consolidation_config,
        buyer_classification_config=buyer_classification_config,
        enrich_juridique_config=enrich_juridique_config,
        excel_export_config=excel_export_config,
    )

    if result.success:
        print(f"\n✓ Pipeline terminé avec succès")
        print(f"  Lignes totales : {result.total_rows}")
        print(f"  Nouveaux marchés: {result.new_rows}")
        print(f"  CSV v2         : {result.output_csv}")
        print(f"  Rapport JSON   : {result.output_report}")
        if result.consolidated_csv:
            print(f"  CSV v3 métier  : {result.consolidated_csv}")
        if result.classification_csv:
            print(f"  CSV classifié  : {result.classification_csv}")
        if result.juridique_csv:
            print(f"  CSV juridique  : {result.juridique_csv}")
        if result.excel_output:
            print(f"  Excel final    : {result.excel_output}")
        return 0
    else:
        print(f"\n⚠ Pipeline terminé avec des problèmes")
        print(f"  Voir le rapport pour les détails: {result.output_report}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
