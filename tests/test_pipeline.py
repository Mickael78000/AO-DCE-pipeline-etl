"""Tests unitaires basiques pour le pipeline."""

import pytest
import tempfile
from pathlib import Path
from ao_etl.utils.validation import MarketDataValidated, validate_csv_row
from ao_etl.utils.html_matcher import HTMLMatcher


class TestValidation:
    """Tests de validation."""
    
    def test_valid_market_data(self):
        """Test de validation avec données valides."""
        data = MarketDataValidated(
            reference="REF-2024-001",
            titre="Maintenance informatique",
            acheteur="Ministère XYZ",
            localisation="Paris",
            cpv_principal="72500000"
        )
        assert data.reference == "REF-2024-001"
        assert data.cpv_principal == "72500000"
    
    def test_invalid_cpv(self):
        """Test avec CPV invalide."""
        with pytest.raises(ValueError):
            MarketDataValidated(
                reference="REF-001",
                titre="Test",
                acheteur="Test",
                localisation="Paris",
                cpv_principal="7250000"  # 7 chiffres au lieu de 8
            )
    
    def test_validate_csv_row_valid(self):
        """Test validation ligne CSV valide."""
        row = {
            'Référence': 'REF-001',
            'Intitulé synthétique': 'Test marché',
            'Acheteur_clean': 'Organisme Test'
        }
        is_valid, error = validate_csv_row(row)
        assert is_valid
        assert error is None
    
    def test_validate_csv_row_missing_field(self):
        """Test validation avec champ manquant."""
        row = {
            'Référence': 'REF-001',
            'Intitulé synthétique': '',  # Vide
            'Acheteur_clean': 'Organisme'
        }
        is_valid, error = validate_csv_row(row)
        assert not is_valid
        assert 'manquant' in error.lower()


class TestHTMLMatcher:
    """Tests du matcher HTML."""
    
    def test_matcher_index_building(self, tmp_path):
        """Test construction de l'index."""
        # Créer un fichier HTML de test
        html_content = """
        <html>
        <body>
        Identifiant interne : TEST-2024-001
        Annonce n° 2024-12345
        </body>
        </html>
        """
        test_file = tmp_path / "test-file.html"
        test_file.write_text(html_content, encoding='utf-8')
        
        matcher = HTMLMatcher(tmp_path)
        stats = matcher.get_stats()
        
        assert stats['total_indexed'] >= 1
    
    def test_matcher_find_by_reference(self, tmp_path):
        """Test recherche par référence."""
        html_content = "Identifiant interne : TEST-REF-001"
        test_file = tmp_path / "test.html"
        test_file.write_text(html_content, encoding='utf-8')
        
        matcher = HTMLMatcher(tmp_path)
        result = matcher.find_html("TEST-REF-001")
        
        assert result.html_path is not None
        assert result.confidence > 0


class TestRobustIO:
    """Tests des utilitaires I/O."""
    
    def test_safe_write_and_read(self, tmp_path):
        """Test écriture et lecture sécurisées."""
        from ao_etl.utils.robust_io import safe_write_file, safe_read_file
        
        test_file = tmp_path / "test.txt"
        content = "Contenu de test"
        
        safe_write_file(test_file, content)
        assert test_file.exists()
        
        read_content = safe_read_file(test_file)
        assert read_content == content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
