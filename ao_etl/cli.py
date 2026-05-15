"""Interface en ligne de commande pour l'ETL AO."""

import argparse
import json
import logging
import sys
from pathlib import Path

from ao_etl.sources.router import extract_for_source
from ao_etl.models.market import MarketData

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
log = logging.getLogger(__name__)


def cmd_extract(args: argparse.Namespace) -> int:
    """Commande: extraction d'un ou plusieurs fichiers HTML."""
    html_dir = Path(args.input_dir)
    
    if not html_dir.exists():
        log.error(f"Répertoire non trouvé: {html_dir}")
        return 1
    
    results = []
    html_files = list(html_dir.glob("*.html"))
    
    log.info(f"Analyse de {len(html_files)} fichiers HTML...")
    
    for filepath in sorted(html_files):
        try:
            data = extract_for_source(filepath)
            results.append(data)
            
            status_icon = "✓" if data.is_complete() else "⚠" if data.reference else "✗"
            log.info(f"{status_icon} {filepath.name}: {data.reference or 'N/A'} | {data.title[:40] or 'N/A'}...")
            
        except Exception as e:
            log.error(f"✗ {filepath.name}: {e}")
            results.append(MarketData(
                filename=filepath.name,
                extraction_notes=[f"ERROR: {e}"]
            ))
    
    # Export JSON si demandé
    if args.output:
        output_path = Path(args.output)
        export_data = {
            "total": len(results),
            "parsed": sum(1 for r in results if r.reference or r.title),
            "complete": sum(1 for r in results if r.is_complete()),
            "data": [
                {
                    "filename": r.filename,
                    "source_type": r.source_type.value,
                    "title": r.title,
                    "reference": r.reference,
                    "buyer": r.buyer,
                    "cpv": r.cpv,
                    "is_alias": r.is_alias,
                    "alias_of": r.alias_of,
                }
                for r in results
            ]
        }
        output_path.write_text(json.dumps(export_data, indent=2, ensure_ascii=False))
        log.info(f"Rapport sauvegardé: {output_path}")
    
    # Résumé
    total = len(results)
    complete = sum(1 for r in results if r.is_complete())
    partial = sum(1 for r in results if r.reference or r.title and not r.is_complete())
    failed = total - complete - partial
    
    print(f"\n{'='*60}")
    print("RÉSUMÉ")
    print(f"{'='*60}")
    print(f"Total fichiers:     {total}")
    print(f"Extraction complète: {complete} ({complete/total*100:.1f}%)")
    print(f"Extraction partielle: {partial} ({partial/total*100:.1f}%)")
    print(f"Échec:              {failed} ({failed/total*100:.1f}%)")
    print(f"{'='*60}")
    
    return 0


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée principal du CLI."""
    parser = argparse.ArgumentParser(
        prog="ao-etl",
        description="Pipeline ETL pour extraction d'appels d'offres publics"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Commande: extract
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extraire les données des fichiers HTML"
    )
    extract_parser.add_argument(
        "input_dir",
        help="Répertoire contenant les fichiers HTML"
    )
    extract_parser.add_argument(
        "-o", "--output",
        help="Chemin du fichier JSON de sortie"
    )
    extract_parser.set_defaults(func=cmd_extract)
    
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
