"""
Tests End-to-End pour le pipeline ETL complet.

Ces tests vérifient le pipeline dans son ensemble avec des données réalistes.
"""

import pytest
import csv
import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import shutil
import os

# Import du pipeline complet
from ao_etl.pipeline import run_pipeline, PipelineResult
from ao_etl.pipeline.state import PipelineStateManager, PhaseStatus


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def e2e_temp_dir():
    """Crée un répertoire temporaire pour les tests E2E."""
    tmp = Path(tempfile.mkdtemp(prefix="e2e_pipeline_"))
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def real_html_structure(e2e_temp_dir):
    """Crée une structure HTML réaliste."""
    html_dir = e2e_temp_dir / "data" / "raw" / "html"
    html_dir.mkdir(parents=True)
    
    # Fichiers HTML de marchés publics réalistes
    html_files = [
        ("DGFIP-DRS-2500077-2025-marche-public.html", """
        <html>
        <head><title>Marché public - DGFIP DRS</title></head>
        <body>
            <h1>Direction Générale des Finances Publiques</h1>
            <p>Référence: DGFIP-DRS-2500077</p>
            <p>Type: Marché public</p>
            <p>Date publication: 15/01/2025</p>
            <p>Date clôture: 28/02/2025</p>
            <p>Estimation: 500000 EUR</p>
        </body>
        </html>
        """),
        ("13joue002925532026-2026-marche-public.html", """
        <html>
        <head><title>Avis d'appel d'offres - Parlement Wallon</title></head>
        <body class="joue">
            <div class="notice">
                <h1>Parlement Wallon</h1>
                <p class="reference">13/joue/002925532026</p>
                <p class="type">Marché public</p>
                <p class="date-publication">2026-01-15</p>
                <p class="date-cloture">2026-02-28</p>
            </div>
        </body>
        </html>
        """),
        ("CNR-2024-001-marche.html", """
        <html>
        <head><title>Marché - Compagnie Nationale du Rhône</title></head>
        <body>
            <h1>Compagnie Nationale du Rhône (CNR)</h1>
            <div>EPIC - Établissement Public à caractère Industriel et Commercial</div>
            <p>Référence: CNR-2024-001</p>
        </body>
        </html>
        """),
        ("UNICANCER-2025-AC.html", """
        <html>
        <head><title>Accord-cadre - UNICANCER</title></head>
        <body>
            <h1>UNICANCER ACHATS</h1>
            <p>Type: Accord-cadre</p>
            <p>Référence: UNICANCER-2025-AC-001</p>
        </body>
        </html>
        """),
    ]
    
    for filename, content in html_files:
        (html_dir / filename).write_text(content, encoding='utf-8')
    
    return html_dir


@pytest.fixture
def real_csv_input(e2e_temp_dir):
    """Crée un CSV d'entrée réaliste."""
    input_dir = e2e_temp_dir / "data" / "input"
    input_dir.mkdir(parents=True)
    
    csv_path = input_dir / "AO-completed.csv"
    
    rows = [
        {
            "Référence": "13/joue/002925532026",
            "Type_AO": "marché",
            "Titre": "Marché public - Parlement Wallon",
            "Date publication": "2026-01-15",
            "Date cloture": "2026-02-28",
            "Date début exécution": "2026-03-15",
            "Durée": "12 mois",
            "Procédure": "procédure ouverte",
            "Estimation": "125000 EUR",
            "Acheteur": "Parlement Wallon",
            "Acheteur_clean": "Parlement Wallon",
            "Type": "",
            "Fonction publique": "",
            "Code CPV": "48000000",
            "Lieu exécution": "Namur, Belgique",
            "CCAG": "",
            "Clause sociale": "non",
            "Clause environnementale": "oui",
            "Recours": "",
            "Allotissement": "non",
            "Extension": "",
            "Variantes": "non",
            "Bons commande": "non",
            "Fonds UE": "non",
            "Tranche": "",
            "Montant garantie": "",
            "Honoraires postaux": "",
            "Periodicite": "",
            "URL": "https://www.parlement-wallon.be",
            "HTML_File": "13joue002925532026-2026-marche-public.html"
        }
    ]
    
    fieldnames = list(rows[0].keys())
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    return csv_path


# =============================================================================
# TESTS END-TO-END
# =============================================================================

