"""Tests unitaires pour l'extracteur France Marchés."""

import pytest
from pathlib import Path
from bs4 import BeautifulSoup

from ao_etl.sources.france_marches import FranceMarchesExtractor
from ao_etl.models.market import SourceType


class TestFranceMarchesExtractor:
    """Tests pour l'extracteur France Marchés (weboramaItemTag)."""
    
    def test_detects_source_from_weborama_tag(self, tmp_path):
        """Détecte la source depuis weboramaItemTag et title_article."""
        html_file = tmp_path / "test.html"
        content = """
        <html>
            <script>
                var weboramaItemTag = JSON.parse("{\\u0022title_article\\u0022:\\u0022Test Title\\u0022}");
            </script>
        </html>
        """
        html_file.write_text(content)
        
        soup = BeautifulSoup(content, 'html.parser')
        extractor = FranceMarchesExtractor(html_file, soup, content)
        
        assert extractor.can_extract() is True
    
    def test_extracts_title_from_json_unicode(self, tmp_path):
        """Extrait le titre depuis JSON avec séquences Unicode échappées."""
        html_file = tmp_path / "test.html"
        # Simule le format France Marchés avec \\u0022 pour "
        content = r'''
        <html>
            <script>
                var weboramaItemTag = JSON.parse("{\u0022title_article\u0022:\u0022Prestations d\u0027assistance\u0020et\u0020expertise\u0022}");
            </script>
        </html>
        '''
        html_file.write_text(content)
        
        soup = BeautifulSoup(content, 'html.parser')
        extractor = FranceMarchesExtractor(html_file, soup, content)
        data = extractor.extract()
        
        assert "Prestations d'assistance" in data.title
    
    def test_extracts_reference_from_filename_boamp(self, tmp_path):
        """Extrait la référence BOAMP depuis le nom de fichier."""
        html_file = tmp_path / "3boamp2643374-test.html"
        content = "<html><body>test</body></html>"
        html_file.write_text(content)
        
        soup = BeautifulSoup(content, 'html.parser')
        extractor = FranceMarchesExtractor(html_file, soup, content)
        data = extractor.extract()
        
        assert data.reference == "3/boamp/2643374"
    
    def test_extracts_reference_from_filename_joue(self, tmp_path):
        """Extrait la référence JOUE depuis le nom de fichier."""
        html_file = tmp_path / "13joue002946822026-test.html"
        content = "<html><body>test</body></html>"
        html_file.write_text(content)
        
        soup = BeautifulSoup(content, 'html.parser')
        extractor = FranceMarchesExtractor(html_file, soup, content)
        data = extractor.extract()
        
        assert data.reference == "13/joue/002946822026"
    
    def test_extracts_reference_from_filename_ao(self, tmp_path):
        """Extrait la référence au format 37ao* depuis le nom de fichier."""
        html_file = tmp_path / "37ao26181581260520263294-test.html"
        content = "<html><body>test</body></html>"
        html_file.write_text(content)
        
        soup = BeautifulSoup(content, 'html.parser')
        extractor = FranceMarchesExtractor(html_file, soup, content)
        data = extractor.extract()
        
        assert data.reference == "37AO26181581260520263294"
    
    def test_extracts_title_from_meta_description(self, tmp_path):
        """Fallback: extrait le titre depuis meta description."""
        html_file = tmp_path / "test.html"
        content = '''
        <html>
            <head>
                <meta name="description" content="Appel d'offre n°13/joue/12345 : Maintenance des serveurs">
            </head>
        </html>
        '''
        html_file.write_text(content)
        
        soup = BeautifulSoup(content, 'html.parser')
        extractor = FranceMarchesExtractor(html_file, soup, content)
        data = extractor.extract()
        
        assert "Maintenance des serveurs" in data.title


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
