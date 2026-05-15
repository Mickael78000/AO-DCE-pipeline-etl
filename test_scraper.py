#!/usr/bin/env python3
"""Test du scraper URL."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ao_etl.scraper.url_scraper import scrape_url, enrich_row_with_url_content, clear_cache

def test_scraper():
    """Test le scraping d'une URL réelle."""
    
    print("=" * 60)
    print("TEST DU SCRAPER URL")
    print("=" * 60)
    print()
    
    # Test avec une URL France Marchés
    test_url = "https://www.francemarches.com/appel-offre/pp1e2-3001-6300-2026031-s-renouvellement-maintenance-des-solutions-dedrm"
    
    print(f"URL de test: {test_url}")
    print()
    
    # Vider le cache pour avoir un test propre
    clear_cache()
    
    # Test 1: Scraping direct
    print("Test 1: Scraping direct...")
    html_content = scrape_url(test_url, timeout=15)
    
    if html_content:
        print(f"✓ Scraping réussi: {len(html_content)} caractères")
        
        # Vérifier qu'on a du contenu pertinent
        if "Conseil" in html_content or " maintenance" in html_content or "solution" in html_content.lower():
            print("✓ Contenu pertinent trouvé (mots-clés présents)")
        else:
            print("⚠ Contenu peut-être non pertinent")
        
        # Afficher un extrait
        print()
        print("Extrait du contenu:")
        excerpt = html_content[:500].replace("\n", " ")
        print(f"  {excerpt}...")
    else:
        print("❌ Scraping échoué")
        return
    
    print()
    print("=" * 60)
    print("Test 2: Enrichissement de row")
    print("=" * 60)
    print()
    
    # Test avec une row
    row = {
        "Référence": "TEST-001",
        "URL source HTTPS": test_url,
        "Estimation_auto": "-",
        "Date_limite_auto": "-",
        "Localisation_auto": "-",
    }
    
    print("Row avant enrichissement:")
    for k, v in row.items():
        print(f"  {k}: {v}")
    
    enriched = enrich_row_with_url_content(row)
    
    print()
    print("Row après enrichissement:")
    for k, v in enriched.items():
        if k.startswith("_"):
            if k == "_url_scraped_content":
                content = v[:200] + "..." if len(v) > 200 else v
                print(f"  {k}: {content[:100]}... (longueur: {len(v)})")
            else:
                print(f"  {k}: {v}")
        else:
            print(f"  {k}: {v}")
    
    if enriched.get("_url_scraped_content"):
        print()
        print("✅ Row enrichie avec succès!")
        print(f"   Longueur du contenu: {len(enriched['_url_scraped_content'])} caractères")
    else:
        print()
        print("❌ Pas de contenu scrappé ajouté")

if __name__ == "__main__":
    try:
        test_scraper()
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
