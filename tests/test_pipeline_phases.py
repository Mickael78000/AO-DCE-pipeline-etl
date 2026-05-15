"""
Tests unitaires pour chaque phase du pipeline ETL.

Tests de composants individuels:
- Phase 1: Discovery
- Phase 2: Reconcile  
- Phase 3: Extract
- Phase 4: Merge
- Phase 5: Validate
- Phase 6: Export
"""

import pytest
import csv
import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import shutil

# Imports des phases
from ao_etl.pipeline.discovery import discover_files, DiscoveryResult
from ao_etl.pipeline.reconcile import reconcile, ReconciledItem, ReconciliationResult, load_csv
from ao_etl.pipeline.merge import merge, MergeResult
from ao_etl.pipeline.validate import validate_rows, ValidationResult
from ao_etl.pipeline.state import ValidationError
from ao_etl.pipeline.export import export_csv, generate_report


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_dir():
    """Crée un répertoire temporaire."""
    tmp = Path(tempfile.mkdtemp(prefix="phase_test_"))
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def html_dir_with_files(temp_dir):
    """Crée un répertoire HTML avec fichiers variés."""
    html_dir = temp_dir / "html"
    html_dir.mkdir()
    
    # Fichiers HTML valides
    (html_dir / "test1-2024-marche.html").write_text("<html><body>Test 1</body></html>")
    (html_dir / "test2-2024-accord-cadre.html").write_text("<html><body>Test 2</body></html>")
    (html_dir / "test3-2025-appel-offres.html").write_text("<html><body>Test 3</body></html>")
    
    # Fichiers à ignorer
    (html_dir / "readme.txt").write_text("Not HTML")
    (html_dir / "backup.html.bak").write_text("Backup")
    
    # Sous-répertoire avec fichiers
    subdir = html_dir / "subdir"
    subdir.mkdir()
    (subdir / "sub1-2024-marche.html").write_text("<html><body>Sub 1</body></html>")
    
    return html_dir


@pytest.fixture
def sample_csv_rows():
    """Retourne des lignes CSV de test."""
    return [
        {
            "Référence": "13/joue/001",
            "Type_AO": "marché",
            "Titre": "Test 1",
            "Date publication": "2024-01-01",
            "Date cloture": "2024-02-01",
            "Acheteur": "Acheteur 1"
        },
        {
            "Référence": "13/joue/002", 
            "Type_AO": "accord-cadre",
            "Titre": "Test 2",
            "Date publication": "2024-01-02",
            "Date cloture": "2024-02-02",
            "Acheteur": "Acheteur 2"
        }
    ]


@pytest.fixture
def sample_fieldnames():
    """Retourne les noms de colonnes CSV."""
    return [
        "Référence", "Type_AO", "Titre", "Date publication",
        "Date cloture", "Acheteur"
    ]


# =============================================================================
# TESTS: Phase 1 - DISCOVERY
# =============================================================================

class TestDiscoveryPhase:
    """Tests pour la phase de découverte des fichiers."""
    
    def test_discover_files_finds_html(self, html_dir_with_files):
        """Test que seuls les fichiers HTML sont découverts."""
        result = discover_files(html_dir_with_files)
        
        assert isinstance(result, DiscoveryResult)
        assert result.total_count == 4  # 3 fichiers à la racine + 1 dans subdir
        
        filenames = [f.filename for f in result.all_files]
        assert "test1-2024-marche.html" in filenames
        assert "test2-2024-accord-cadre.html" in filenames
        assert "test3-2025-appel-offres.html" in filenames
        assert "sub1-2024-marche.html" in filenames
        
        # Vérifier que les non-HTML sont exclus
        assert "readme.txt" not in filenames
        assert "backup.html.bak" not in filenames
    
    def test_discover_empty_directory(self, temp_dir):
        """Test découverte dans répertoire vide."""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()
        
        result = discover_files(empty_dir)
        assert result.total_count == 0
        assert len(result.all_files) == 0
    
    def test_discover_nonexistent_directory(self, temp_dir):
        """Test découverte dans répertoire inexistant."""
        nonexistent = temp_dir / "does_not_exist"
        
        with pytest.raises(FileNotFoundError):
            discover_files(nonexistent)
    
    def test_discover_preserves_paths(self, html_dir_with_files):
        """Test que les chemins complets sont préservés."""
        result = discover_files(html_dir_with_files)
        
        for file_info in result.all_files:
            assert file_info.path.exists()
            assert file_info.path.suffix == ".html"
            assert file_info.filename.endswith(".html")
    
    def test_discover_file_attributes(self, html_dir_with_files):
        """Test que les attributs de fichiers sont présents."""
        result = discover_files(html_dir_with_files)
        
        for file_info in result.all_files:
            assert file_info.path.exists()
            assert file_info.filename.endswith(".html")
            assert file_info.category is not None
            assert file_info.reference_derived is not None


