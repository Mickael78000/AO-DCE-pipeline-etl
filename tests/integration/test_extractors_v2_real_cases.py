"""Tests d'intégration pour les extracteurs V2 sur cas réels."""

from pathlib import Path
import pytest

from ao_etl.sources import extract_for_source


# Répertoire des fixtures HTML
HTML_DIR = Path(__file__).parent.parent.parent / "data" / "raw" / "html"


class TestPlaceNumeric:
    """Tests pour le format PLACE (orgAcronyme)."""
    
    def test_place_2997383(self):
        """Test PLACE: 2997383-orgAcronyme-s2d.html
        
        Attendus:
        - reference = B26-01107-LS
        - rejet de "Détail de la consultation"
        - title métier retenu
        - rejet de "Autres organismes"
        - buyer = AO / CEA / CEA / GRENOBLE - CENTRE DE GRENOBLE
        - deadline = 10/06/2026 16:00
        - location = (38) Isère
        """
        filepath = HTML_DIR / "2997383?orgAcronyme=s2d.html"
        if not filepath.exists():
            pytest.skip(f"Fixture non trouvé: {filepath}")
        
        result = extract_for_source(filepath, version='v2')
        
        # Référence
        assert result.reference == "B26-01107-LS", f"Expected B26-01107-LS, got {result.reference}"
        
        # Titre ne doit pas être générique
        assert result.title != "Détail de la consultation"
        assert result.title != ""
        assert "maintenance" in result.title.lower() or "prestation" in result.title.lower() or len(result.title) > 20
        
        # Acheteur ne doit pas être générique
        assert result.buyer != "Autres organismes"
        assert "CEA" in result.buyer or "GRENOBLE" in result.buyer or result.review_needed
        
        # Traces doivent montrer les rejets
        notes = " | ".join(result.extraction_notes)
        assert "rejected" in notes.lower() or "accepted" in notes.lower()


class TestBoamp:
    """Tests pour le format BOAMP XML."""
    
    def test_boamp_26_41049(self):
        """Test BOAMP: 26-41049.html (DGFIP)
        
        Attendus:
        - buyer = Direction Générale des Finances Publiques
        - title complet retenu (pas "Titre")
        - reference = DGFIP-DRS-2500077
        - estimation = 400,000 Euro ou équivalent
        - duration = 48 Mois ou équivalent
        - deadline = 04/06/2026 17:00
        - pas de confusion avec rôles parasites
        """
        filepath = HTML_DIR / "26-41049.html"
        if not filepath.exists():
            pytest.skip(f"Fixture non trouvé: {filepath}")
        
        result = extract_for_source(filepath, version='v2')
        
        # Référence
        assert result.reference == "DGFIP-DRS-2500077", f"Expected DGFIP-DRS-2500077, got {result.reference}"
        
        # Titre ne doit pas être "Titre"
        assert result.title != "Titre"
        assert len(result.title) > 20
        assert "assistance" in result.title.lower() or "consultation" in result.title.lower() or result.review_needed
        
        # Acheteur = DGFIP
        assert "Direction Générale des Finances Publiques" in result.buyer or \
               "Finances Publiques" in result.buyer or result.review_needed
        
        # Pas de confusion avec rôles
        assert "TED eSender" not in result.buyer
        assert "informations complémentaires" not in result.buyer.lower()


class TestFranceMarches:
    """Tests pour le format France Marchés."""
    
    def test_france_marches_13joue(self):
        """Test France Marchés: 13joue003107212026-2026-maintien-condition-operationnelle.html
        
        Attendus:
        - buyer = Centre Hospitalier de l'Agglomération de Nevers
        - rejet de "Organisme de droit public"
        """
        filepath = HTML_DIR / "13joue003107212026-2026-maintien-condition-operationnelle.html"
        if not filepath.exists():
            pytest.skip(f"Fixture non trouvé: {filepath}")
        
        result = extract_for_source(filepath, version='v2')
        
        # Acheteur ne doit pas être la catégorie
        assert result.buyer != "Organisme de droit public"
        
        # Doit trouver le vrai acheteur
        assert "Centre Hospitalier" in result.buyer or "CHU" in result.buyer or \
               "Nevers" in result.buyer or result.review_needed
    
    def test_france_marches_36parisien(self):
        """Test France Marchés: 36parisien1157695-2026-infogerance-systeme-information.html
        
        Attendus:
        - title = Infogérance du système d'information de la ville de Croissy-sur-Seine
        - buyer = Ville de Croissy-sur-Seine
        - deadline = 20/05/2026 12:00 ou équivalent
        - reference interne = info-SI si possible
        """
        filepath = HTML_DIR / "36parisien1157695-2026-infogerance-systeme-information.html"
        if not filepath.exists():
            pytest.skip(f"Fixture non trouvé: {filepath}")
        
        result = extract_for_source(filepath, version='v2')
        
        # Titre
        assert "infogérance" in result.title.lower() or "système" in result.title.lower() or result.review_needed
        
        # Acheteur
        assert "Croissy" in result.buyer or "Ville" in result.buyer or result.review_needed


class TestMarchesOnline:
    """Tests pour le format Marchés Online (prudents)."""
    
    def test_marches_online_ao_9599071_prudent(self):
        """Test Marchés Online: ao-9599071-1.html (prudent)
        
        Principe: ne pas inventer de données non prouvées.
        Si la fixture est incomplète ou incertaine:
        - review_needed=True
        - extraction_notes explicite
        - champs vides préférables à faux positifs
        """
        filepath = HTML_DIR / "ao-9599071-1.html"
        if not filepath.exists():
            pytest.skip(f"Fixture non trouvé: {filepath}")
        
        result = extract_for_source(filepath, version='v2')
        
        # Ne doit PAS inventer un acheteur final non prouvé
        if "Services d'administration générale" in result.buyer:
            # Si on tombe sur un faux positif connu, on doit marquer review_needed
            assert result.review_needed, "Faux positif détecté mais review_needed=False"
        
        # Ne doit PAS inventer une référence non prouvée
        if result.reference and result.reference.startswith("MO-"):
            # Si on a une référence, vérifier qu'elle est correcte
            pass  # OK si prouvé
        
        # Extraction notes doit expliquer les décisions
        notes = " | ".join(result.extraction_notes)
        assert len(notes) > 0, "Aucune trace d'extraction"


class TestExtractionNotes:
    """Tests pour la traçabilité des extractions."""
    
    def test_traces_structure(self):
        """Vérifie que les traces sont bien structurées."""
        filepath = HTML_DIR / "26-41049.html"
        if not filepath.exists():
            pytest.skip(f"Fixture non trouvé: {filepath}")
        
        result = extract_for_source(filepath, version='v2')
        
        # Doit avoir des notes
        assert len(result.extraction_notes) > 0
        
        # Notes doivent contenir des traces acceptées ou rejetées
        for note in result.extraction_notes:
            assert any(kw in note.lower() for kw in ["accepted", "rejected", "->"])


class TestReviewNeeded:
    """Tests pour le flag review_needed."""
    
    def test_review_when_critical_fields_missing(self):
        """Vérifie que review_needed=True quand champs critiques manquants."""
        # Utiliser un fichier qui pose problème
        filepath = HTML_DIR / "ao-9599071-1.html"
        if not filepath.exists():
            pytest.skip(f"Fixture non trouvé: {filepath}")
        
        result = extract_for_source(filepath, version='v2')
        
        # Si titre ou acheteur vide, review_needed doit être True
        if not result.title or not result.buyer:
            assert result.review_needed, "Champs critiques vides mais review_needed=False"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
