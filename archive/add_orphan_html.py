"""
Ajoute les fichiers HTML orphelins au CSV comme nouveaux marchés.

Un fichier est considéré orphelin si:
- Il n'est pas référencé dans la colonne 'match_source' du CSV
- Sa référence (basée sur le nom de fichier) n'existe pas dans la colonne 'Référence'
"""

import csv
import json
import logging
from pathlib import Path
from datetime import datetime

from ao_etl.sources.router import extract_for_source
from ao_etl.models.market import MarketData, SourceType

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def load_csv(filepath: Path) -> tuple[list[dict], list[str]]:
    """Charge le CSV et retourne les lignes + fieldnames."""
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = [dict(row) for row in reader]
    return rows, fieldnames


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


def get_matched_files(csv_rows: list[dict]) -> set[str]:
    """Retourne l'ensemble des fichiers HTML déjà matchés dans le CSV."""
    matched = set()
    for row in csv_rows:
        # Colonne match_source contient le nom du fichier HTML
        match_source = row.get('match_source', '').strip()
        if match_source and match_source != '-':
            matched.add(match_source)
        
        # Vérifier aussi la référence pour les Marchés Online
        reference = row.get('Référence', '').strip()
        if reference.startswith('MO-') or reference.startswith('ao-'):
            # Extrait l'ID pour retrouver le fichier
            matched.add(reference)
    
    return matched


def is_orphan(html_file: Path, matched_files: set[str], csv_refs: set[str]) -> bool:
    """Vérifie si un fichier HTML est orphelin."""
    filename = html_file.name
    
    # Déjà matché par nom de fichier
    if filename in matched_files:
        return False
    
    # Vérifier par référence pour Marchés Online
    if filename.startswith('ao-'):
        # Extraire l'ID (ex: ao-9597894-1 → 9597894)
        parts = filename.replace('ao-', '').split('-')
        if parts:
            mo_ref = f"MO-{parts[0]}"
            if mo_ref in csv_refs or parts[0] in csv_refs:
                return False
    
    # Vérifier pour France Marchés
    for ref in csv_refs:
        if ref and ref != '-' and ref.lower() in filename.lower().replace('-', ''):
            return False
    
    return True


def extract_to_csv_row(data: MarketData, html_file: Path) -> dict:
    """Convertit les données extraites en ligne CSV."""
    # Déterminer la plateforme
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
    
    # Construire la ligne CSV
    row = {
        'Référence': data.reference or '-',
        'Intitulé synthétique': data.title or '-',
        'Type d\'AO': data.type_ao or '-',
        'Type': data.type_marche or '-',
        'Fonction publique': data.fonction_publique or '-',
        'Acheteur_auto': data.buyer or '-',
        'Acheteur_manual': '',
        'Acheteur_clean': data.buyer or '-',
        'Localisation_auto': data.location or '-',
        'Localisation_manual': '',
        'Localisation': data.location or '-',
        'Localisation_clean': data.location or '-',
        'Date_limite_auto': data.date_limite or '-',
        'Date_limite_manual': '',
        'Date limite de remise des offres': data.date_limite or '-',
        'Durée initiale du marché': '-',
        'Reconduction(s)': '-',
        'Estimation_auto': data.estimation or '-',
        'Estimation_manual': '',
        'Estimation du marché': data.estimation or '-',
        'URL source HTTPS': data.url or '-',
        'Plateforme': plateforme,
        'match_status': 'new',
        'match_source': html_file.name,
        'review_needed': 'oui' if not data.title or not data.buyer else '',
        'extraction_notes': '; '.join(data.extraction_notes) if data.extraction_notes else '',
        'source_type': data.source_type.value,
    }
    
    return row