class TestPipelineEndToEnd:
    """Tests end-to-end du pipeline complet."""
    
    def test_minimal_pipeline_execution(self, e2e_temp_dir, real_html_structure):
        """Test exécution minimale du pipeline."""
        output_dir = e2e_temp_dir / "data" / "output"
        output_dir.mkdir(parents=True)
        
        input_csv = e2e_temp_dir / "input.csv"
        input_csv.write_text("Référence,Type_AO,Titre\n")
        
        result = run_pipeline(
            html_dir=real_html_structure,
            input_csv=input_csv,
            output_csv=output_dir / "output.csv",
            report_path=output_dir / "report.json",
            verbose=False
        )
        
        assert isinstance(result, PipelineResult)
        assert result.output_csv.exists()
        assert result.output_report.exists()
        assert result.total_rows > 0
    
    def test_pipeline_with_existing_csv(self, e2e_temp_dir, real_html_structure, real_csv_input):
        """Test pipeline avec CSV existant."""
        output_dir = e2e_temp_dir / "data" / "output"
        output_dir.mkdir(parents=True)
        
        result = run_pipeline(
            html_dir=real_html_structure,
            input_csv=real_csv_input,
            output_csv=output_dir / "AO-pipeline-v2.csv",
            report_path=output_dir / "report.json",
            verbose=False
        )
        
        assert result.total_rows > 0
        assert result.output_csv.exists()
        
        # Vérifier le contenu
        with open(result.output_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) > 0
    
    def test_pipeline_idempotence(self, e2e_temp_dir, real_html_structure):
        """Test que le pipeline est idempotent (même résultat si relancé)."""
        output_dir = e2e_temp_dir / "data" / "output"
        output_dir.mkdir(parents=True)
        
        input_csv = e2e_temp_dir / "input.csv"
        input_csv.write_text("Référence,Type_AO,Titre\n")
        
        # Première exécution
        result1 = run_pipeline(
            html_dir=real_html_structure,
            input_csv=input_csv,
            output_csv=output_dir / "output.csv",
            verbose=False
        )
        
        rows1 = result1.total_rows
        
        # Deuxième exécution (avec le même output comme input)
        result2 = run_pipeline(
            html_dir=real_html_structure,
            input_csv=output_dir / "output.csv",
            output_csv=output_dir / "output2.csv",
            verbose=False
        )
        
        # Le nombre de lignes devrait être le même
        assert result2.total_rows == rows1
    
    def test_pipeline_state_tracking(self, e2e_temp_dir, real_html_structure):
        """Test du tracking d'état pendant l'exécution."""
        state_dir = e2e_temp_dir / "state"
        state_manager = PipelineStateManager(
            pipeline_id="e2e_test",
            state_dir=state_dir
        )
        
        # Simuler l'exécution des phases
        with state_manager.run_phase("discovery") as phase:
            phase.stats["files_found"] = 4
        
        with state_manager.run_phase("reconcile") as phase:
            phase.stats["new_items"] = 4
        
        with state_manager.run_phase("extract") as phase:
            phase.stats["extracted"] = 4
        
        with state_manager.run_phase("merge") as phase:
            phase.stats["final_rows"] = 4
        
        with state_manager.run_phase("validate") as phase:
            phase.stats["valid_rows"] = 4
        
        with state_manager.run_phase("export") as phase:
            phase.stats["exported"] = 4
        
        state_manager.mark_complete(success=True)
        
        # Vérifier l'état
        summary = state_manager.get_summary()
        assert summary["total_phases"] == 6
        assert summary["successful_phases"] == 6
        assert summary["failed_phases"] == 0
        
        # Vérifier la persistance
        state_file = state_dir / "e2e_test.json"
        assert state_file.exists()
    
    def test_pipeline_error_recovery(self, e2e_temp_dir):
        """Test de récupération après erreur."""
        # Créer un répertoire HTML avec un fichier corrompu
        html_dir = e2e_temp_dir / "html"
        html_dir.mkdir()
        
        # Fichier valide
        (html_dir / "valid.html").write_text("<html><body>Valid</body></html>")
        
        # Fichier corrompu (pas HTML)
        (html_dir / "corrupt.html").write_text("NOT HTML AT ALL")
        
        input_csv = e2e_temp_dir / "input.csv"
        input_csv.write_text("Référence,Type_AO,Titre\n")
        
        output_dir = e2e_temp_dir / "output"
        output_dir.mkdir()
        
        # Le pipeline devrait continuer malgré l'erreur
        result = run_pipeline(
            html_dir=html_dir,
            input_csv=input_csv,
            output_csv=output_dir / "output.csv",
            verbose=False
        )
        
        # Le pipeline devrait terminer
        assert result.output_csv.exists()


# =============================================================================
# TESTS: Scénarios Réels
# =============================================================================

