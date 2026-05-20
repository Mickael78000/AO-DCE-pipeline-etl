"""Tests pour les extracteurs HTML Version 2."""

from __future__ import annotations

from pathlib import Path

from ao_etl.sources import extract_from_html


def test_file(filepath: Path, expected: dict | None = None) -> dict:
    """Test l'extraction d'un fichier HTML."""
    print(f"\n{'='*70}")
    print(f"Test: {filepath.name}")
    print('='*70)
    
    html = filepath.read_text(encoding='utf-8')
    result = extract_from_html(filepath, html)
    
    print(f"\n📊 Source détectée: {result.source_type}")
    print(f"📄 Référence: {result.reference}")
    print(f"📝 Titre: {result.title[:80]}..." if len(result.title) > 80 else f"📝 Titre: {result.title}")
    print(f"🏢 Acheteur: {result.buyer}")
    print(f"📍 Localisation: {result.location}")
    print(f"⏰ Date limite: {result.deadline}")
    print(f"⏱️ Durée: {result.duration}")
    print(f"💰 Estimation: {result.estimation}")
    print(f"⚠️ Review needed: {result.review_needed}")
    
    print(f"\n📝 Extraction traces:")
    for note in result.extraction_notes[:6]:  # Limiter l'affichage
        print(f"    • {note}")
    
    # Vérifications
    if expected:
        print(f"\n✅ Vérifications:")
        for field, expected_value in expected.items():
            actual = getattr(result, field, "")
            if expected_value in actual or actual in expected_value:
                print(f"  ✓ {field}: '{actual[:50]}...' contient '{expected_value[:30]}...'")
            else:
                print(f"  ✗ {field}: attendu '{expected_value[:50]}...', obtenu '{actual[:50]}...'")
    
    return result.to_pipeline_dict()


def main():
    html_dir = Path('data/raw/html')
    
    # Test 1: PLACE (2997383-orgAcronyme-s2d.html)
    place_file = html_dir / '2997383?orgAcronyme=s2d.html'
    if place_file.exists():
        test_file(place_file, {
            'title': 'Prestations de tierce maintenance',
            'reference': 'B26-01107-LS',
            'buyer': 'CEA',  # Ne doit PAS être "Autres organismes"
        })
    else:
        print(f"❌ Fichier non trouvé: {place_file}")
    
    # Test 2: BOAMP (26-41049.html - DGFIP)
    boamp_file = html_dir / '26-41049.html'
    if boamp_file.exists():
        test_file(boamp_file, {
            'title': 'Assistance externe',
            'reference': 'DGFIP-DRS-2500077',
            'buyer': 'Direction Générale des Finances Publiques',  # Pas "Titre"
        })
    else:
        print(f"❌ Fichier non trouvé: {boamp_file}")
    
    # Test 3: Marchés Online (ao-9599071-1.html)
    mo_file = html_dir / 'ao-9599071-1.html'
    if mo_file.exists():
        test_file(mo_file, {
            'title': 'Prestations de support',
            'reference': 'MO-9599071',
            'buyer': 'Région Grand Est',  # Pas "Services d'administration générale"
            'location': '67',
        })
    else:
        print(f"❌ Fichier non trouvé: {mo_file}")
    
    # Test 4: France Marchés (13joue003107212026-2026-maintien-condition-operationnelle.html)
    fm_file = html_dir / '13joue003107212026-2026-maintien-condition-operationnelle.html'
    if fm_file.exists():
        test_file(fm_file, {
            'buyer': 'Centre Hospitalier',  # Pas "Organisme de droit public"
        })
    else:
        print(f"❌ Fichier non trouvé: {fm_file}")


if __name__ == '__main__':
    main()