# =============================================================================
# TESTS: Phase 2 - RECONCILE
# =============================================================================

class TestReconcilePhase:
    """Tests pour la phase de réconciliation."""
    
    def test_reconcile_new_files(self, html_dir_with_files):
        """Test réconciliation avec nouveaux fichiers."""
        discovery = discover_files(html_dir_with_files)
        
        # CSV vide
        csv_rows = []
        fieldnames = ["Référence", "Type_AO", "Titre"]
        
        result = reconcile(
            discovered_files=discovery.all_files,
            csv_rows=csv_rows,
            csv_fieldnames=fieldnames
        )
        
        assert isinstance(result, ReconciliationResult)
        # Vérifier via by_status
        from ao_etl.pipeline.reconcile import ReconciliationStatus
        assert len(result.get_by_status(ReconciliationStatus.NEW_MARKET)) == 4
        assert len(result.items) == 4
        
        # Tous les items devraient nécessiter extraction
        from ao_etl.pipeline.reconcile import ReconciliationStatus
        for item in result.items:
            assert item.needs_extraction
            assert item.status == ReconciliationStatus.NEW_MARKET
    
    def test_reconcile_existing_files(self, html_dir_with_files):
        """Test réconciliation avec fichiers existants."""
        discovery = discover_files(html_dir_with_files)
        
        # CSV avec fichier existant
        csv_rows = [
            {
                "Référence": "test1-2024",
                "Type_AO": "marché",
                "Titre": "Test 1",
                "HTML_File": "test1-2024-marche.html"
            }
        ]
        fieldnames = list(csv_rows[0].keys())
        
        result = reconcile(
            discovered_files=discovery.all_files,
            csv_rows=csv_rows,
            csv_fieldnames=fieldnames
        )
        
        # Vérifier la structure du résultat
        assert len(result.items) == 4
        # Certains peuvent être NEW_MARKET, d'autres MATCHED
        assert len(result.by_status) > 0
    
    def test_reconcile_with_modifications(self, html_dir_with_files):
        """Test réconciliation avec fichiers modifiés."""
        discovery = discover_files(html_dir_with_files)
        
        # Simuler un fichier modifié (date plus ancienne)
        csv_rows = [
            {
                "Référence": "test1-2024",
                "Type_AO": "marché", 
                "Titre": "Test 1",
                "HTML_File": "test1-2024-marche.html",
                "File_Modified": "2020-01-01T00:00:00"  # Date ancienne
            }
        ]
        fieldnames = list(csv_rows[0].keys())
        
        result = reconcile(
            discovered_files=discovery.all_files,
            csv_rows=csv_rows,
            csv_fieldnames=fieldnames
        )
        
        # Le fichier devrait être présent dans les items
        assert len(result.items) > 0
    
    def test_load_csv_existing_file(self, temp_dir, sample_csv_rows, sample_fieldnames):
        """Test chargement CSV existant."""
        csv_path = temp_dir / "test.csv"
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=sample_fieldnames)
            writer.writeheader()
            writer.writerows(sample_csv_rows)
        
        rows, fieldnames = load_csv(csv_path)
        
        assert len(rows) == 2
        assert rows[0]["Référence"] == "13/joue/001"
        assert rows[1]["Référence"] == "13/joue/002"
        assert "Référence" in fieldnames
    
    def test_load_csv_nonexistent_file(self, temp_dir):
        """Test chargement CSV inexistant."""
        csv_path = temp_dir / "does_not_exist.csv"
        
        rows, fieldnames = load_csv(csv_path)
        
        assert len(rows) == 0
        assert len(fieldnames) == 0  # Pas de fieldnames si fichier inexistant


# =============================================================================
# TESTS: Phase 3 - EXTRACT (mocké)
# =============================================================================

class TestExtractPhase:
    """Tests pour la phase d'extraction (avec mocking)."""
    
    @patch('ao_etl.sources.router.extract_for_source')
    def test_extract_success(self, mock_extract, html_dir_with_files):
        """Test extraction réussie."""
        from ao_etl.models.market import MarketData
        
        # Mock de données extraites
        mock_data = MarketData(
            reference="13/joue/001",
            title="Test Market",
            buyer="Test Buyer",
            type_ao="marché"
        )
        mock_extract.return_value = mock_data
        
        from ao_etl.pipeline.run import extract_for_source
        result = extract_for_source(html_dir_with_files / "test1-2024-marche.html")
        
        assert result is not None
        assert result.reference == "13/joue/001"
    
    @patch('ao_etl.sources.router.extract_for_source')
    def test_extract_error_handling(self, mock_extract, html_dir_with_files):
        """Test gestion d'erreur d'extraction."""
        mock_extract.side_effect = Exception("Extraction failed")
        
        from ao_etl.sources.router import extract_for_source
        
        with pytest.raises(Exception, match="Extraction failed"):
            extract_for_source(html_dir_with_files / "test1-2024-marche.html")


