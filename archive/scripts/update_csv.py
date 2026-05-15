#!/usr/bin/env python3
"""
Mise à jour du fichier AO-completed.csv avec les nouveaux marchés et les doublons
"""

import csv
import json
from pathlib import Path
from datetime import datetime

# Chemins des fichiers
CSV_FILE = Path("/home/michka/Documents/0-AO-DCE/AO-completed.csv")
JSON_FILE = Path("/home/michka/Documents/0-AO-DCE/rapport_redondances.json")
OUTPUT_FILE = Path("/home/michka/Documents/0-AO-DCE/AO-completed-updated.csv")

def load_existing_csv():
    """Charge le CSV existant"""
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames
    return rows, fieldnames

def load_json_data():
    """Charge les données JSON"""
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_ref_from_filename(filename):
    """Extrait la référence du nom de fichier HTML"""
    # Enlever l'extension .html
    ref = filename.replace('.html', '')
    # Enlever les suffixes de type d'AO
    ref = ref.split('-2026-')[0] if '-2026-' in ref else ref
    return ref

def find_existing_row(existing_rows, ref, filename):
    """Trouve une ligne existante par référence ou nom de fichier"""
    for row in existing_rows:
        if row.get('Référence') == ref:
            return row
        # Vérifier aussi par nom de fichier dans match_source
        if filename and filename in str(row.get('match_source', '')):
            return row
    return None

def create_new_row(market_data, duplicate_info=None):
    """Crée une nouvelle ligne CSV à partir des données du marché"""
    filename = market_data.get('filename', '')
    ref = market_data.get('reference', '')
    
    # Déterminer la plateforme depuis le nom de fichier
    plateforme = ''
    if 'joue' in filename.lower():
        plateforme = 'JOUE'
    elif 'boamp' in filename.lower():
        plateforme = 'BOAMP'
    elif 'parisien' in filename.lower():
        plateforme = 'PQR'
    elif 'ao-' in filename.lower():
        plateforme = 'Marchés Online'
    elif 'orgacronyme' in filename.lower():
        plateforme = 'PLACE'
    
    # Construire l'URL si possible
    url = ''
    if 'francemarches.com' in filename or plateforme in ['JOUE', 'BOAMP', 'PQR']:
        base_name = filename.replace('.html', '')
        url = f"https://www.francemarches.com/appel-offre/{base_name}"
    
    row = {
        'Référence': ref,
        'Intitulé synthétique': market_data.get('title', '')[:100],
        "Type d'AO": '',
        'Type': '',
        'Fonction publique': '',
        'Acheteur_auto': market_data.get('buyer', ''),
        'Acheteur_manual': '',
        'Acheteur_clean': market_data.get('buyer', '')[:50],
        'Localisation_auto': '',
        'Localisation_manual': '',
        'Localisation': '',
        'Localisation_clean': '',
        'Date_limite_auto': '',
        'Date_limite_manual': '',
        'Date limite de remise des offres': '',
        'Durée initiale du marché': '',
        'Reconduction(s)': '',
        'Estimation_auto': '',
        'Estimation_manual': '',
        'Estimation du marché': '',
        'URL source HTTPS': url,
        'Plateforme': plateforme,
        'match_status': 'matched' if plateforme else 'unmatched',
        'match_source': filename,
        'review_needed': 'oui' if duplicate_info else '',
        'extraction_notes': f"Doublon potentiel: {duplicate_info}" if duplicate_info else '',
        'Colonne 1': '',
        'Colonne 2': '',
        'Column 29': ''
    }
    return row

