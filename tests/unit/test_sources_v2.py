"""Tests unitaires pour les sources V2 - validation et scoring."""

import pytest
from ao_etl.sources.validation_v2 import (
    normalize_text,
    is_valid_title,
    is_valid_buyer,
    score_title,
    score_buyer,
    pick_best_candidate,
    _TITLE_EXACT_BLACKLIST,
    _BUYER_EXACT_BLACKLIST,
)
from ao_etl.sources.base_v2 import FieldCandidate, ExtractionTrace


class TestNormalizeText:
    """Tests pour la normalisation de texte."""
    
    def test_basic_normalization(self):
        assert normalize_text("  Hello  World  ") == "Hello World"
    
    def test_unicode_spaces(self):
        assert normalize_text("Hello\xa0World") == "Hello World"
    
    def test_empty_and_none(self):
        assert normalize_text("") == ""
        assert normalize_text(None) == ""


class TestIsValidTitle:
    """Tests pour la validation des titres."""
    
    def test_rejects_empty(self):
        assert is_valid_title("") == (False, "empty")
        assert is_valid_title(None) == (False, "empty")
    
    def test_rejects_too_short(self):
        assert is_valid_title("AB") == (False, "too_short")
        assert is_valid_title("Short") == (False, "too_short")  # < 12 chars
    
    def test_rejects_generic_titles(self):
        for bad in ["Titre", "Détail de la consultation", "Accord", "TMA"]:
            is_valid, reason = is_valid_title(bad)
            assert not is_valid, f"'{bad}' should be rejected"
            assert reason == "generic_exact_title"
    
    def test_accepts_valid_titles(self):
        valid = [
            "Prestations de tierce maintenance applicative",
            "Assistance externe pour la conduite de consultations",
            "Infogérance du système d'information",
        ]
        for title in valid:
            is_valid, reason = is_valid_title(title)
            assert is_valid, f"'{title}' should be accepted, got reason={reason}"


class TestIsValidBuyer:
    """Tests pour la validation des acheteurs."""
    
    def test_rejects_empty_and_url(self):
        assert is_valid_buyer("") == (False, "empty")
        assert is_valid_buyer("https://example.com") == (False, "url")
        assert is_valid_buyer("www.example.com") == (False, "url")
    
    def test_rejects_generic_buyers(self):
        for bad in _BUYER_EXACT_BLACKLIST:
            is_valid, reason = is_valid_buyer(bad)
            assert not is_valid, f"'{bad}' should be rejected"
            assert reason in ["generic_exact_buyer", "generic_contains_buyer", "url"]
    
    def test_rejects_contains_blacklist(self):
        bad_buyers = [
            "Organisation qui fournit des informations complémentaires",
            "Organisation chargée des procédures de recours",
        ]
        for buyer in bad_buyers:
            is_valid, reason = is_valid_buyer(buyer)
            assert not is_valid, f"'{buyer}' should be rejected"
            assert reason == "generic_contains_buyer"
    
    def test_accepts_valid_buyers(self):
        valid = [
            "Direction Générale des Finances Publiques",
            "Centre Hospitalier de l'Agglomération de Nevers",
            "Région Grand Est",
            "AO / CEA / CEA / GRENOBLE - CENTRE DE GRENOBLE",
        ]
        for buyer in valid:
            is_valid, reason = is_valid_buyer(buyer)
            assert is_valid, f"'{buyer}' should be accepted, got reason={reason}"


class TestScoreTitle:
    """Tests pour le scoring des titres."""
    
    def test_length_scoring(self):
        short = "Short title"
        medium = "This is a medium length title for testing purposes"
        long = "This is a very long title that should score higher because it contains more information about the actual market content"
        
        assert score_title(long) > score_title(medium) > score_title(short)
    
    def test_penalizes_dates(self):
        with_date = "Market published on 10/06/2026 with some details"
        without_date = "Market with some details and information"
        
        assert score_title(without_date) > score_title(with_date)


class TestScoreBuyer:
    """Tests pour le scoring des acheteurs."""
    
    def test_length_and_tokens(self):
        short = "City"
        with_tokens = "Ville de Strasbourg"
        with_structure = "AO / CEA / CEA / GRENOBLE"
        
        assert score_buyer(with_structure) > score_buyer(with_tokens) > score_buyer(short)


class TestPickBestCandidate:
    """Tests pour la sélection du meilleur candidat."""
    
    def test_selects_highest_score_valid(self):
        candidates = [
            FieldCandidate("title", "Titre", "generic", score=0),
            FieldCandidate("title", "Valid Title Here", "specific", score=20),
            FieldCandidate("title", "Another Good Title", "specific2", score=15),
        ]
        
        best, traces = pick_best_candidate(candidates, is_valid_title, score_title)
        assert best == "Valid Title Here"
        assert len(traces) == 3
        assert traces[0].accepted is False  # "Titre" rejected
        assert traces[1].accepted is True
        assert traces[2].accepted is True
    
    def test_returns_empty_if_all_invalid(self):
        candidates = [
            FieldCandidate("title", "Titre", "generic", score=0),
            FieldCandidate("title", "Accord", "generic2", score=0),
        ]
        
        best, traces = pick_best_candidate(candidates, is_valid_title, score_title)
        assert best == ""
        assert all(not t.accepted for t in traces)
    
    def test_empty_candidates(self):
        best, traces = pick_best_candidate([], is_valid_title, score_title)
        assert best == ""
        assert traces == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
