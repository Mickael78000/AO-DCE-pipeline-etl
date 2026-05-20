"""Tests unitaires pour la Phase A-bis — 4 correctifs post-Phase A.

Couvre:
  A-bis 1 : buyer JOUE/BOAMP — plus jamais "Opérateur"
  A-bis 2 : titre JOUE non tronqué sur la première virgule
  A-bis 3 : référence PLACE_NUMERIC = référence métier
  A-bis 4 : apostrophes typographiques normalisées
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ao_etl.sources.router import extract_from_html
from ao_etl.sources.validation import normalize_text

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HTML_DIR = Path(__file__).parent.parent.parent / "data" / "raw" / "html"

BUYER_BLACKLIST = {
    "opérateur",
    "opérateur économique",
    "nom officiel",
    "adresse",
    "1.1",
    "i.1",
    "pouvoir adjudicateur",
    "autorité contractante",
    "entité adjudicatrice",
}


def _extract(filename: str):
    fpath = HTML_DIR / filename
    if not fpath.exists():
        pytest.skip(f"Fichier HTML absent: {filename}")
    html = fpath.read_text()
    return extract_from_html(fpath, html)


# ===========================================================================
# A-bis 1 — Buyer JOUE : valeur réelle, pas "Opérateur"
# ===========================================================================

class TestBuyerNotOperateur:
    """Le buyer extrait ne doit jamais être dans la liste noire de labels."""

    def test_joue_buyer_not_in_blacklist(self):
        result = _extract("13joue002708922026-2026-fourniture-prestation-service.html")
        assert result.buyer.casefold() not in BUYER_BLACKLIST, (
            f"buyer={result.buyer!r} est dans la liste noire"
        )

    def test_boamp_buyer_not_in_blacklist(self):
        result = _extract("3boamp2640079-2026-mise-disposition-adaptation.html")
        assert result.buyer.casefold() not in BUYER_BLACKLIST, (
            f"buyer={result.buyer!r} est dans la liste noire"
        )

    def test_joue_buyer_exact_unicancer(self):
        """UNICANCER ACHATS doit être le buyer exact extrait."""
        result = _extract("13joue002708922026-2026-fourniture-prestation-service.html")
        assert result.buyer == "UNICANCER ACHATS"

    def test_boamp_buyer_exact_has(self):
        """Haute Autorité de Santé doit être le buyer exact extrait."""
        result = _extract("3boamp2640079-2026-mise-disposition-adaptation.html")
        assert result.buyer == "Haute Autorité de Santé"

    def test_no_operateur_across_all_html(self):
        """Zéro occurrence de buyer='Opérateur' dans tous les fichiers HTML du répertoire."""
        failures = []
        for fpath in sorted(HTML_DIR.glob("*.html")):
            html = fpath.read_text()
            result = extract_from_html(fpath, html)
            if result.buyer == "Opérateur":
                failures.append(fpath.name)
        assert failures == [], (
            f"{len(failures)} fichier(s) ont encore buyer='Opérateur': {failures}"
        )


# ===========================================================================
# A-bis 2 — Titre JOUE non tronqué sur la première virgule
# ===========================================================================

class TestTitleNotTruncated:
    """Le titre ne doit pas s'arrêter à la première virgule."""

    def test_title_longer_than_50_chars(self):
        result = _extract(
            "13joue002946202026-2026-continuite-exploitation-hebergement"
            "?q=h%C3%A9bergement web.html"
        )
        assert len(result.title) > 50, (
            f"Titre trop court ({len(result.title)} chars): {result.title!r}"
        )

    def test_title_contains_developpement(self):
        result = _extract(
            "13joue002946202026-2026-continuite-exploitation-hebergement"
            "?q=h%C3%A9bergement web.html"
        )
        assert "développement" in result.title.lower(), (
            f"Mot 'développement' absent du titre: {result.title!r}"
        )

    def test_title_contains_exploitation(self):
        result = _extract(
            "13joue002946202026-2026-continuite-exploitation-hebergement"
            "?q=h%C3%A9bergement web.html"
        )
        assert "exploitation" in result.title.lower(), (
            f"Mot 'exploitation' absent du titre: {result.title!r}"
        )


# ===========================================================================
# A-bis 3 — Référence PLACE_NUMERIC = référence métier
# ===========================================================================

class TestPlaceNumericReference:
    """La référence extraite par V2 doit correspondre à la référence métier du legacy."""

    @pytest.mark.parametrize("filename,expected_ref", [
        ("2956468?orgAcronyme=g7h.html",  "Shom_26AC07"),
        ("2986378?orgAcronyme=f2h.html",  "A2026-018"),
        ("2987833?orgAcronyme=f2h.html",  "2026-005"),
        ("2990888?orgAcronyme=d3f.html",  "26_AMOE_AST"),
        ("2992873?orgAcronyme=d4t.html",  "AOO_2026-02"),
        ("2997383?orgAcronyme=s2d.html",  "B26-01107-LS"),
        ("2998043?orgAcronyme=f2h.html",  "RFI_CRM_2026-02"),
    ])
    def test_reference_matches_legacy(self, filename: str, expected_ref: str):
        result = _extract(filename)
        assert result.reference == expected_ref, (
            f"Pour {filename}: attendu {expected_ref!r}, obtenu {result.reference!r}"
        )


# ===========================================================================
# A-bis 4 — Apostrophes typographiques normalisées
# ===========================================================================

class TestTypographicApostrophes:
    """Les apostrophes U+2019 doivent être converties en U+0027 dans normalize_text."""

    def test_normalize_curly_apostrophe(self):
        assert normalize_text("l\u2019exploitation") == "l'exploitation"

    def test_normalize_opening_apostrophe(self):
        assert normalize_text("l\u2018exploitation") == "l'exploitation"

    def test_normalize_curly_quotes(self):
        assert normalize_text("\u201cvaleur\u201d") == '"valeur"'

    def test_title_with_apostrophes_normalized_in_extraction(self):
        """Un titre extrait d'un fichier JOUE doit contenir l'apostrophe droite."""
        result = _extract(
            "13joue002946202026-2026-continuite-exploitation-hebergement"
            "?q=h%C3%A9bergement web.html"
        )
        assert "\u2019" not in result.title, (
            f"Apostrophe typographique U+2019 présente dans le titre: {result.title!r}"
        )
        assert "l'exploitation" in result.title, (
            f"Attendu \"l'exploitation\" (apostrophe droite) dans: {result.title!r}"
        )

    def test_buyer_with_apostrophes_normalized(self):
        """Un buyer extrait d'un fichier BOAMP ne doit pas contenir U+2019."""
        result = _extract("3boamp2640079-2026-mise-disposition-adaptation.html")
        assert "\u2019" not in result.buyer, (
            f"Apostrophe typographique U+2019 présente dans buyer: {result.buyer!r}"
        )