def add_orphan_entries(input_csv: Path, html_dir: Path, output_csv: Path) -> dict:
    """Ajoute les entrées orphelines au CSV.
    
    Returns:
        Statistiques de l'opération
    """
    log.info(f"Chargement CSV: {input_csv}")
    rows, fieldnames = load_csv(input_csv)
    log.info(f"  → {len(rows)} lignes existantes")
    
    # Récupérer les fichiers déjà matchés
    matched_files = get_matched_files(rows)
    csv_refs = {row.get('Référence', '').strip() for row in rows if row.get('Référence')}
    log.info(f"  → {len(matched_files)} fichiers déjà matchés")
    
    # Vérifier les colonnes requises
    required_cols = ['source_type', 'match_status', 'review_needed']
    for col in required_cols:
        if col not in fieldnames:
            fieldnames.append(col)
    
    # Trouver les fichiers orphelins
    all_html_files = list(html_dir.glob('*.html'))
    orphan_files = [f for f in all_html_files if is_orphan(f, matched_files, csv_refs)]
    log.info(f"  → {len(orphan_files)} fichiers orphelins trouvés sur {len(all_html_files)}")
    
    stats = {
        'total_html': len(all_html_files),
        'already_matched': len(matched_files),
        'orphan_found': len(orphan_files),
        'successfully_added': 0,
        'errors': 0,
        'new_entries': [],
    }
    
    # Traiter chaque fichier orphelin
    for i, html_file in enumerate(orphan_files, 1):
        log.info(f"[{i}/{len(orphan_files)}] Traitement: {html_file.name}")
        
        try:
            data = extract_for_source(html_file)
            new_row = extract_to_csv_row(data, html_file)
            
            # Compléter avec les colonnes manquantes
            for field in fieldnames:
                if field not in new_row:
                    new_row[field] = '-'
            
            rows.append(new_row)
            stats['successfully_added'] += 1
            stats['new_entries'].append({
                'file': html_file.name,
                'reference': new_row['Référence'],
                'title': new_row['Intitulé synthétique'][:80] + '...' if len(new_row['Intitulé synthétique']) > 80 else new_row['Intitulé synthétique'],
                'buyer': new_row['Acheteur_auto'][:50] + '...' if len(new_row['Acheteur_auto']) > 50 else new_row['Acheteur_auto'],
            })
            
            log.info(f"  ✓ Ajouté: {new_row['Référence']}")
            
        except Exception as e:
            log.error(f"  ✗ Erreur extraction {html_file.name}: {e}")
            stats['errors'] += 1
    
    # Sauvegarder le CSV mis à jour
    log.info(f"Sauvegarde: {output_csv}")
    save_csv(output_csv, rows, fieldnames)
    log.info(f"  → {len(rows)} lignes totales ({len(rows) - stats['successfully_added']} existantes + {stats['successfully_added']} nouvelles)")
    
    return stats


def generate_report(stats: dict, report_path: Path) -> None:
    """Génère un rapport JSON des ajouts."""
    report = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_html_files': stats['total_html'],
            'already_matched': stats['already_matched'],
            'orphan_found': stats['orphan_found'],
            'successfully_added': stats['successfully_added'],
            'errors': stats['errors'],
        },
        'new_entries': stats['new_entries'],
    }
    
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    log.info(f"Rapport sauvegardé: {report_path}")


def main():
    """Point d'entrée principal."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Ajoute les fichiers HTML orphelins au CSV")
    parser.add_argument('--input', '-i', default='AO-completed-updated.csv', help="CSV d'entrée")
    parser.add_argument('--output', '-o', default='AO-completed-final.csv', help="CSV de sortie")
    parser.add_argument('--html-dir', '-d', default='html_ao', help="Répertoire HTML")
    parser.add_argument('--report', '-r', default='orphan_additions_report.json', help="Rapport JSON")
    
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
    stats = add_orphan_entries(input_csv, html_dir, output_csv)
    generate_report(stats, report_path)
    
    # Résumé
    print("\n" + "="*60)
    print("RÉSUMÉ DES AJOUTS")
    print("="*60)
    print(f"Fichiers HTML total:     {stats['total_html']}")
    print(f"Déjà matchés:            {stats['already_matched']}")
    print(f"Orphelins trouvés:       {stats['orphan_found']}")
    print(f"Ajoutés avec succès:     {stats['successfully_added']}")
    print(f"Erreurs:                 {stats['errors']}")
    print(f"CSV final:               {output_csv} ({stats['successfully_added'] + stats['already_matched']} lignes)")
    print(f"Rapport:                 {report_path}")
    print("="*60)
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
