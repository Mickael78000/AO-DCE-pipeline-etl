"""Tests unitaires pour l'extracteur Marchés Online."""

import pytest
from pathlib import Path
from bs4 import BeautifulSoup

from ao_etl.sources.marches_online import MarchesOnlineExtractor
from ao_etl.sources.base import ExtractionContext
from ao_etl.sources.router import detect_source_type
from ao_etl.models.market import SourceType, ExtractionStatus


class TestMarchesOnlineExtractor:
    """Tests pour l'extracteur Marchés Online."""
    
    def test_detects_source_from_filename(self, tmp_path):
        """Détecte la source depuis le nom de fichier ao-*."""
        html_file = tmp_path / "ao-12345-1.html"
        content = "<html><body>test</body></html>"
        html_file.write_text(content)
        
        soup = BeautifulSoup(content, 'html.parser')
        assert detect_source_type(html_file, content, soup) == "MARCHES_ONLINE"
    
    def test_detects_source_from_content(self, tmp_path):
        """Détecte la source depuis marchesonline.com dans le contenu."""
        html_file = tmp_path / "test.html"
        content = '<html><script>var x = "marchesonline.com";</script></html>'
        html_file.write_text(content)
        
        soup = BeautifulSoup(content, 'html.parser')
        assert detect_source_type(html_file, content, soup) == "MARCHES_ONLINE"
    
    def test_extracts_reference_from_filename_not_refcontrat(self, tmp_path):
        """Critique: la référence doit provenir du nom de fichier, PAS de refContrat."""
        # Simule un fichier avec refContrat identique (bug ancien: 1838554)
        html_file = tmp_path / "ao-9594452-1.html"
        content = """
        <html>
            <script>
                dataLayer = [{
                    'refContrat': '1838554',  // Identique pour tous les marchés du compte!
                    'organisme': 'Test Org'
                }];
            </script>
        </html>
        """
        html_file.write_text(content)
        
        soup = BeautifulSoup(content, 'html.parser')
        context = ExtractionContext(file_path=html_file, html=content, soup=soup)
        extractor = MarchesOnlineExtractor(context)
        data = extractor.extract()
        
        # Doit extraire MO-9594452 depuis le nom de fichier, PAS 1838554
        assert data.reference == "MO-9594452"
        assert data.reference != "1838554"
    
    def test_extracts_title_from_title_tag(self, tmp_path):
        """Extrait le titre depuis la balise <title>."""
        html_file = tmp_path / "ao-12345-1.html"
        content = "<html><head><title>Appel d'offres : Maintenance serveurs, Paris</title></head></html>"
        html_file.write_text(content)
        
        soup = BeautifulSoup(content, 'html.parser')
        context = ExtractionContext(file_path=html_file, html=content, soup=soup)
        extractor = MarchesOnlineExtractor(context)
        data = extractor.extract()
        
        assert "Maintenance serveurs" in data.title
        assert "Appel d'offres" not in data.title  # Doit être nettoyé
    
    @pytest.mark.skip(reason="MarchesOnlineExtractor V2 n'extrait pas depuis 'Pouvoir adjudicateur' - utilise print_area_company, Nom officiel, dataLayer")
    def test_extracts_buyer_from_text(self, tmp_path):
        """Extrait l'acheteur depuis le texte structuré.
        
        NOTE: Test legacy - le nouveau MarchesOnlineExtractor V2 utilise une architecture
        candidate/trace avec sources: print_area_company > a, Nom officiel pattern, dataLayer.
        Le pattern 'Pouvoir adjudicateur' n'est pas implémenté dans la version actuelle.
        """
        html_file = tmp_path / "ao-12345-1.html"
        content = """
        <html>
            <body>
                <div>Pouvoir adjudicateur : Ministère de la Test</div>
            </body>
        </html>
        """
        html_file.write_text(content)
        
        soup = BeautifulSoup(content, 'html.parser')
        context = ExtractionContext(file_path=html_file, html=content, soup=soup)
        extractor = MarchesOnlineExtractor(context)
        data = extractor.extract()
        
        assert "Ministère" in data.buyer
    
    @pytest.mark.skip(reason="Dépend de test_extracts_buyer_from_text - pattern 'Pouvoir adjudicateur' non implémenté dans V2")
    def test_rejects_suspicious_buyer_values(self, tmp_path):
        """Rejète les valeurs d'acheteur suspectes ("Retour à la liste").
        
        NOTE: Test legacy - dépend du pattern 'Pouvoir adjudicateur' qui n'est pas
        implémenté dans MarchesOnlineExtractor V2. Le rejet des valeurs suspectes
        est toujours actif dans validation.is_valid_buyer() mais ce test ne peut
        pas l'exercer avec le pattern legacy.
        """
        html_file = tmp_path / "ao-12345-1.html"
        content = """
        <html>
            <body>
                <div>Pouvoir adjudicateur : Retour à la liste</div>
            </body>
        </html>
        """
        html_file.write_text(content)
        
        soup = BeautifulSoup(content, 'html.parser')
        context = ExtractionContext(file_path=html_file, html=content, soup=soup)
        extractor = MarchesOnlineExtractor(context)
        data = extractor.extract()
        
        # Ne doit pas accepter "Retour à la liste" comme acheteur valide
        assert data.buyer == "" or "Retour" not in data.buyer


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
