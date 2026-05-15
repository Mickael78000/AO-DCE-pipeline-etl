"""Script de test pour vérifier les corrections des extracteurs."""

from pathlib import Path
from bs4 import BeautifulSoup
from ao_etl.sources.place_numeric import PlaceNumericExtractor
from ao_etl.sources.marches_online import MarchesOnlineExtractor

def test_place_file(filepath: Path) -> dict:
    """Test l'extraction d'un fichier PLACE."""
    print(f"\n{'='*60}")
    print(f"Test PLACE: {filepath.name}")
    print('='*60)
    
    content = filepath.read_text(encoding='utf-8')
    soup = BeautifulSoup(content, 'html.parser')
    
    extractor = PlaceNumericExtractor(filepath, soup, content)
    if not extractor.can_extract():
        print("❌ Extracteur ne peut pas traiter ce fichier")
        return None
    
    data = extractor.extract()
    
    print(f"\n📊 Résultat:")
    print(f"  Titre: {data.title[:80]}..." if len(data.title) > 80 else f"  Titre: {data.title}")
    print(f"  Référence: {data.reference}")
    print(f"  Acheteur: {data.buyer}")
    print(f"  Localisation: {data.location}")
    print(f"  Date limite: {data.date_limite}")
    print(f"  Status: {data.status.name}")
    
    print(f"\n📝 Extraction notes:")
    for note in data.extraction_notes[-5:]:  # Dernières 5 notes
        print(f"    - {note}")
    
    return {
        'title': data.title,
        'reference': data.reference,
        'buyer': data.buyer,
        'location': data.location,
        'date_limite': data.date_limite,
        'status': data.status.name
    }


def test_marches_online_file(filepath: Path) -> dict:
    """Test l'extraction d'un fichier Marchés Online."""
    print(f"\n{'='*60}")
    print(f"Test Marchés Online: {filepath.name}")
    print('='*60)
    
    content = filepath.read_text(encoding='utf-8')
    soup = BeautifulSoup(content, 'html.parser')
    
    extractor = MarchesOnlineExtractor(filepath, soup, content)
    if not extractor.can_extract():
        print("❌ Extracteur ne peut pas traiter ce fichier")
        return None
    
    data = extractor.extract()
    
    print(f"\n📊 Résultat:")
    print(f"  Titre: {data.title[:80]}..." if len(data.title) > 80 else f"  Titre: {data.title}")
    print(f"  Référence: {data.reference}")
    print(f"  Acheteur: {data.buyer}")
    print(f"  Localisation: {data.location}")
    print(f"  Date limite: {data.date_limite}")
    print(f"  Status: {data.status.name}")
    
    print(f"\n📝 Extraction notes:")
    for note in data.extraction_notes[-5:]:  # Dernières 5 notes
        print(f"    - {note}")
    
    return {
        'title': data.title,
        'reference': data.reference,
        'buyer': data.buyer,
        'location': data.location,
        'date_limite': data.date_limite,
        'status': data.status.name
    }


def main():
    html_dir = Path('data/raw/html')
    
    # Test PLACE - B26-01107-LS
    place_file = html_dir / '2997383?orgAcronyme=s2d.html'
    if place_file.exists():
        place_result = test_place_file(place_file)
        
        # Vérifications
        if place_result:
            print("\n✅ Vérifications PLACE:")
            
            # Le titre ne doit PAS être "Détail de la consultation"
            if place_result['title'] and 'Détail de la consultation' not in place_result['title']:
                print("  ✓ Titre: Pas 'Détail de la consultation'")
            else:
                print("  ✗ Titre: Toujours générique ou vide!")
            
            # L'acheteur ne doit PAS être une catégorie
            if place_result['buyer'] and place_result['buyer'] not in ['Autres organismes', '']:
                print(f"  ✓ Acheteur: {place_result['buyer'][:50]}")
            else:
                print(f"  ✗ Acheteur: Toujours catégorie ou vide: '{place_result['buyer']}'")
    else:
        print(f"❌ Fichier non trouvé: {place_file}")
    
    # Test Marchés Online - MO-9599071
    mo_file = html_dir / 'ao-9599071-1.html'
    if mo_file.exists():
        mo_result = test_marches_online_file(mo_file)
        
        # Vérifications
        if mo_result:
            print("\n✅ Vérifications Marchés Online:")
            
            # Le titre doit être long (pas juste "Prestations de support")
            if mo_result['title'] and len(mo_result['title']) > 50:
                print(f"  ✓ Titre: Long ({len(mo_result['title'])} caractères)")
            else:
                print(f"  ✗ Titre: Trop court ou vide: '{mo_result['title'][:50]}...'")
            
            # L'acheteur doit être "Région Grand Est" pas une catégorie
            if mo_result['buyer'] and mo_result['buyer'] == 'Région Grand Est':
                print(f"  ✓ Acheteur correct: {mo_result['buyer']}")
            elif mo_result['buyer'] and 'Services' not in mo_result['buyer']:
                print(f"  ✓ Acheteur amélioré: {mo_result['buyer'][:50]}")
            else:
                print(f"  ✗ Acheteur: Toujours catégorie: '{mo_result['buyer']}'")
            
            # La localisation doit contenir "67" ou "REGION"
            if mo_result['location'] and ('67' in mo_result['location'] or 'REGION' in mo_result['location']):
                print(f"  ✓ Localisation: {mo_result['location']}")
            else:
                print(f"  ✗ Localisation: Manquante ou incorrecte: '{mo_result['location']}'")
    else:
        print(f"❌ Fichier non trouvé: {mo_file}")


if __name__ == '__main__':
    main()