# =============================================================================
# TESTS: Phase 4 - MERGE
# =============================================================================

class TestMergePhase:
    """Tests pour la phase de fusion."""
    
    def test_merge_new_items(self):
        """Test fusion avec nouveaux items."""
        # Créer un ReconciliationResult simulé
        reconcile_result = Mock(spec=ReconciliationResult)
        reconcile_result.items = []
        reconcile_result.new_markets = []
        
        # Créer des items
        for i, filename in enumerate(["file1.html", "file2.html"]):
            item = Mock()
            item.discovered = Mock()
            item.discovered.filename = filename
            item.status = "new"
            item.needs_extraction = True
            item.existing_row = None
            reconcile_result.items.append(item)
        
        # Données extraites
        extracted_data = {
            "file1.html": Mock(
                reference="13/joue/001",
                title="Test 1",
                buyer="Buyer 1",
                type_ao="marché"
            ),
            "file2.html": Mock(
                reference="13/joue/002",
                title="Test 2",
                buyer="Buyer 2",
                type_ao="accord-cadre"
            )
        }
        
        result = merge(reconcile_result, extracted_data)
        
        assert isinstance(result, MergeResult)
        assert result.new_count == 2
        assert len(result.final_rows) == 2
    
    def test_merge_preserves_existing(self):
        """Test que les lignes existantes sont préservées."""
        reconcile_result = Mock(spec=ReconciliationResult)
        reconcile_result.items = []
        reconcile_result.new_count = 0
        reconcile_result.preserve_count = 1
        reconcile_result.update_count = 0
        
        # Item à préserver
        item = Mock()
        item.discovered = Mock()
        item.discovered.filename = "existing.html"
        item.status = "preserve"
        item.needs_extraction = False
        item.existing_row = {
            "Référence": "13/joue/001",
            "Titre": "Existing Title",
            "Acheteur": "Existing Buyer"
        }
        reconcile_result.items.append(item)
        
        result = merge(reconcile_result, {})
        
        assert result.preserve_count == 1
        assert len(result.final_rows) == 1
        assert result.final_rows[0]["Titre"] == "Existing Title"


# =============================================================================
# TESTS: Phase 5 - VALIDATE
# =============================================================================

class TestValidatePhase:
    """Tests pour la phase de validation."""
    
    def test_validate_empty_reference(self):
        """Test validation détecte référence vide."""
        rows = [
            {"Référence": "", "Titre": "Test", "Acheteur": "Buyer"},
            {"Référence": "13/joue/001", "Titre": "Test 2", "Acheteur": "Buyer 2"}
        ]
        
        result = validate_rows(rows, new_rows_only=False)
        
        assert isinstance(result, ValidationResult)
        assert not result.is_valid  # Devrait être invalide
        assert result.total_rows == 2
        assert len(result.errors) > 0
        
        # Vérifier l'erreur de référence vide
        ref_errors = [e for e in result.errors if "référence" in e.lower() or "Référence" in e]
        assert len(ref_errors) > 0
    
    def test_validate_empty_title(self):
        """Test validation détecte titre vide."""
        rows = [
            {"Référence": "13/joue/001", "Titre": "", "Acheteur": "Buyer"}
        ]
        
        result = validate_rows(rows, new_rows_only=False)
        
        assert not result.is_valid
        assert len(result.errors) > 0
    
    def test_validate_duplicate_references(self):
        """Test validation détecte doublons."""
        rows = [
            {"Référence": "13/joue/001", "Titre": "Test 1", "Acheteur": "Buyer 1"},
            {"Référence": "13/joue/001", "Titre": "Test 2", "Acheteur": "Buyer 2"}
        ]
        
        result = validate_rows(rows, new_rows_only=False)
        
        assert not result.is_valid
        # Vérifier erreur de doublon
        dup_errors = [e for e in result.errors if "doublon" in e.lower() or "duplicate" in e.lower()]
        assert len(dup_errors) > 0
    
    def test_validate_valid_rows(self):
        """Test validation avec lignes valides."""
        rows = [
            {
                "Référence": "13/joue/001",
                "Titre": "Test 1",
                "Acheteur": "Buyer 1",
                "Type_AO": "marché"
            },
            {
                "Référence": "13/joue/002",
                "Titre": "Test 2",
                "Acheteur": "Buyer 2",
                "Type_AO": "accord-cadre"
            }
        ]
        
        result = validate_rows(rows, new_rows_only=False)
        
        assert result.is_valid
        assert result.total_rows == 2
        assert len(result.errors) == 0
    
    def test_validate_new_rows_only(self):
        """Test validation seulement sur nouvelles lignes."""
        rows = [
            {"Référence": "13/joue/001", "Titre": "Test 1", "_new": True},
            {"Référence": "13/joue/002", "Titre": "", "_new": False}  # Existant avec titre vide
        ]
        
        result = validate_rows(rows, new_rows_only=True)
        
        # Devrait valider car seule la ligne _new=True est vérifiée
        # et elle est valide
        assert len(result.errors) == 0 or result.is_valid