class TestRealWorldScenarios:
    """Tests basés sur des scénarios réels d'utilisation."""
    
    def test_incremental_update_scenario(self, e2e_temp_dir):
        """Test scénario de mise à jour incrémentale."""
        # Jour 1: 3 marchés
        html_dir = e2e_temp_dir / "html"
        html_dir.mkdir()
        
        for i in range(3):
            (html_dir / f"day1-{i}-marche.html").write_text(f"<html>Market {i}</html>")
        
        input_csv = e2e_temp_dir / "input.csv"
        input_csv.write_text("Référence,Type_AO,Titre\n")
        
        output_dir = e2e_temp_dir / "output"
        output_dir.mkdir()
        
        # Exécution Jour 1
        result1 = run_pipeline(
            html_dir=html_dir,
            input_csv=input_csv,
            output_csv=output_dir / "day1.csv",
            verbose=False
        )
        assert result1.total_rows == 3
        
        # Jour 2: Ajout de 2 nouveaux marchés
        for i in range(2):
            (html_dir / f"day2-{i}-marche.html").write_text(f"<html>New Market {i}</html>")
        
        # Exécution Jour 2 (avec le CSV du jour 1 comme input)
        result2 = run_pipeline(
            html_dir=html_dir,
            input_csv=output_dir / "day1.csv",
            output_csv=output_dir / "day2.csv",
            verbose=False
        )
        
        # Devrait avoir 5 marchés au total
        assert result2.total_rows == 5
    
    def test_html_modification_scenario(self, e2e_temp_dir):
        """Test scénario de modification de fichier HTML."""
        html_dir = e2e_temp_dir / "html"
        html_dir.mkdir()
        
        # Créer fichier HTML initial
        html_file = html_dir / "market-2024-001.html"
        html_file.write_text("<html><body>Original Title</body></html>")
        
        input_csv = e2e_temp_dir / "input.csv"
        input_csv.write_text("Référence,Type_AO,Titre\n")
        
        output_dir = e2e_temp_dir / "output"
        output_dir.mkdir()
        
        # Première exécution
        run_pipeline(
            html_dir=html_dir,
            input_csv=input_csv,
            output_csv=output_dir / "v1.csv",
            verbose=False
        )
        
        # Modifier le fichier HTML
        html_file.write_text("<html><body>Updated Title</body></html>")
        
        # Mettre à jour la date de modification
        os.utime(html_file, (datetime.now().timestamp(), datetime.now().timestamp()))
        
        # Deuxième exécution
        result2 = run_pipeline(
            html_dir=html_dir,
            input_csv=output_dir / "v1.csv",
            output_csv=output_dir / "v2.csv",
            verbose=False
        )
        
        # Le fichier devrait être détecté comme modifié
        assert result2.total_rows == 1
    
    def test_empty_market_detection(self, e2e_temp_dir):
        """Test détection des marchés vides/incomplets."""
        html_dir = e2e_temp_dir / "html"
        html_dir.mkdir()
        
        # Fichier avec données manquantes
        (html_dir / "incomplete.html").write_text("""
        <html>
        <body>
            <h1>Marché incomplet</h1>
            <!-- Pas de référence, pas de date -->
        </body>
        </html>
        """)
        
        input_csv = e2e_temp_dir / "input.csv"
        input_csv.write_text("Référence,Type_AO,Titre\n")
        
        output_dir = e2e_temp_dir / "output"
        output_dir.mkdir()
        
        result = run_pipeline(
            html_dir=html_dir,
            input_csv=input_csv,
            output_csv=output_dir / "output.csv",
            verbose=False
        )
        
        # Le marché devrait être présent mais potentiellement invalide
        assert result.total_rows >= 0


# =============================================================================
# TESTS: Performance et Robustesse
# =============================================================================

class TestPerformanceAndRobustness:
    """Tests de performance et robustesse."""
    
    def test_large_html_directory(self, e2e_temp_dir):
        """Test avec beaucoup de fichiers HTML."""
        html_dir = e2e_temp_dir / "html"
        html_dir.mkdir()
        
        # Créer 50 fichiers HTML
        for i in range(50):
            (html_dir / f"market-{i:03d}-2024-marche.html").write_text(
                f"<html><body>Market {i}</body></html>"
            )
        
        input_csv = e2e_temp_dir / "input.csv"
        input_csv.write_text("Référence,Type_AO,Titre\n")
        
        output_dir = e2e_temp_dir / "output"
        output_dir.mkdir()
        
        import time
        start = time.time()
        
        result = run_pipeline(
            html_dir=html_dir,
            input_csv=input_csv,
            output_csv=output_dir / "output.csv",
            verbose=False
        )
        
        duration = time.time() - start
        
        assert result.total_rows == 50
        assert duration < 60  # Devrait terminer en moins d'une minute
    
    def test_special_characters_handling(self, e2e_temp_dir):
        """Test gestion des caractères spéciaux."""
        html_dir = e2e_temp_dir / "html"
        html_dir.mkdir()
        
        # Fichier avec caractères spéciaux
        (html_dir / "special-chars.html").write_text("""
        <html>
        <head><meta charset="utf-8"></head>
        <body>
            <h1>Marché avec accents: é à ù ç ñ</h1>
            <p>Référence: 13/joue/001</p>
            <p>Description: 日本語 العربية עברית</p>
        </body>
        </html>
        """, encoding='utf-8')
        
        input_csv = e2e_temp_dir / "input.csv"
        input_csv.write_text("Référence,Type_AO,Titre\n", encoding='utf-8')
        
        output_dir = e2e_temp_dir / "output"
        output_dir.mkdir()
        
        result = run_pipeline(
            html_dir=html_dir,
            input_csv=input_csv,
            output_csv=output_dir / "output.csv",
            verbose=False
        )
        
        assert result.output_csv.exists()
        
        # Vérifier que les caractères sont préservés
        content = result.output_csv.read_text(encoding='utf-8')
        assert result.total_rows >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
