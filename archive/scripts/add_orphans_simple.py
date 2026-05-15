#!/usr/bin/env python3
"""Script pour ajouter les orphelins au CSV avec extraction complète.

Utilise les extracteurs ao_etl.sources pour extraire tous les champs pertinents
y compris l'acheteur (Acheteur_auto).
"""

import csv
import json
import logging
from pathlib import Path
from datetime import datetime

# Import des extracteurs du projet
import sys
sys.path.insert(0, str(Path(__file__).parent))
from ao_etl.sources.router import extract_for_source

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# Configuration
INPUT_CSV = Path('AO-completed-updated.csv')
OUTPUT_CSV = Path('AO-completed-final.csv')
HTML_DIR = Path('html_ao')
REPORT_PATH = Path('orphan_additions_report.json')

def load_csv(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else []
        rows = [dict(row) for row in reader]
    return rows, fieldnames

def save_csv(filepath, rows, fieldnames):
    for row in rows:
        for field in fieldnames:
            if field not in row:
                row[field] = '-'
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

def get_matched_files(csv_rows):
    matched = set()
    for row in csv_rows:
        match_source = row.get('match_source', '').strip()
        if match_source and match_source != '-' and match_source.endswith('.html'):
            matched.add(match_source)
    return matched

def extract_with_full_data(html_file):
    """Extraction complète via les extracteurs ao_etl.sources.
    
    Returns:
        dict avec tous les champs extraits ou None si échec
    """
    try:
        data = extract_for_source(html_file)
        
        # Mapper les données extraites sur le format CSV
        return {
            'reference': data.reference,
            'title': data.title,
            'buyer': data.buyer,
            'cpv': data.cpv,
            'date_limite': data.date_limite,
            'estimation': data.estimation,
            'location': data.location,
            'source_type': data.source_type.value if data.source_type else 'UNKNOWN',
            'plateforme': _get_plateforme(data.source_type),
            'url': data.url,
            'extraction_notes': '; '.join(data.extraction_notes) if data.extraction_notes else '',
        }
    except Exception as e:
        log.warning(f"Extraction complète échouée pour {html_file.name}: {e}")
        # Fallback sur extraction basique
        return _extract_basic(html_file)

def _get_plateforme(source_type):
    """Convertit le source_type en nom de plateforme."""
    if not source_type:
        return 'Standard'
    source_str = str(source_type).upper()
    if 'MARCHES_ONLINE' in source_str:
        return 'Marchés Online'
    elif 'FRANCE_MARCHES' in source_str:
        return 'France Marchés'
    elif 'BOAMP' in source_str:
        return 'BOAMP'
    elif 'PLACE' in source_str:
        return 'PLACE'
    return 'Standard'

def _extract_basic(html_file):
    """Extraction basique en fallback si l'extraction complète échoue."""
    content = html_file.read_text(encoding='utf-8')
    
    # Détection source
    if 'marchesonline.com' in content or html_file.name.startswith('ao-'):
        source = 'MARCHES_ONLINE'
        plateforme = 'Marchés Online'
        parts = html_file.name.replace('ao-', '').replace('.html', '').split('-')
        reference = f"MO-{parts[0]}" if parts else f"MO-{html_file.name}"
    elif 'francemarches.com' in content:
        source = 'FRANCE_MARCHES'
        plateforme = 'France Marchés'
        import re
        match = re.search(r'/(appel-offre|consultation)/([^/]+)', content)
        reference = match.group(2) if match else html_file.name.replace('.html', '')
    else:
        source = 'STANDARD'
        plateforme = 'Standard'
        reference = html_file.name.replace('.html', '')
    
    # Extraction basique du titre
    import re
    title_match = re.search(r'<h1[^>]*>(.*?)</h1>', content, re.DOTALL | re.IGNORECASE)
    if not title_match:
        title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.DOTALL | re.IGNORECASE)
    title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()[:200] if title_match else '-'
    
    return {
        'reference': reference,
        'title': title,
        'buyer': None,  # Non extrait en mode basique
        'cpv': None,
        'date_limite': None,
        'estimation': None,
        'location': None,
        'source_type': source,
        'plateforme': plateforme,
        'url': None,
        'extraction_notes': f'Extraction basique (erreur extracteur): {html_file.name}',
    }