def update_csv():
    """Met à jour le CSV"""
    print("Chargement du CSV existant...")
    existing_rows, fieldnames = load_existing_csv()
    print(f"  {len(existing_rows)} lignes existantes")
    
    print("\nChargement des données JSON...")
    json_data = load_json_data()
    print(f"  {len(json_data['data'])} marchés analysés")
    print(f"  {len(json_data['duplicates'])} doublons identifiés")
    
    # Créer un ensemble des fichiers à marquer comme doublons
    duplicate_files = set()
    duplicate_mapping = {}
    for dup in json_data['duplicates']:
        file1 = dup['file1']
        file2 = dup['file2']
        duplicate_files.add(file1)
        duplicate_files.add(file2)
        duplicate_mapping[file1] = f"Doublon avec {file2} (score: {dup['score']}) - {', '.join(dup['reasons'])}"
        duplicate_mapping[file2] = f"Doublon avec {file1} (score: {dup['score']}) - {', '.join(dup['reasons'])}"
    
    # Identifier les nouveaux marchés
    new_markets = []
    updated_count = 0
    
    for market in json_data['data']:
        filename = market['filename']
        ref = market.get('reference', '')
        
        # Chercher si déjà présent
        existing = find_existing_row(existing_rows, ref, filename)
        
        if existing:
            # Mettre à jour les informations si c'est un doublon
            if filename in duplicate_files:
                existing['review_needed'] = 'oui'
                existing['extraction_notes'] = duplicate_mapping.get(filename, 'Doublon potentiel')
                updated_count += 1
        else:
            # Nouveau marché
            dup_info = duplicate_mapping.get(filename) if filename in duplicate_files else None
            new_row = create_new_row(market, dup_info)
            new_markets.append(new_row)
    
    print(f"\n  {len(new_markets)} nouveaux marchés à ajouter")
    print(f"  {updated_count} lignes existantes marquées comme doublons")
    
    # Combiner toutes les lignes
    all_rows = existing_rows + new_markets
    
    # Écrire le fichier CSV mis à jour
    print(f"\nÉcriture du fichier mis à jour: {OUTPUT_FILE}")
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    
    # Créer un rapport de synthèse
    report = {
        'date_mise_a_jour': datetime.now().isoformat(),
        'fichier_original': str(CSV_FILE),
        'fichier_sortie': str(OUTPUT_FILE),
        'statistiques': {
            'lignes_avant': len(existing_rows),
            'lignes_apres': len(all_rows),
            'nouveaux_marches': len(new_markets),
            'doublons_identifies': len(duplicate_files),
            'lignes_marquees_doublon': updated_count
        },
        'nouveaux_marches': [
            {
                'reference': m['Référence'],
                'titre': m['Intitulé synthétique'],
                'acheteur': m['Acheteur_clean'],
                'plateforme': m['Plateforme']
            } for m in new_markets
        ],
        'doublons_a_verifier': [
            {
                'fichier1': d['file1'],
                'fichier2': d['file2'],
                'acheteur': d['buyer'],
                'score': d['score'],
                'raisons': d['reasons']
            } for d in json_data['duplicates']
        ]
    }
    
    report_file = Path("/home/michka/Documents/0-AO-DCE/update_report.json")
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\nRapport de mise à jour sauvegardé: {report_file}")
    
    return report

def print_summary(report):
    """Affiche un résumé de la mise à jour"""
    print("\n" + "=" * 80)
    print("RÉSUMÉ DE LA MISE À JOUR")
    print("=" * 80)
    
    stats = report['statistiques']
    print(f"\nLignes avant:    {stats['lignes_avant']}")
    print(f"Lignes après:    {stats['lignes_apres']}")
    print(f"Nouveaux:        {stats['nouveaux_marches']}")
    print(f"Doublons:        {stats['doublons_identifies']} fichiers")
    
    print("\n" + "-" * 80)
    print("NOUVEAUX MARCHÉS AJOUTÉS:")
    print("-" * 80)
    for m in report['nouveaux_marchés']:
        print(f"  • {m['reference']:<20} | {m['titre'][:50]:<50} | {m['plateforme']}")
    
    print("\n" + "-" * 80)
    print("DOUBLONS À VÉRIFIER:")
    print("-" * 80)
    for i, d in enumerate(report['doublons_a_verifier'], 1):
        print(f"\n{i}. Score: {d['score']}/8")
        print(f"   Acheteur: {d['acheteur']}")
        print(f"   Raisons: {', '.join(d['raisons'])}")
        print(f"   → {d['fichier1'][:60]}")
        print(f"   → {d['fichier2'][:60]}")

if __name__ == "__main__":
    report = update_csv()
    print_summary(report)
