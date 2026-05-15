"""
Mise à jour du CSV AO avec le nouveau système d'extraction sources/.

Ce script remplace update_csv.py legacy avec:
- Extraction via les nouveaux extracteurs modulaires
- Gestion des triplets _auto/_manual/_final
- Rapport de mise à jour détaillé
"""

import csv
import json
import logging
from pathlib import Path
from datetime import datetime
from collections import defaultdict

from ao_etl.sources.router import extract_for_source
from ao_etl.models.market import MarketData, SourceType

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def load_csv(filepath: Path) -> list[dict]:
    """Charge le CSV et retourne les lignes comme listes de dicts."""
    rows = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(dict(row))
    return rows


def save_csv(filepath: Path, rows: list[dict], fieldnames: list[str]) -> None:
    """Sauvegarde les lignes dans un CSV."""
    # S'assurer que toutes les lignes ont toutes les clés
    for row in rows:
        for field in fieldnames:
            if field not in row:
                row[field] = ''
    
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def find_html_file(reference: str, html_dir: Path) -> Path | None:
    """Trouve le fichier HTML correspondant à une référence.
    
    Stratégies de matching:
    1. Nom de fichier contenant la référence
    2. Pattern spécifique selon le type de référence
    """
    if not reference or reference == '-':
        return None
    
    # Nettoyer la référence pour la recherche
    ref_clean = reference.replace('/', '').replace('-', '').lower()
    
    for html_file in html_dir.glob('*.html'):
        name = html_file.name.lower()
        
        # Matching exact ou partiel
        if ref_clean in name.replace('-', '').replace('_', ''):
            return html_file
        
        # Matching pour MO-XXXX → ao-XXXX
        if reference.startswith('MO-'):
            mo_id = reference[3:]
            if f'ao-{mo_id}' in name:
                return html_file
    
    return None


def extract_and_merge(row: dict, html_file: Path) -> tuple[dict, list[str]]:
    """Extrait les données du HTML et fusionne avec la ligne CSV.
    
    Returns:
        (row_mise_a_jour, liste_des_changements)
    """
    changes = []
    
    try:
        data = extract_for_source(html_file)
    except Exception as e:
        log.warning(f"Erreur extraction {html_file.name}: {e}")
        return row, [f"ERREUR_EXTRACTION: {e}"]
    
    # Mapping des champs extraits vers les colonnes CSV
    field_mapping = {
        'title': 'Intitulé synthétique',
        'reference': 'Référence',
        'buyer': 'Acheteur_auto',
    }
    
    # Mettre à jour les champs _auto si différents et non vides
    for extracted_field, csv_field in field_mapping.items():
        extracted_value = getattr(data, extracted_field, '')
        current_value = row.get(csv_field, '')
        
        if extracted_value and extracted_value.strip():
            if not current_value or current_value.strip() == '-':
                row[csv_field] = extracted_value
                changes.append(f"{csv_field}: '{current_value}' → '{extracted_value}'")
            elif extracted_value != current_value:
                # Valeur différente - logguer pour review
                changes.append(f"{csv_field}_DIFF: '{current_value}' vs '{extracted_value}'")
    
    # Mise à jour source_type si pertinent
    if data.source_type != SourceType.UNKNOWN:
        row['source_type'] = data.source_type.value
    
    # Ajouter notes d'extraction
    if data.extraction_notes:
        existing_notes = row.get('extraction_notes', '')
        row['extraction_notes'] = existing_notes + '; ' + '; '.join(data.extraction_notes)
    
    return row, changes


def apply_manual_overrides(row: dict) -> dict:
    """Applique la règle: valeur finale = manual si non vide, sinon auto."""
    triplets = [
        ('Acheteur_auto', 'Acheteur_manual', 'Acheteur'),
        ('Localisation_auto', 'Localisation_manual', 'Localisation'),
        ('Date_limite_auto', 'Date_limite_manual', 'Date limite de remise des offres'),
        ('Estimation_auto', 'Estimation_manual', 'Estimation du marché'),
    ]
    
    for auto_field, manual_field, final_field in triplets:
        manual_value = row.get(manual_field, '').strip()
        auto_value = row.get(auto_field, '').strip()
        
        if manual_value:
            row[final_field] = manual_value
        elif auto_value:
            row[final_field] = auto_value
        else:
            row[final_field] = '-'
    
    return row


