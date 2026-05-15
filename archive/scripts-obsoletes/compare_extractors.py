#!/usr/bin/env python3
"""Script de comparaison legacy vs V2 pour validation de non-régression."""

import sys
import os
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ao_etl.sources import extract_for_source


def compare_file(filepath: Path):
    """Compare l'extraction legacy vs V2 pour un fichier."""
    print(f"\n{'='*70}")
    print(f"Fichier: {filepath.name}")
    print('='*70)
    
    # Legacy
    print("\n--- LEGACY ---")
    try:
        legacy = extract_for_source(filepath, version='legacy')
        print(f"  Source: {legacy.source_type}")
        print(f"  Référence: {legacy.reference}")
        print(f"  Titre: {legacy.title[:60]}..." if len(legacy.title) > 60 else f"  Titre: {legacy.title}")
        print(f"  Acheteur: {legacy.buyer}")
    except Exception as e:
        print(f"  ERREUR: {e}")
        legacy = None
    
    # V2
    print("\n--- V2 ---")
    try:
        v2 = extract_for_source(filepath, version='v2')
        print(f"  Source: {v2.source_type}")
        print(f"  Référence: {v2.reference}")
        print(f"  Titre: {v2.title[:60]}..." if len(v2.title) > 60 else f"  Titre: {v2.title}")
        print(f"  Acheteur: {v2.buyer}")
        print(f"  Location: {v2.location}")
        print(f"  Deadline: {v2.deadline}")
        print(f"  Duration: {v2.duration}")
        print(f"  Estimation: {v2.estimation}")
        print(f"  Review needed: {v2.review_needed}")
        print(f"  Notes: {len(v2.extraction_notes)} traces")
        for note in v2.extraction_notes[:3]:
            print(f"    • {note[:80]}..." if len(note) > 80 else f"    • {note}")
    except Exception as e:
        print(f"  ERREUR: {e}")
        import traceback
        traceback.print_exc()
        v2 = None
    
    # Comparaison
    if legacy and v2:
        print("\n--- COMPARAISON ---")
        
        # Titre
        if legacy.title == v2.title:
            print(f"  ✓ Titre identique")
        elif not v2.title and legacy.title:
            print(f"  ⚠ Titre V2 vide (legacy: '{legacy.title[:40]}...')")
        elif v2.title and not legacy.title:
            print(f"  ✓ Titre V2 trouvé (legacy vide)")
        else:
            print(f"  ≠ Titre différent")
            print(f"    Legacy: {legacy.title[:50]}...")
            print(f"    V2:     {v2.title[:50]}...")
        
        # Acheteur
        if legacy.buyer == v2.buyer:
            print(f"  ✓ Acheteur identique")
        elif not v2.buyer and legacy.buyer:
            print(f"  ⚠ Acheteur V2 vide (legacy: '{legacy.buyer[:40]}...')")
        elif v2.buyer and not legacy.buyer:
            print(f"  ✓ Acheteur V2 trouvé (legacy vide)")
        else:
            print(f"  ≠ Acheteur différent")
            print(f"    Legacy: {legacy.buyer[:50]}...")
            print(f"    V2:     {v2.buyer[:50]}...")
    
    return legacy, v2


def main():
    html_dir = Path('data/raw/html')
    
    # Fichiers de test prioritaires
    test_files = [
        "2997383?orgAcronyme=s2d.html",  # PLACE
        "26-41049.html",  # BOAMP DGFIP
        "13joue003107212026-2026-maintien-condition-operationnelle.html",  # France Marchés
        "36parisien1157695-2026-infogerance-systeme-information.html",  # France Marchés
        "ao-9599071-1.html",  # Marchés Online
    ]
    
    print(f"{'='*70}")
    print("COMPARAISON EXTRACTEURS LEGACY vs V2")
    print(f"{'='*70}")
    
    for filename in test_files:
        filepath = html_dir / filename
        if filepath.exists():
            compare_file(filepath)
        else:
            print(f"\n⚠ Fichier non trouvé: {filepath}")
    
    print(f"\n{'='*70}")
    print("Comparaison terminée")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
