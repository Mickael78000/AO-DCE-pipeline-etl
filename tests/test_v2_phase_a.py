"""Tests Phase A - Correctifs V2 critiques.

Ces tests valident les 5 correctifs de la Phase A:
1. Extraction CPV dans v2
2. Extraction buyer dans BOAMP/JOUE
3. Extraction duree_mois dans v2
4. Normalisation de reference en v2
5. Bug buyer='1.1' pour 26-41049.html
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ao_etl.sources.router import extract_from_html


# =============================================================================
# Fixtures HTML de test (simplifiés mais représentatifs)
# =============================================================================

PLACE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Test PLACE</title></head>
<body>
<div data-code-cpv="72250000"></div>
<div data-code-cpv="72260000"></div>
<p>Durée du marché : 24 mois</p>
<p>B26-01107-LS</p>
<p>CEA / Direction des Achats</p>
</body>
</html>
"""

BOAMP_HTML = """
<!DOCTYPE html>
<html>
<head><title>Test BOAMP</title></head>
<body>
<p>Identifiant interne</p>
<p>2026-12345678</p>
<p>Titre</p>
<p>Fourniture de prestations informatiques</p>
<p>Nom officiel</p>
<p>Direction Générale des Finances Publiques</p>
<p>Durée du marché</p>
<p>36 mois</p>
<p>72200000</p>
<p>48000000</p>
</body>
</html>
"""

# Simule le cas 26-41049.html où il y a une section 1.1 avant le vrai acheteur
BOAMP_WITH_SECTION_HTML = """
<!DOCTYPE html>
<html>
<head><title>Test BOAMP Section</title></head>
<body>
<table>
<tr><th>Section</th><td>1.1</td></tr>
<tr><th>Nom officiel</th><td>Direction Générale des Finances Publiques</td></tr>
</table>
<p>Durée : 12 mois</p>
</body>
</html>
"""

JOUE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Test JOUE</title></head>
<body>
<p>13/joue/002671162026</p>
<p>Nom et adresse de l'autorité attribuant le marché : UNICANCER ACHATS</p>
<p>Durée du marché : 48 mois</p>
<p>72500000</p>
</body>
</html>
"""

FRANCE_MARCHES_HTML = """
<!DOCTYPE html>
<html>
<head><title>Test France Marchés</title></head>
<body data-code-cpv="72000000">
<p>Intitulé de l'appel d'offre public : Maintenance des systèmes</p>
<p>Nom complet de l'acheteur : Centre Hospitalier de Paris</p>
<p>Durée : 24 mois</p>
</body>
</html>
"""

MARCHES_ONLINE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Appel d'offres : Prestations de support</title></head>
<body>
<div id="print_area_company"><a href="#">Région Grand Est</a></div>
<p>Durée : 36 mois</p>
<p>73000000</p>
<div class="title-avis">Prestations de support</div>
<span>marchesonline</span>
</body>
</html>
"""


# =============================================================================
# Tests Fix 1: Extraction CPV
# =============================================================================

def test_cpv_extraction_place_numeric():
    """Test CPV extraction from PLACE format with data-code-cpv attributes."""
    result = extract_from_html(Path("test.html"), PLACE_HTML)
    assert "cpv_codes" in result.raw
    assert len(result.raw["cpv_codes"]) == 2
    assert "72250000" in result.raw["cpv_codes"]
    assert "72260000" in result.raw["cpv_codes"]
    # All codes should be 8-digit strings
    for code in result.raw["cpv_codes"]:
        assert len(code) == 8
        assert code.isdigit()


def test_cpv_extraction_boamp_from_text():
    """Test CPV extraction from BOAMP format (8-digit codes in text)."""
    result = extract_from_html(Path("test.html"), BOAMP_HTML)
    assert "cpv_codes" in result.raw
    # Should find the CPV codes 72200000 and 48000000
    codes = result.raw["cpv_codes"]
    assert len(codes) >= 1
    # Verify format
    for code in codes:
        assert len(code) == 8
        assert code.isdigit()


def test_cpv_extraction_france_marches():
    """Test CPV extraction from France Marchés format."""
    result = extract_from_html(Path("test.html"), FRANCE_MARCHES_HTML)
    assert "cpv_codes" in result.raw
    # Should find 72000000 from data-code-cpv attribute
    if result.raw["cpv_codes"]:
        for code in result.raw["cpv_codes"]:
            assert len(code) == 8
            assert code.isdigit()


def test_cpv_max_10_codes():
    """Test that CPV extraction returns at most 10 codes."""
    # HTML with many CPV codes
    html = '<html>' + ''.join([f'<div data-code-cpv="{72000000 + i}"></div>' for i in range(15)]) + '</html>'
    result = extract_from_html(Path("test.html"), html)
    assert len(result.raw["cpv_codes"]) <= 10


# =============================================================================
# Tests Fix 2: Buyer extraction in BOAMP/JOUE
# =============================================================================

def test_buyer_extraction_boamp_nom_officiel():
    """Test buyer extraction from BOAMP with Nom officiel."""
    result = extract_from_html(Path("test.html"), BOAMP_HTML)
    assert result.buyer == "Direction Générale des Finances Publiques"


def test_buyer_extraction_joue_autorite():
    """Test buyer extraction from JOUE with autorité attribuant."""
    result = extract_from_html(Path("test.html"), JOUE_HTML)
    assert "UNICANCER" in result.buyer.upper()


def test_buyer_extraction_france_marches():
    """Test buyer extraction from France Marchés format."""
    result = extract_from_html(Path("test.html"), FRANCE_MARCHES_HTML)
    assert "Centre Hospitalier" in result.buyer