def update_csv(input_csv: Path, html_dir: Path, output_csv: Path) -> dict:
    """Met à jour le CSV avec les données extraites des fichiers HTML.
    
    Returns:
        Statistiques de mise à jour
    """
    log.info(f"Chargement CSV: {input_csv}")
    rows = load_csv(input_csv)
    log.info(f"  → {len(rows)} lignes chargées")
    
    # Déterminer les colonnes (utiliser celles du CSV + champs additionnels)
    if rows:
        fieldnames = list(rows[0].keys())
        # Ajouter les champs manquants
        for field in ['source_type', 'extraction_notes']:
            if field not in fieldnames:
                fieldnames.append(field)
    else:
        fieldnames = []
    
    stats = {
        'total_rows': len(rows),
        'matched': 0,
        'updated': 0,
        'errors': 0,
        'changes': [],
        'source_distribution': defaultdict(int),
    }
    
    updated_rows = []
    
    for i, row in enumerate(rows, 1):
        reference = row.get('Référence', '')
        
        log.info(f"[{i}/{len(rows)}] Traitement: {reference or 'N/A'}")
        
        # Trouver le fichier HTML correspondant
        html_file = find_html_file(reference, html_dir)
        
        if html_file:
            log.info(f"  → HTML trouvé: {html_file.name}")
            row, changes = extract_and_merge(row, html_file)
            stats['matched'] += 1
            
            if changes:
                stats['updated'] += 1
                stats['changes'].append({
                    'reference': reference,
                    'file': html_file.name,
                    'changes': changes,
                })
            
            # Compter les sources
            if 'source_type' in row:
                stats['source_distribution'][row['source_type']] += 1
        else:
            log.info(f"  → Pas de HTML trouvé")
            changes = ["NO_HTML_MATCH"]
        
        # Appliquer les overrides manual/auto
        row = apply_manual_overrides(row)
        
        updated_rows.append(row)
    
    # Sauvegarder le CSV mis à jour
    log.info(f"Sauvegarde: {output_csv}")
    save_csv(output_csv, updated_rows, fieldnames)
    
    return dict(stats)


def generate_report(stats: dict, report_path: Path) -> None:
    """Génère un rapport JSON de la mise à jour."""
    report = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_rows': stats['total_rows'],
            'matched': stats['matched'],
            'updated': stats['updated'],
            'errors': stats['errors'],
            'match_rate': f"{stats['matched']/stats['total_rows']*100:.1f}%" if stats['total_rows'] else "N/A",
        },
        'source_distribution': dict(stats['source_distribution']),
        'changes': stats['changes'],
    }
    
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    log.info(f"Rapport sauvegardé: {report_path}")


def main():
    """Point d'entrée principal."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Mise à jour CSV AO avec extraction moderne")
    parser.add_argument('--input', '-i', default='AO-completed.csv', help="CSV d'entrée")
    parser.add_argument('--output', '-o', default='AO-completed-updated.csv', help="CSV de sortie")
    parser.add_argument('--html-dir', '-d', default='html_ao', help="Répertoire HTML")
    parser.add_argument('--report', '-r', default='update_report_modern.json', help="Rapport JSON")
    
    args = parser.parse_args()
    
    input_csv = Path(args.input)
    output_csv = Path(args.output)
    html_dir = Path(args.html_dir)
    report_path = Path(args.report)
    
    if not input_csv.exists():
        log.error(f"CSV d'entrée non trouvé: {input_csv}")
        return 1
    
    if not html_dir.exists():
        log.error(f"Répertoire HTML non trouvé: {html_dir}")
        return 1
    
    # Exécution
    stats = update_csv(input_csv, html_dir, output_csv)
    generate_report(stats, report_path)
    
    # Résumé
    print("\n" + "="*60)
    print("RÉSUMÉ DE LA MISE À JOUR")
    print("="*60)
    print(f"Lignes traitées:    {stats['total_rows']}")
    print(f"HTML trouvés:       {stats['matched']} ({stats['matched']/stats['total_rows']*100:.1f}%)")
    print(f"Lignes modifiées:   {stats['updated']}")
    print(f"Rapport:            {report_path}")
    print("="*60)
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
