#!/usr/bin/env python3
"""
Rapport d'audit ETL pour AO-pipeline-v2-clean.csv
Auditeur: Senior ETL Data Auditor
Date: 2026-05-11
"""

import csv
import json
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

def run_audit():
    print("=" * 100)
    print("RAPPORT D'AUDIT ETL - AO-DCE Pipeline v2")
    print("Fichier audité: AO-pipeline-v2-clean.csv")
    print("Date d'audit:", datetime.now().isoformat())
    print("Auditeur: Senior ETL Data Auditor")
    print("=" * 100)
    
    # 1. Chargement des données
    csv_path = Path('AO-pipeline-v2-clean.csv')
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames
    
    html_dir = Path('html_ao')
    html_files = set(f.name for f in html_dir.glob('*.html'))
    
    print(f"\n📊 DONNÉES DE BASE")
    print(f"   Fichiers HTML dans html_ao/: {len(html_files)}")
    print(f"   Lignes CSV (hors en-tête): {len(rows)}")
    print(f"   Colonnes CSV: {len(fieldnames)}")
    
    # 2. Vérification correspondance CSV ↔ HTML
    print(f"\n🔍 VÉRIFICATION 1: Correspondance CSV ↔ HTML")
    match_sources = [r.get('match_source', '') for r in rows if r.get('match_source')]
    unique_sources = set(match_sources)
    
    print(f"   Match sources uniques: {len(unique_sources)}")
    
    # Vérifier que tous les match_source existent
    invalid_match = []
    for row in rows:
        src = row.get('match_source', '')
        if src and src not in html_files:
            invalid_match.append({
                'ref': row.get('Référence', 'N/A'),
                'match_source': src,
                'line': rows.index(row) + 2
            })
    
    if invalid_match:
        print(f"   ✗ Match sources invalides: {len(invalid_match)}")
        for inv in invalid_match[:5]:
            print(f"     Ligne {inv['line']}: {inv['ref']} -> {inv['match_source']}")
    else:
        print(f"   ✓ Tous les match_source correspondent à des fichiers HTML existants")
    
    # Vérifier doublons match_source
    source_counts = Counter(match_sources)
    dups = {k: v for k, v in source_counts.items() if v > 1}
    if dups:
        print(f"   ✗ Doublons match_source: {dups}")
    else:
        print(f"   ✓ Pas de doublon match_source (1 ligne = 1 fichier HTML)")
    
    # Vérifier HTML non utilisés
    unused_html = html_files - unique_sources
    if unused_html:
        print(f"   ⚠ Fichiers HTML sans ligne CSV: {len(unused_html)}")
        for h in sorted(unused_html)[:5]:
            print(f"     - {h}")
    else:
        print(f"   ✓ Tous les fichiers HTML ont une ligne CSV correspondante")
    
    # 3. Analyse des références
    print(f"\n🔍 VÉRIFICATION 2: Unicité des références")
    refs = [r.get('Référence', '') for r in rows]
    ref_counts = Counter(refs)
    duplicates = {k: v for k, v in ref_counts.items() if v > 1}
    
    print(f"   Total références: {len(refs)}")
    print(f"   Références uniques: {len(set(refs))}")
    
    if duplicates:
        print(f"   ✗ Doublons de références détectés:")
        for ref, count in duplicates.items():
            print(f"     - {ref}: {count} occurrences")
    else:
        print(f"   ✓ Toutes les références sont uniques")
    
    # 4. Analyse match_status
    print(f"\n🔍 VÉRIFICATION 3: Classification match_status")
    statuses = Counter(r.get('match_status', 'unknown') for r in rows)
    for status, count in statuses.items():
        pct = count / len(rows) * 100
        print(f"   {status}: {count} ({pct:.1f}%)")
    
    # 5. Vérification champs critiques
    print(f"\n🔍 VÉRIFICATION 4: Champs critiques")
    
    # Référence vide
    empty_ref = [r for r in rows if not r.get('Référence') or r['Référence'] == '-']
    print(f"   Références vides: {len(empty_ref)}")
    
    # Title vide
    empty_title = [r for r in rows if not r.get('Intitulé synthétique') or r['Intitulé synthétique'] == '-']
    print(f"   Titres vides: {len(empty_title)}")
    if empty_title:
        for r in empty_title[:3]:
            print(f"     - {r.get('Référence', 'N/A')}: {r.get('Intitulé synthétique', 'VIDE')[:40]}")
    
    # Acheteur_auto
    empty_buyer = [r for r in rows if not r.get('Acheteur_auto') or r['Acheteur_auto'] == '-']
    print(f"   Acheteur_auto vide: {len(empty_buyer)}/{len(rows)} ({len(empty_buyer)/len(rows)*100:.1f}%)")
    
    # source_type vide
    empty_source = [r for r in rows if not r.get('source_type') or r['source_type'] == '-']
    print(f"   source_type vide: {len(empty_source)}")
    
    # 6. Analyse Marchés Online spécifique
    print(f"\n🔍 VÉRIFICATION 5: Cas Marchés Online (MO-*)")
    mo_rows = [r for r in rows if r.get('Référence', '').startswith('MO-')]
    print(f"   Total lignes MO: {len(mo_rows)}")
    
    # Vérifier cohérence référence vs match_source
    mo_issues = []
    for row in mo_rows:
        ref = row.get('Référence', '')
        match_src = row.get('match_source', '')
        
        # Extraction ID attendu depuis match_source (ao-XXXXX-Y.html -> MO-XXXXX)
        if match_src.startswith('ao-'):
            parts = match_src.replace('ao-', '').split('-')
            expected_ref = f"MO-{parts[0]}" if parts else None
            
            if expected_ref and ref != expected_ref:
                mo_issues.append({
                    'ref': ref,
                    'match_source': match_src,
                    'expected': expected_ref,
                    'line': rows.index(row) + 2
                })
    
    if mo_issues:
        print(f"   ✗ Incohérences MO détectées: {len(mo_issues)}")
        for issue in mo_issues[:5]:
            print(f"     Ligne {issue['line']}: {issue['ref']} (attendu: {issue['expected']}) <- {issue['match_source']}")
    else:
        print(f"   ✓ Toutes les références MO sont cohérentes avec les match_source")
    
    # 7. Détail des Acheteur_auto vides
    print(f"\n📋 DÉTAIL: Lignes sans Acheteur_auto ({len(empty_buyer)})")
    for row in empty_buyer:
        ref = row.get('Référence', 'N/A')[:30]
        match_src = row.get('match_source', 'N/A')[:25]
        status = row.get('match_status', '?')
        source_type = row.get('source_type', '?')
        print(f"   - {ref:<30} | {match_src:<25} | {status} | {source_type}")
    
    # 8. Récapitulatif
    print(f"\n" + "=" * 100)
    print("RÉCAPITULATIF DE L'AUDIT")
    print("=" * 100)
    
    issues = []
    
    if invalid_match:
        issues.append(f"{len(invalid_match)} match_source invalides")
    if dups:
        issues.append(f"{len(dups)} doublons match_source")
    if unused_html:
        issues.append(f"{len(unused_html)} fichiers HTML non utilisés")
    if duplicates:
        issues.append(f"{len(duplicates)} doublons de références")
    if empty_ref:
        issues.append(f"{len(empty_ref)} références vides")
    if empty_buyer:
        issues.append(f"{len(empty_buyer)} acheteurs non extraits")
    
    if issues:
        print(f"\n⚠️  ANOMALIES DÉTECTÉES:")
        for issue in issues:
            print(f"   - {issue}")
    else:
        print(f"\n✅ AUCUNE ANOMALIE MAJEURE DÉTECTÉE")
    
    # Conclusion
    print(f"\n🎯 CONCLUSION:")
    if len(rows) == len(html_files) and not invalid_match and not dups and not duplicates:
        if len(empty_buyer) <= 2:  # 2-3 acheteurs vides est acceptable
            print(f"   FICHIER PARTIELLEMENT COHÉRENT")
            print(f"   Structure: ✓ Correcte (50 lignes = 50 fichiers)")
            print(f"   Références: ✓ Uniques")
            print(f"   Acheteurs: ⚠ {len(empty_buyer)} non extraits (acceptable)")
        else:
            print(f"   FICHIER NON COHÉRENT - Trop d'acheteurs manquants")
    else:
        print(f"   FICHIER NON COHÉRENT - Problèmes structurels détectés")
    
    print("\n" + "=" * 100)

if __name__ == '__main__':
    run_audit()