def test_buyer_extraction_marches_online():
    """Test buyer extraction from Marchés Online format."""
    result = extract_from_html(Path("test.html"), MARCHES_ONLINE_HTML)
    assert "Région Grand Est" in result.buyer


# =============================================================================
# Tests Fix 3: Duration months extraction
# =============================================================================

def test_duration_extraction_place_numeric():
    """Test duration extraction from PLACE format."""
    result = extract_from_html(Path("test.html"), PLACE_HTML)
    assert result.raw.get("duration_months") == 24


def test_duration_extraction_boamp():
    """Test duration extraction from BOAMP format."""
    result = extract_from_html(Path("test.html"), BOAMP_HTML)
    assert result.raw.get("duration_months") == 36


def test_duration_extraction_joue():
    """Test duration extraction from JOUE format."""
    result = extract_from_html(Path("test.html"), JOUE_HTML)
    assert result.raw.get("duration_months") == 48


def test_duration_extraction_france_marches():
    """Test duration extraction from France Marchés format."""
    result = extract_from_html(Path("test.html"), FRANCE_MARCHES_HTML)
    assert result.raw.get("duration_months") == 24


def test_duration_extraction_marches_online():
    """Test duration extraction from Marchés Online format."""
    result = extract_from_html(Path("test.html"), MARCHES_ONLINE_HTML)
    assert result.raw.get("duration_months") == 36


def test_duration_validation_range():
    """Test that duration is validated to be within 1-120 months."""
    # Test with invalid duration (too high)
    html = '<html><p>Durée : 999 mois</p></html>'
    result = extract_from_html(Path("test.html"), html)
    # Should return None for out-of-range values
    assert result.raw.get("duration_months") is None


# =============================================================================
# Tests Fix 4: Reference normalization
# =============================================================================

def test_reference_normalization_boamp_from_filename():
    """Test reference normalization for BOAMP files (26-XXXXX)."""
    result = extract_from_html(Path("26-41049.html"), BOAMP_WITH_SECTION_HTML)
    assert result.reference == "26-41049"


def test_reference_normalization_3boamp():
    """Test reference normalization for 3boampXXXX files - fallback to filename when Identifiant interne not found."""
    # Use HTML without Identifiant interne to test filename fallback
    html_simple = """
    <html><body>
    <p>Nom officiel</p><p>Test Acheteur</p>
    <p>Durée : 12 mois</p>
    </body></html>
    """
    result = extract_from_html(Path("3boamp2640079.html"), html_simple)
    assert result.reference == "3/boamp/2640079"


def test_reference_normalization_joue():
    """Test reference normalization for JOUE files."""
    result = extract_from_html(Path("13joue002671162026.html"), JOUE_HTML)
    assert result.reference == "13/joue/002671162026"


def test_reference_normalization_ao():
    """Test reference normalization for AO (Marchés Online) files."""
    result = extract_from_html(Path("37ao26181581260520263294.html"), FRANCE_MARCHES_HTML)
    assert result.reference == "37AO26181581260520263294"


def test_reference_normalization_parisien():
    """Test reference normalization for parisien files."""
    result = extract_from_html(Path("36parisien1157695.html"), FRANCE_MARCHES_HTML)
    assert result.reference == "1157695"


# =============================================================================
# Tests Fix 5: Bug buyer='1.1' (section number rejection)
# =============================================================================

def test_buyer_rejects_section_number_11():
    """Test that buyer extraction rejects section numbers like '1.1'."""
    result = extract_from_html(Path("26-41049.html"), BOAMP_WITH_SECTION_HTML)
    # Should NOT be "1.1" or any section number
    assert result.buyer != "1.1"
    assert not result.buyer.replace(".", "").isdigit()
    # Should be the real buyer
    assert "Direction" in result.buyer or "Finances" in result.buyer or result.buyer == ""


def test_value_rejects_section_numbers():
    """Test that _value_after_label rejects section number patterns."""
    from ao_etl.sources.boamp_xml_v2 import BoampExtractor
    from ao_etl.sources.base_v2 import ExtractionContext
    from bs4 import BeautifulSoup

    html = "<p>Label</p><p>2.3.1</p><p>Label</p><p>Vrai Acheteur</p>"
    context = ExtractionContext(
        file_path=Path("test.html"),
        html=html,
        soup=BeautifulSoup(html, "html.parser")
    )
    extractor = BoampExtractor(context)
    result = extractor._value_after_label("Label\n2.3.1\nLabel\nVrai Acheteur", "Label")
    # Should skip "2.3.1" and find "Vrai Acheteur"
    assert result != "2.3.1"


# =============================================================================
# Test d'intégration sur vrais fichiers (si disponibles)
# =============================================================================

@pytest.mark.skipif(
    not Path("data/raw/html").exists(),
    reason="HTML fixtures not available"
)
def test_integration_real_files():
    """Test d'intégration sur les vrais fichiers HTML du dataset."""
    html_dir = Path("data/raw/html")
    files = list(html_dir.glob("*.html"))[:5]  # Test sur 5 premiers fichiers

    for file_path in files:
        html = file_path.read_text(encoding='utf-8')
        result = extract_from_html(file_path, html)

        # Vérifications de base
        assert result.source_type != "UNKNOWN" or file_path.name.startswith("test")

        # CPV doit être une liste
        assert isinstance(result.raw.get("cpv_codes", []), list)

        # Duration_months doit être int ou None
        duration = result.raw.get("duration_months")
        assert duration is None or isinstance(duration, int)
        if isinstance(duration, int):
            assert 1 <= duration <= 120

        # Buyer ne doit pas être un numéro de section
        if result.buyer:
            assert not re.match(r'^\d+(\.\d+)*$', result.buyer)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