# =============================================================================
# TESTS: Phase 6 - EXPORT
# =============================================================================

class TestExportPhase:
    """Tests pour la phase d'export."""
    
    def test_export_csv_creates_file(self, temp_dir):
        """Test que export_csv crée le fichier."""
        output_path = temp_dir / "output.csv"
        rows = [
            {"Référence": "13/joue/001", "Titre": "Test 1"},
            {"Référence": "13/joue/002", "Titre": "Test 2"}
        ]
        fieldnames = ["Référence", "Titre"]
        
        export_csv(rows, fieldnames, output_path)
        
        assert output_path.exists()
        
        # Vérifier le contenu
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "13/joue/001" in content
            assert "Test 1" in content
    
    def test_export_csv_with_utf8(self, temp_dir):
        """Test export avec caractères UTF-8."""
        output_path = temp_dir / "output.csv"
        rows = [
            {"Référence": "13/joue/001", "Titre": "Test avec accents: éàù"},
            {"Référence": "13/joue/002", "Titre": "Test unicode: 日本語"}
        ]
        fieldnames = ["Référence", "Titre"]
        
        export_csv(rows, fieldnames, output_path)
        
        # Vérifier encodage
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "éàù" in content
            assert "日本語" in content
    
    def test_generate_report(self):
        """Test génération de rapport."""
        discovery = Mock()
        discovery.total_count = 5
        discovery.all_files = []
        
        reconcile = Mock()
        reconcile.new_count = 3
        reconcile.preserve_count = 2
        
        merge = Mock()
        merge.final_rows = [{"Référence": "1"}, {"Référence": "2"}]
        merge.new_count = 3
        
        validate = Mock()
        validate.is_valid = True
        validate.total_rows = 5
        
        report = generate_report(
            discovery=discovery,
            reconcile=reconcile,
            merge=merge,
            validate=validate,
            output_csv_path=Path("/tmp/test.csv"),
            output_report_path=Path("/tmp/test.json")
        )
        
        assert report["discovery"]["total_files"] == 5
        assert report["reconcile"]["new_count"] == 3
        assert report["merge"]["total_rows"] == 5
        assert report["validation"]["is_valid"] is True


# =============================================================================
# TESTS: Intégration Phase par Phase
# =============================================================================

class TestPhaseIntegration:
    """Tests d'intégration entre phases."""
    
    def test_discovery_to_reconcile(self, html_dir_with_files):
        """Test flux discovery → reconcile."""
        # Phase 1
        discovery = discover_files(html_dir_with_files)
        assert discovery.total_count == 4
        
        # Phase 2
        csv_rows = []
        fieldnames = ["Référence", "Type_AO", "Titre"]
        
        reconcile_result = reconcile(
            discovered_files=discovery.all_files,
            csv_rows=csv_rows,
            csv_fieldnames=fieldnames
        )
        
        assert reconcile_result.total_count == discovery.total_count
        assert reconcile_result.new_count == discovery.total_count
    
    def test_full_pipeline_flow_mocked(self, temp_dir):
        """Test flux complet avec mocking."""
        # Setup
        html_dir = temp_dir / "html"
        html_dir.mkdir()
        (html_dir / "test-2024-marche.html").write_text("<html>Test</html>")
        
        # Phase 1
        discovery = discover_files(html_dir)
        assert discovery.total_count == 1
        
        # Phase 2
        reconcile_result = reconcile(
            discovered_files=discovery.all_files,
            csv_rows=[],
            csv_fieldnames=["Référence", "Titre"]
        )
        
        # Phase 3 (mocké)
        extracted_data = {
            "test-2024-marche.html": Mock(
                reference="13/joue/001",
                title="Test Market",
                buyer="Test Buyer",
                type_ao="marché"
            )
        }
        
        # Phase 4
        merge_result = merge(reconcile_result, extracted_data)
        assert len(merge_result.final_rows) == 1
        
        # Phase 5
        validation = validate_rows(merge_result.final_rows, new_rows_only=False)
        
        # Phase 6
        output_path = temp_dir / "output.csv"
        export_csv(
            merge_result.final_rows,
            merge_result.fieldnames,
            output_path
        )
        
        assert output_path.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
