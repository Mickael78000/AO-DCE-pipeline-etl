#!/usr/bin/env python3
"""Retire les lignes CSV sans fichier HTML associé.

Objectif: avoir exactement autant de lignes que de fichiers HTML.
"""

import argparse
from pathlib import Path
from typing import List, Dict, Set, Tuple

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import read_csv, write_csv, get_html_dir, get_output_path


def get_html_files(html_dir: Path) -> Set[str]:
    """Liste tous les fichiers HTML du répertoire."""
    return set(f.name for f in html_dir.glob('*.html'))


def filter_rows(
    rows: List[Dict[str, str]],
    html_files: Set[str],
    match_field: str = 'match_source'
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """
    Filtre les lignes CSV pour ne garder que celles avec fichier HTML associé.
    
    Returns:
        (matched_rows, unmatched_rows)
    """
    matched_rows = []
    unmatched_rows = []
    seen_files: Set[str] = set()
    
    for row in rows:
        match_source = row.get(match_field, '').strip()
        
        if match_source and match_source in html_files:
            if match_source not in seen_files:
                matched_rows.append(row)
                seen_files.add(match_source)
            else:
                unmatched_rows.append(row)
        else:
            unmatched_rows.append(row)
    
    return matched_rows, unmatched_rows


def generate_report(
    report_path: Path,
    html_count: int,
    total_rows: int,
    removed_rows: int,
    final_rows: int,
    unmatched: List[Dict[str, str]]
) -> None:
    """Génère le rapport de nettoyage."""
    lines = [
        "RAPPORT DE NETTOYAGE - Lignes sans fichier HTML",
        "=" * 70,
        "",
        f"Fichiers HTML: {html_count}",
        f"Lignes CSV initiales: {total_rows}",
        f"Lignes retirées: {removed_rows}",
        f"Lignes finales: {final_rows}",
        "",
        "LIGNES RETIRÉES:",
        "-" * 70,
    ]
    
    for row in unmatched:
        ref = row.get('reference') or row.get('Référence', 'N/A')
        title = row.get('Intitulé synthétique') or row.get('titre', 'N/A')
        lines.append(f"- {ref}: {title}")
    
    report_path.write_text('\n'.join(lines), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(
        description="Retire les lignes CSV sans fichier HTML associé"
    )
    parser.add_argument(
        '--html-dir', '-d',
        type=Path,
        default=None,
        help="Répertoire des fichiers HTML (défaut: data/raw/html ou html_ao)"
    )
    parser.add_argument(
        '--input', '-i',
        type=Path,
        default=None,
        help="Fichier CSV d'entrée (défaut: AO-pipeline-v2.csv)"
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        default=None,
        help="Fichier CSV de sortie (défaut: AO-pipeline-v2-clean.csv)"
    )
    parser.add_argument(
        '--match-field', '-f',
        default='match_source',
        help="Nom du champ contenant le nom du fichier HTML (défaut: match_source)"
    )
    args = parser.parse_args()
    
    # Détection chemins
    html_dir = args.html_dir
    if html_dir is None:
        html_dir = get_html_dir() if get_html_dir().exists() else Path('html_ao')
    
    input_csv = args.input or get_output_path('AO-pipeline-v2.csv')
    output_csv = args.output or get_output_path('AO-pipeline-v2-clean.csv')
    
    # 1. Lister HTML
    html_files = get_html_files(html_dir)
    print(f"Fichiers HTML trouvés: {len(html_files)}")
    
    # 2. Charger CSV
    rows, fieldnames = read_csv(input_csv)
    print(f"Lignes CSV en entrée: {len(rows)}")
    
    # 3. Filtrer
    matched_rows, unmatched_rows = filter_rows(rows, html_files, args.match_field)
    
    print(f"\nLignes avec fichier HTML: {len(matched_rows)}")
    print(f"Lignes sans fichier HTML (retirées): {len(unmatched_rows)}")
    
    # 4. Afficher lignes retirées
    if unmatched_rows:
        print("\n--- Lignes retirées ---")
        for row in unmatched_rows:
            ref = row.get('reference') or row.get('Référence', 'N/A')[:30]
            title = row.get('Intitulé synthétique') or row.get('titre', 'N/A')[:40]
            match_source = row.get(args.match_field, 'N/A')
            print(f"  - {ref:<30} | {title:<40} | match_source: {match_source}")
    
    # 5. Sauvegarder
    write_csv(output_csv, matched_rows, fieldnames)
    print(f"\n✓ CSV nettoyé sauvegardé: {output_csv}")
    print(f"  Lignes finales: {len(matched_rows)}")
    
    # 6. Rapport
    report_path = output_csv.parent / 'cleanup-unmatched-report.txt'
    generate_report(
        report_path,
        len(html_files),
        len(rows),
        len(unmatched_rows),
        len(matched_rows),
        unmatched_rows
    )
    print(f"✓ Rapport sauvegardé: {report_path}")

if __name__ == '__main__':
    main()