def main():
    print("Chargement CSV...")
    rows, fieldnames = load_csv(INPUT_CSV)
    print(f"  → {len(rows)} lignes existantes")
    
    matched = get_matched_files(rows)
    print(f"  → {len(matched)} fichiers déjà matchés")
    
    # Ajouter colonnes si manquantes
    for col in ['source_type', 'match_status']:
        if col not in fieldnames:
            fieldnames.append(col)
    
    # Trouver les orphelins
    all_html = list(HTML_DIR.glob('*.html'))
    orphans = [f for f in all_html if f.name not in matched]
    print(f"  → {len(orphans)} fichiers orphelins sur {len(all_html)}")
    
    new_entries = []
    errors = []
    
    for i, html_file in enumerate(orphans, 1):
        print(f"[{i}/{len(orphans)}] {html_file.name}", end=' ')
        try:
            data = extract_with_full_data(html_file)
            
            row = {
                'Référence': data['reference'] or '-',
                'Intitulé synthétique': data['title'] or '-',
                'Type d\'AO': '-',
                'Type': '-',
                'Fonction publique': '-',
                'Acheteur_auto': data['buyer'] or '-',
                'Acheteur_manual': '',
                'Acheteur_clean': data['buyer'] or '-',
                'Localisation_auto': data['location'] or '-',
                'Localisation_manual': '',
                'Localisation': data['location'] or '-',
                'Localisation_clean': data['location'] or '-',
                'Date_limite_auto': data['date_limite'] or '-',
                'Date_limite_manual': '',
                'Date limite de remise des offres': data['date_limite'] or '-',
                'Durée initiale du marché': '-',
                'Reconduction(s)': '-',
                'Estimation_auto': data['estimation'] or '-',
                'Estimation_manual': '',
                'Estimation du marché': data['estimation'] or '-',
                'URL source HTTPS': data['url'] or '-',
                'Plateforme': data['plateforme'],
                'match_status': 'new',
                'match_source': html_file.name,
                'review_needed': 'oui' if not data['buyer'] else '',
                'extraction_notes': data['extraction_notes'] or 'Nouveau marché ajouté depuis fichier orphelin',
                'source_type': data['source_type'],
            }
            
            # Compléter colonnes manquantes
            for f in fieldnames:
                if f not in row:
                    row[f] = '-'
            
            rows.append(row)
            new_entries.append({
                'file': html_file.name,
                'reference': data['reference'],
                'title': data['title'][:60] + '...' if len(data['title']) > 60 else data['title'],
            })
            print("✓")
            
        except Exception as e:
            errors.append({'file': html_file.name, 'error': str(e)})
            print(f"✗ {e}")
    
    # Sauvegarder
    print(f"\nSauvegarde: {OUTPUT_CSV}")
    save_csv(OUTPUT_CSV, rows, fieldnames)
    print(f"  → {len(rows)} lignes totales ({len(rows) - len(new_entries)} + {len(new_entries)} nouvelles)")
    
    # Rapport
    report = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_html': len(all_html),
            'already_matched': len(matched),
            'orphan_found': len(orphans),
            'successfully_added': len(new_entries),
            'errors': len(errors),
        },
        'new_entries': new_entries,
        'errors': errors,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Rapport: {REPORT_PATH}")
    
    # Statistiques Acheteur
    with_buyer = sum(1 for e in new_entries if e.get('buyer'))
    without_buyer = len(new_entries) - with_buyer
    
    print("\n" + "="*50)
    print("RÉSUMÉ")
    print("="*50)
    print(f"Nouveaux marchés ajoutés: {len(new_entries)}")
    print(f"  - Avec Acheteur_auto: {with_buyer}")
    print(f"  - Sans Acheteur_auto: {without_buyer}")
    print(f"Erreurs: {len(errors)}")
    if errors:
        print("\nErreurs:")
        for e in errors:
            print(f"  - {e['file']}: {e['error']}")

if __name__ == '__main__':
    main()
