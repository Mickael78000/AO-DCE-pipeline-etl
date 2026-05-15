"""Tests unitaires pour le nouveau pipeline ETL unifié."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import csv
import tempfile
import shutil

# Imports à tester
from ao_etl.pipeline.discovery import (
    discover_files, derive_reference, is_likely_alias,
    FileCategory, DiscoveredFile
)
from ao_etl.pipeline.reconcile import (
    reconcile, load_csv, ReconciliationStatus
)
from ao_etl.pipeline.merge import (
    merge, apply_manual_overrides, marketdata_to_csv_row
)
from ao_etl.pipeline.validate import (
    validate_rows, ValidationIssue
)
from ao_etl.models.market import MarketData, SourceType


class TestDiscovery:
    """Tests de la phase DISCOVERY."""
    
    def test_derive_reference_marches_online(self):
        """Test dérivation référence Marchés Online."""
        ref, cat = derive_reference('ao-9597894-1.html')
        assert ref == 'MO-9597894'
        assert cat == FileCategory.MARCHES_ONLINE
    
    def test_derive_reference_joue(self):
        """Test dérivation référence JOUE."""
        ref, cat = derive_reference('13joue003085442026.html')
        assert ref == '13joue003085442026'
        assert cat == FileCategory.JOUE
    
    def test_derive_reference_boamp(self):
        """Test dérivation référence BOAMP."""
        ref, cat = derive_reference('3boamp2642071.html')
        assert ref == '3boamp2642071'
        assert cat == FileCategory.BOAMP_XML
    
    def test_derive_reference_place(self):
        """Test dérivation référence PLACE."""
        ref, cat = derive_reference('2987833?orgAcronyme=f2h.html')
        assert '2987833' in ref
        assert cat == FileCategory.PLACE_NUMERIC
    
    def test_is_likely_alias(self):
        """Test détection des alias."""
        is_alias, alias_of = is_likely_alias('13joue003085442026 (1ère occurrence).html')
        assert is_alias is True
        assert alias_of == '13joue003085442026'
    
    def test_discover_files_empty_dir(self, tmp_path):
        """Test discovery sur répertoire vide."""
        with pytest.raises(FileNotFoundError):
            discover_files(tmp_path / 'nonexistent')
    
    def test_discover_files_with_mock(self, tmp_path):
        """Test discovery avec fichiers mock."""
        html_dir = tmp_path / 'html_ao'
        html_dir.mkdir()
        
        # Créer des fichiers test
        (html_dir / 'ao-9597894-1.html').write_text('<html></html>')
        (html_dir / '13joue003085442026.html').write_text('<html></html>')
        (html_dir / 'standard.html').write_text('<html></html>')
        
        result = discover_files(html_dir)
        
        assert result.total_count == 3
        assert len(result.by_category[FileCategory.MARCHES_ONLINE]) == 1
        assert len(result.by_category[FileCategory.JOUE]) == 1
        assert len(result.by_category[FileCategory.STANDARD]) == 1


class TestReconcile:
    """Tests de la phase RECONCILE."""
    
    def test_load_csv_existing(self, tmp_path):
        """Test chargement CSV existant."""
        csv_file = tmp_path / 'test.csv'
        csv_file.write_text('Référence,Titre\nREF1,Titre1\nREF2,Titre2\n')
        
        rows, fieldnames = load_csv(csv_file)
        
        assert len(rows) == 2
        assert 'Référence' in fieldnames
        assert rows[0]['Référence'] == 'REF1'
    
    def test_load_csv_nonexistent(self, tmp_path):
        """Test chargement CSV inexistant."""
        rows, fieldnames = load_csv(tmp_path / 'nonexistent.csv')
        assert rows == []
        assert fieldnames == []
    
    def test_reconcile_new_market(self):
        """Test réconciliation nouveau marché."""
        # Mock discovered file
        discovered = Mock()
        discovered.filename = 'ao-9597894-1.html'
        discovered.reference_derived = 'MO-9597894'
        discovered.is_alias = False
        discovered.category = FileCategory.MARCHES_ONLINE
        
        # CSV vide
        csv_rows = []
        fieldnames = ['Référence']
        
        result = reconcile([discovered], csv_rows, fieldnames)
        
        assert len(result.new_markets) == 1
        assert result.new_markets[0].reference == 'MO-9597894'
    
    def test_reconcile_matched(self):
        """Test réconciliation fichier déjà matché."""
        discovered = Mock()
        discovered.filename = 'ao-9597894-1.html'
        discovered.reference_derived = 'MO-9597894'
        discovered.is_alias = False
        
        # CSV avec entrée existante
        csv_rows = [
            {'Référence': 'MO-9597894', 'match_source': 'ao-9597894-1.html'}
        ]
        fieldnames = ['Référence', 'match_source']
        
        result = reconcile([discovered], csv_rows, fieldnames)
        
        matched = result.get_by_status(ReconciliationStatus.MATCHED)
        assert len(matched) == 1
        assert matched[0].csv_row == csv_rows[0]


class TestMerge:
    """Tests de la phase MERGE."""
    
    def test_apply_manual_overrides(self):
        """Test règle manual > auto."""
        row = {
            'Acheteur_auto': 'Auto Buyer',
            'Acheteur_manual': 'Manual Buyer',
            'Acheteur': '',
        }
        
        result = apply_manual_overrides(row)
        
        assert result['Acheteur'] == 'Manual Buyer'
    
    def test_apply_manual_overrides_empty_manual(self):
        """Test fallback auto quand manual vide."""
        row = {
            'Acheteur_auto': 'Auto Buyer',
            'Acheteur_manual': '',
            'Acheteur': '',
        }
        
        result = apply_manual_overrides(row)
        
        assert result['Acheteur'] == 'Auto Buyer'
    
    def test_marketdata_to_csv_row(self):
        """Test conversion MarketData vers CSV."""
        data = MarketData(
            filename='test.html',
            reference='MO-123',
            title='Test Title',
            buyer='Test Buyer',
            source_type=SourceType.MARCHES_ONLINE
        )
        discovered = Mock()
        discovered.filename = 'test.html'
        discovered.reference_derived = 'MO-123'
        
        row = marketdata_to_csv_row(data, discovered, ['Référence', 'Acheteur_auto'])
        
        assert row['Référence'] == 'MO-123'
        assert row['Acheteur_auto'] == 'Test Buyer'
        assert row['Plateforme'] == 'Marchés Online'


class TestValidate:
    """Tests de la phase VALIDATE."""
    
    def test_validate_empty_reference(self):
        """Test détection référence vide."""
        rows = [
            {'Référence': '-', 'Intitulé synthétique': 'Title'},
            {'Référence': 'REF1', 'Intitulé synthétique': 'Title'},
        ]
        
        result = validate_rows(rows)
        
        assert result.is_valid is False
        assert result.stats.empty_references == 1
        assert any(i.field == 'Référence' for i in result.issues)
    
    def test_validate_duplicate_reference(self):
        """Test détection doublon."""
        rows = [
            {'Référence': 'REF1', 'Intitulé synthétique': 'Title1'},
            {'Référence': 'REF1', 'Intitulé synthétique': 'Title2'},
        ]
        
        result = validate_rows(rows)
        
        assert result.is_valid is False
        assert result.stats.duplicate_references == 1
    
    def test_validate_buyer_stats(self):
        """Test stats acheteur."""
        rows = [
            {'Référence': 'REF1', 'Acheteur_auto': 'Buyer1'},
            {'Référence': 'REF2', 'Acheteur_auto': '-'},
            {'Référence': 'REF3', 'Acheteur_auto': 'Buyer3'},
        ]
        
        result = validate_rows(rows)
        
        assert result.stats.buyer_filled == 2
        assert result.stats.buyer_empty == 1
        assert result.stats.buyer_completion_rate == pytest.approx(66.67, 0.01)
    
    def test_validate_new_rows_only(self):
        """Test validation uniquement sur nouvelles lignes."""
        rows = [
            {'Référence': '-', 'match_status': 'new'},
            {'Référence': 'REF1', 'match_status': 'existing'},
        ]
        
        result = validate_rows(rows, new_rows_only=True)
        
        assert result.stats.total_rows == 1
        assert result.stats.empty_references == 1


class TestIntegration:
    """Tests d'intégration des phases."""
    
    def test_pipeline_phases_integration(self, tmp_path):
        """Test intégration complète discovery → reconcile."""
        # Setup
        html_dir = tmp_path / 'html_ao'
        html_dir.mkdir()
        (html_dir / 'ao-9597894-1.html').write_text('<html>Test</html>')
        
        csv_file = tmp_path / 'test.csv'
        csv_file.write_text('Référence\nEXISTING\n')
        
        # Discovery
        from ao_etl.pipeline.discovery import discover_files
        discovery = discover_files(html_dir)
        
        # Reconcile
        from ao_etl.pipeline.reconcile import reconcile, load_csv
        csv_rows, fieldnames = load_csv(csv_file)
        reconcile_result = reconcile(discovery.all_files, csv_rows, fieldnames)
        
        # Assertions
        assert discovery.total_count == 1
        assert len(reconcile_result.new_markets) == 1
        assert reconcile_result.new_markets[0].reference == 'MO-9597894'
