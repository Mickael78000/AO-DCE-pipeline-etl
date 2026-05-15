#!/usr/bin/env python3
"""Corrige Acheteur_auto pour les 19 lignes orphelines déjà ajoutées.

Utilise les extracteurs ao_etl.sources pour extraire l'acheteur manquant.
"""

import csv
import json
import logging
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent))
from ao_etl.sources.router import extract_for_source

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

CSV_PATH = Path('AO-completed-final.csv')
HTML_DIR = Path('html_ao')
REPORT_PATH = Path('fix_orphan_buyers_report.json')


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


def find_html_file(match_source, html_dir):
    """Trouve le fichier HTML correspondant."""
    if not match_source or match_source == '-':
        return None
    html_file = html_dir / match_source
    if html_file.exists():
        return html_file
    return None


def extract_buyer(html_file):
    """Extrait l'acheteur via les extracteurs ao_etl.sources."""
    try:
        data = extract_for_source(html_file)
        return data.buyer, data.location, data.date_limite, data.estimation, data.url
    except Exception as e:
        log.warning(f"Extraction échouée pour {html_file.name}: {e}")
        return None, None, None, None, None


def main():
    print("="*70)
    print("CORRECTION Acheteur_auto - LIGNES ORPHELINES")
    print("="*70)
    
    # 1. Charger CSV
    print(f"\n[1] Chargement CSV: {CSV_PATH}")
    rows, fieldnames = load_csv(CSV_PATH)
    print(f"    Total lignes: {len(rows)}")
    
    # 2. Identifier les lignes orphelines (match_status = 'new')
    orphan_rows = [(i, r) for i, r in enumerate(rows) if r.get('match_status') == 'new']
    print(f"    Lignes orphelines (match_status='new'): {len(orphan_rows)}")
    
    # 3. Stats avant correction
    before_with_buyer = sum(1 for _, r in orphan_rows 
                           if r.get('Acheteur_auto') and r['Acheteur_auto'] != '-')
    print(f"    Acheteur_auto renseigné AVANT: {before_with_buyer}/{len(orphan_rows)}")
    
    # 4. Corriger chaque ligne orpheline
    print(f"\n[2] CORRECTION DES {len(orphan_rows)} LIGNES")
    print("-"*70)
    
    fixes = []
    errors = []
    unchanged = []
    
    for idx, (row_idx, row) in enumerate(orphan_rows, 1):
        match_source = row.get('match_source', '')
        current_buyer = row.get('Acheteur_auto', '')
        reference = row.get('Référence', '')
        
        print(f"[{idx}/{len(orphan_rows)}] {reference[:30]:<30} (fichier: {match_source[:25]}...)", end=' ')
        
        # Trouver le fichier HTML
        html_file = find_html_file(match_source, HTML_DIR)
        if not html_file:
            print(f"✗ Fichier HTML introuvable")
            errors.append({
                'row': row_idx,
                'reference': reference,
                'match_source': match_source,
                'error': 'Fichier HTML introuvable'
            })
            continue
        
        # Extraire l'acheteur
        buyer, location, date_lim, estim, url = extract_buyer(html_file)
        
        if buyer and buyer != '-':
            # Mettre à jour la ligne
            old_buyer = row.get('Acheteur_auto', '-')
            row['Acheteur_auto'] = buyer
            row['Acheteur_clean'] = buyer
            
            # Mettre à jour aussi les autres champs si vides
            if location and (not row.get('Localisation_auto') or row['Localisation_auto'] == '-'):
                row['Localisation_auto'] = location
                row['Localisation'] = location
                row['Localisation_clean'] = location
            
            if date_lim and (not row.get('Date_limite_auto') or row['Date_limite_auto'] == '-'):
                row['Date_limite_auto'] = date_lim
                row['Date limite de remise des offres'] = date_lim
            
            if estim and (not row.get('Estimation_auto') or row['Estimation_auto'] == '-'):
                row['Estimation_auto'] = estim
                row['Estimation du marché'] = estim
            
            if url and (not row.get('URL source HTTPS') or row['URL source HTTPS'] == '-'):
                row['URL source HTTPS'] = url
            
            # Mettre à jour review_needed si maintenant complété
            if buyer:
                row['review_needed'] = ''
            
            print(f"✓ Acheteur: {buyer[:40]}...")
            fixes.append({
                'row': row_idx,
                'reference': reference,
                'match_source': match_source,
                'old_buyer': old_buyer,
                'new_buyer': buyer,
                'location': location,
                'date_limite': date_lim,
            })
        else:
            print(f"⚠ Acheteur introuvable")
            unchanged.append({
                'row': row_idx,
                'reference': reference,
                'match_source': match_source,
                'reason': 'Acheteur non extrait'
            })
    
    # 5. Sauvegarder CSV
    print(f"\n[3] SAUVEGARDE CSV")
    save_csv(CSV_PATH, rows, fieldnames)
    print(f"    CSV mis à jour: {CSV_PATH}")
    
    # 6. Stats après correction
    after_orphan_rows = [r for r in rows if r.get('match_status') == 'new']
    after_with_buyer = sum(1 for r in after_orphan_rows 
                         if r.get('Acheteur_auto') and r['Acheteur_auto'] != '-')
    print(f"    Acheteur_auto renseigné APRÈS: {after_with_buyer}/{len(after_orphan_rows)}")
    
    # 7. Générer rapport
    report = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_orphan_rows': len(orphan_rows),
            'with_buyer_before': before_with_buyer,
            'with_buyer_after': after_with_buyer,
            'successfully_fixed': len(fixes),
            'unchanged': len(unchanged),
            'errors': len(errors),
        },
        'fixes': fixes,
        'unchanged': unchanged,
        'errors': errors,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"    Rapport généré: {REPORT_PATH}")
    
    # 8. Tableau récapitulatif
    print(f"\n[4] TABLEAU RÉCAPITULATIF")
    print("-"*70)
    print(f"{'Métrique':<40} {'Avant':<10} {'Après':<10}")
    print("-"*70)
    print(f"{'Lignes orphelines':<40} {len(orphan_rows):<10} {len(after_orphan_rows):<10}")
    print(f"{'Acheteur_auto renseigné':<40} {before_with_buyer:<10} {after_with_buyer:<10}")
    print(f"{'Taux de complétion Acheteur':<40} {before_with_buyer/len(orphan_rows)*100:.1f}%{'':<5} {after_with_buyer/len(after_orphan_rows)*100:.1f}%")
    print("-"*70)
    
    # 9. Validation rapide
    print(f"\n[5] VALIDATION RAPIDE")
    print("-"*70)
    
    # Unicité références
    refs = [r.get('Référence', '') for r in rows if r.get('Référence')]
    from collections import Counter
    dup_refs = [r for r, c in Counter(refs).items() if c > 1]
    print(f"{'Références uniques:':<40} {len(set(refs))}/{len(refs)}")
    print(f"{'Doublons de références:':<40} {len(dup_refs)} {'✓' if not dup_refs else '⚠'}")
    
    # Préservation flags
    all_new_have_flags = all(
        r.get('match_status') == 'new' and r.get('review_needed') in ['oui', '']
        for r in after_orphan_rows
    )
    print(f"{'Flags préservés (new/review_needed):':<40} {'Oui ✓' if all_new_have_flags else 'Non ✗'}")
    
    # Conclusion
    print(f"\n" + "="*70)
    print("CONCLUSION")
    print("="*70)
    
    if after_with_buyer > before_with_buyer:
        print(f"✓ CORRECTION RÉUSSIE: {after_with_buyer - before_with_buyer} acheteurs ajoutés")
        if after_with_buyer == len(after_orphan_rows):
            print("✓ Tous les orphelins ont maintenant un Acheteur_auto")
        else:
            remaining = len(after_orphan_rows) - after_with_buyer
            print(f"⚠ {remaining} orphelins sans acheteur (extraction impossible ou HTML incomplet)")
    else:
        print("✗ AUCUNE AMÉLIORATION - Tous les acheteurs restent introuvables")
    
    print("="*70)


if __name__ == '__main__':
    main()
