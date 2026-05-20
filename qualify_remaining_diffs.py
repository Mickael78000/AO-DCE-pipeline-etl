#!/usr/bin/env python3
"""Qualifie les divergences restantes après la Phase A.

Usage:
    python qualify_remaining_diffs.py reports/compare_phase_a/compare_details.json
"""
import json
import sys
from collections import Counter
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        path = Path("reports/compare_phase_a/compare_details.json")
    else:
        path = Path(sys.argv[1])

    if not path.exists():
        # Fallback dossier compare/
        path = Path("reports/compare/compare_details.json")
    if not path.exists():
        print(f"Pas trouvé: {sys.argv[1] if len(sys.argv)>1 else path}", file=sys.stderr)
        return 2

    d = json.load(open(path))
    print(f"Source: {path}  ({len(d)} fichiers)\n")

    # 1. Les 6 reference only_legacy → c'est quoi ?
    print("=" * 70)
    print("1. RÉFÉRENCES PERDUES (only_legacy) — à examiner avant bascule")
    print("=" * 70)
    refs_lost = []
    for x in d:
        for r in x['fields']:
            if r['field'] == 'reference' and r['status'] == 'only_legacy':
                refs_lost.append((x['file'], r['legacy']))
    if not refs_lost:
        print("Aucune. Bravo.")
    else:
        for f, lv in refs_lost:
            print(f"  • {f}")
            print(f"      legacy = {lv!r}")

    # 2. Pattern des diff sur buyer
    print()
    print("=" * 70)
    print("2. DIFF SUR BUYER — cosmétique ou pas ?")
    print("=" * 70)
    diff_buyer = []
    for x in d:
        for r in x['fields']:
            if r['field'] == 'buyer' and r['status'] == 'diff':
                diff_buyer.append((x['file'], r['legacy'], r['v2']))

    cosmetic = 0
    semantic = 0
    for f, lv, vv in diff_buyer:
        if lv is None or vv is None:
            semantic += 1
            continue
        # Heuristique cosmétique : seul le whitespace, ponctuation finale, ou entités HTML diffère
        norm = lambda s: (s.replace('&quot;','"').replace('&amp;','&')
                          .rstrip('.').strip().lower())
        if norm(lv) == norm(vv):
            cosmetic += 1
        else:
            semantic += 1
    print(f"  → {cosmetic} cosmétiques (acceptables)")
    print(f"  → {semantic} sémantiques (à inspecter)")
    print()
    print("  Échantillon sémantique (max 8) :")
    n = 0
    for f, lv, vv in diff_buyer:
        if lv is None or vv is None:
            print(f"  • {f}\n      L: {lv!r}\n      V: {vv!r}")
            n += 1
        else:
            norm = lambda s: (s.replace('&quot;','"').replace('&amp;','&')
                              .rstrip('.').strip().lower())
            if norm(lv) != norm(vv):
                print(f"  • {f}\n      L: {str(lv)[:90]}\n      V: {str(vv)[:90]}")
                n += 1
        if n >= 8:
            break

    # 3. Pattern des diff sur title
    print()
    print("=" * 70)
    print("3. DIFF SUR TITLE — cosmétique ou pas ?")
    print("=" * 70)
    diff_title = []
    for x in d:
        for r in x['fields']:
            if r['field'] == 'title' and r['status'] == 'diff':
                diff_title.append((x['file'], r['legacy'], r['v2']))

    cosmetic = 0
    semantic = 0
    for f, lv, vv in diff_title:
        if lv is None or vv is None:
            semantic += 1
            continue
        norm = lambda s: s.rstrip('.').strip().lower()
        if norm(lv) == norm(vv):
            cosmetic += 1
        else:
            semantic += 1
    print(f"  → {cosmetic} cosmétiques (acceptables)")
    print(f"  → {semantic} sémantiques (à inspecter)")
    print()
    print("  Échantillon sémantique (max 5) :")
    n = 0
    for f, lv, vv in diff_title:
        if lv is None or vv is None:
            print(f"  • {f}\n      L: {lv!r}\n      V: {vv!r}")
            n += 1
        else:
            norm = lambda s: s.rstrip('.').strip().lower()
            if norm(lv) != norm(vv):
                print(f"  • {f}\n      L: {str(lv)[:90]}\n      V: {str(vv)[:90]}")
                n += 1
        if n >= 5:
            break

    # 4. only_legacy résiduels sur duree_mois et location
    print()
    print("=" * 70)
    print("4. AUTRES PERTES RÉSIDUELLES (only_legacy)")
    print("=" * 70)
    for field in ['location', 'date_limite', 'estimation_eur', 'duree_mois']:
        losses = [(x['file'], r['legacy']) for x in d for r in x['fields']
                  if r['field']==field and r['status']=='only_legacy']
        if losses:
            print(f"\n  {field}:")
            for f, lv in losses[:5]:
                print(f"    • {f} → legacy={lv!r}")

    print()
    print("=" * 70)
    print("VERDICT : OK pour basculer en V2 si :")
    print(" - Les 'references perdues' (section 1) sont marginales / explicables")
    print(" - Les diff buyer/title sont majoritairement cosmétiques (section 2-3)")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
