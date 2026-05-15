"""
Tests pour les cas limites et effets de bord du pipeline.

Ces tests vérifient:
- Comportement avec entrées invalides
- Gestion des erreurs
- Effets de bord (rollback, cleanup)
- Scénarios de concurrence
- Robustesse générale
"""

import pytest
import csv
import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, call
import shutil
import os
import threading
import time

from ao_etl.pipeline.state import (
    PipelineStateManager, PhaseStatus, PhaseError, ValidationError
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_dir():
    """Répertoire temporaire."""
    tmp = Path(tempfile.mkdtemp(prefix="edge_test_"))
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def state_manager(temp_dir):
    """State manager isolé."""
    return PipelineStateManager(
        pipeline_id="edge_test",
        state_dir=temp_dir / "state"
    )


# =============================================================================
# TESTS: Cas Limites (Edge Cases)
# =============================================================================

class TestEdgeCases:
    """Tests pour les cas limites."""
    
    def test_empty_pipeline(self, state_manager):
        """Test pipeline sans phases."""
        state_manager.mark_complete(success=True)
        summary = state_manager.get_summary()
        assert summary["total_phases"] == 0
        assert summary["successful_phases"] == 0
    
    def test_very_long_phase_name(self, state_manager):
        """Test avec nom de phase très long."""
        long_name = "a" * 10000
        
        with state_manager.run_phase(long_name):
            pass
        
        assert long_name in state_manager.state.phases
        assert state_manager.state.phases[long_name].status == PhaseStatus.SUCCESS
    
    def test_unicode_special_characters(self, state_manager, temp_dir):
        """Test avec caractères Unicode complexes."""
        unicode_names = [
            "相位_中文",           # Chinois
            "фаза_русский",      # Russe
            "φάση_ελληνικά",     # Grec
            " phase_🚀_emoji",     # Emoji
            " مرحلة_عربية",       # Arabe
            " שלב_עברית",         # Hébreu
            "フェーズ_日本語",      # Japonais
        ]
        
        for name in unicode_names:
            with state_manager.run_phase(name) as phase:
                phase.metadata["test"] = f"value_{name}"
        
        # Vérifier persistance
        state_manager._save_state()
        from ao_etl.pipeline.state import PipelineState
        loaded = PipelineState.load(state_manager.state_dir / "edge_test.json")
        
        for name in unicode_names:
            assert name in loaded.phases
    
    def test_none_and_falsy_values(self, state_manager):
        """Test avec valeurs falsy."""
        with state_manager.run_phase("falsy_test") as phase:
            phase.stats["none"] = None
            phase.stats["empty_string"] = ""
            phase.stats["zero"] = 0
            phase.stats["false"] = False
            phase.stats["empty_list"] = []
            phase.stats["empty_dict"] = {}
        
        data = state_manager.state.phases["falsy_test"].to_dict()
        assert data["stats"]["none"] is None
        assert data["stats"]["empty_string"] == ""
        assert data["stats"]["zero"] == 0
        assert data["stats"]["false"] is False
    
    def test_nested_exception_handling(self, state_manager):
        """Test gestion d'exceptions imbriquées."""
        try:
            with state_manager.run_phase("outer", can_fail=False):
                try:
                    with state_manager.run_phase("inner", can_fail=False):
                        raise ValueError("Inner error")
                except PhaseError:
                    # Devrait être capturé et converti
                    raise RuntimeError("Outer error")
        except PhaseError as e:
            assert e.phase_name in ["outer", "inner"]
    
    def test_deeply_nested_phases(self, state_manager):
        """Test avec phases profondément imbriquées."""
        depth = 0
        max_depth = 10
        
        def nested_phase(current_depth):
            nonlocal depth
            if current_depth >= max_depth:
                depth = current_depth
                return
            
            with state_manager.run_phase(f"level_{current_depth}"):
                nested_phase(current_depth + 1)
        
        nested_phase(0)
        assert depth == max_depth
        assert len(state_manager.state.phases) == max_depth + 1
    
    def test_rapid_phase_transitions(self, state_manager):
        """Test transitions rapides entre phases."""
        for i in range(100):
            with state_manager.run_phase(f"rapid_{i}"):
                pass
        
        assert len(state_manager.state.phases) == 100
        assert all(
            p.status == PhaseStatus.SUCCESS 
            for p in state_manager.state.phases.values()
        )


# =============================================================================
# TESTS: Effets de Bord (Side Effects)
# =============================================================================

class TestSideEffects:
    """Tests pour les effets de bord."""
    
    def test_rollback_creates_no_output(self, state_manager, temp_dir):
        """Test que le rollback supprime les fichiers créés."""
        output_file = temp_dir / "should_not_exist.txt"
        
        def rollback_handler():
            pass
        
        state_manager.register_rollback("rollback_test", rollback_handler)
        
        try:
            with state_manager.run_phase("rollback_test", can_fail=False):
                output_file.write_text("temporary")
                state_manager.track_output("rollback_test", output_file)
                raise ValueError("Trigger rollback")
        except PhaseError:
            pass
        
        assert not output_file.exists()
    
    def test_rollback_order(self, state_manager):
        """Test ordre d'exécution des handlers de rollback."""
        execution_order = []
        
        def handler1():
            execution_order.append("handler1")
        
        def handler2():
            execution_order.append("handler2")
        
        def handler3():
            execution_order.append("handler3")
        
        state_manager.register_rollback("ordered", handler1)
        state_manager.register_rollback("ordered", handler2)
        state_manager.register_rollback("ordered", handler3)
        
        try:
            with state_manager.run_phase("ordered", can_fail=False):
                raise ValueError("Trigger")
        except PhaseError:
            pass
        
        assert execution_order == ["handler1", "handler2", "handler3"]
    
    def test_cleanup_all_handlers_called(self, state_manager):
        """Test que tous les handlers de cleanup sont appelés."""
        cleanup_called = []
        
        for i in range(5):
            def make_handler(idx):
                return lambda: cleanup_called.append(f"handler_{idx}")
            
            state_manager.register_cleanup(f"phase_{i}", make_handler(i))
            with state_manager.run_phase(f"phase_{i}"):
                pass
        
        state_manager.cleanup_all()
        
        assert len(cleanup_called) == 5
        assert all(f"handler_{i}" in cleanup_called for i in range(5))
    
    def test_cleanup_failure_continues(self, state_manager):
        """Test que le cleanup continue même si un handler échoue."""
        cleanup_order = []
        
        def failing_handler():
            cleanup_order.append("failing")
            raise RuntimeError("Cleanup error")
        
        def success_handler():
            cleanup_order.append("success")
        
        state_manager.register_cleanup("test", failing_handler)
        state_manager.register_cleanup("test", success_handler)
        
        with state_manager.run_phase("test"):
            pass
        
        state_manager.cleanup_all()
        
        assert "failing" in cleanup_order
        assert "success" in cleanup_order
    
    def test_multiple_output_files_cleanup(self, state_manager, temp_dir):
        """Test cleanup de multiples fichiers de sortie."""
        files = [temp_dir / f"output_{i}.txt" for i in range(10)]
        
        try:
            with state_manager.run_phase("multi_output", can_fail=False):
                for i, f in enumerate(files):
                    f.write_text(f"content_{i}")
                    state_manager.track_output("multi_output", f)
                raise ValueError("Trigger cleanup")
        except PhaseError:
            pass
        
        assert all(not f.exists() for f in files)
    
    def test_file_permissions_during_cleanup(self, state_manager, temp_dir):
        """Test gestion des permissions de fichiers."""
        output_file = temp_dir / "readonly.txt"
        output_file.write_text("content")
        
        # Rendre le fichier en lecture seule
        os.chmod(output_file, 0o444)
        
        try:
            with state_manager.run_phase("readonly_test", can_fail=False):
                state_manager.track_output("readonly_test", output_file)
                raise ValueError("Trigger")
        except PhaseError:
            pass
        
        # Restaurer les permissions pour le cleanup
        os.chmod(output_file, 0o644)


# =============================================================================
# TESTS: Robustesse et Résilience
# =============================================================================

class TestRobustness:
    """Tests de robustesse."""
    
    def test_concurrent_state_managers(self, temp_dir):
        """Test isolation entre state managers concurrents."""
        results = {}
        
        def worker(worker_id):
            manager = PipelineStateManager(
                pipeline_id=f"worker_{worker_id}",
                state_dir=temp_dir / f"state_{worker_id}"
            )
            
            with manager.run_phase("work"):
                manager.state.global_metadata["worker"] = worker_id
            
            manager.mark_complete(success=True)
            results[worker_id] = manager.state.global_metadata["worker"]
        
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert all(results[i] == i for i in range(5))
    
    def test_disk_full_simulation(self, state_manager, temp_dir):
        """Test comportement quand le disque est plein (simulé)."""
        with patch.object(Path, 'write_text', side_effect=OSError("No space left on device")):
            try:
                with state_manager.run_phase("disk_full", can_fail=True):
                    state_manager._save_state()
            except:
                pass
        
        # Le pipeline devrait continuer même si la sauvegarde échoue
        assert state_manager.state.phases["disk_full"].status == PhaseStatus.FAILED
    
    def test_corrupted_state_recovery(self, temp_dir):
        """Test récupération après fichier d'état corrompu."""
        state_file = temp_dir / "corrupted.json"
        state_file.write_text("NOT VALID JSON {{{")
        
        from ao_etl.pipeline.state import PipelineState
        
        with pytest.raises(json.JSONDecodeError):
            PipelineState.load(state_file)
    
    def test_phase_timeout_simulation(self, state_manager):
        """Test gestion de timeout de phase."""
        with state_manager.run_phase("slow_phase", can_fail=True):
            time.sleep(0.1)  # Simuler une opération lente
        
        phase = state_manager.state.phases["slow_phase"]
        assert phase.status == PhaseStatus.SUCCESS
        assert phase.end_time > phase.start_time
    
    def test_memory_pressure(self, state_manager):
        """Test avec beaucoup de données en mémoire."""
        with state_manager.run_phase("memory_test") as phase:
            # Créer beaucoup de métadonnées
            for i in range(10000):
                phase.metadata[f"key_{i}"] = f"value_{i}" * 100
        
        assert len(state_manager.state.phases["memory_test"].metadata) == 10000
        
        # Vérifier que ça persiste
        state_manager._save_state()


# =============================================================================
# TESTS: Scénarios d'Erreur Complexes
# =============================================================================

class TestComplexErrorScenarios:
    """Tests pour scénarios d'erreur complexes."""
    
    def test_partial_failure_continues(self, state_manager):
        """Test que le pipeline continue après échec partiel."""
        # Phase 1: Succès
        with state_manager.run_phase("phase1"):
            pass
        
        # Phase 2: Échec mais continue
        with state_manager.run_phase("phase2", can_fail=True):
            raise ValueError("Phase 2 failed")
        
        # Phase 3: Succès
        with state_manager.run_phase("phase3"):
            pass
        
        # Phase 4: Échec mais continue
        with state_manager.run_phase("phase4", can_fail=True):
            raise RuntimeError("Phase 4 failed")
        
        # Phase 5: Succès
        with state_manager.run_phase("phase5"):
            pass
        
        summary = state_manager.get_summary()
        assert summary["successful_phases"] == 3
        assert summary["failed_phases"] == 2
    
    def test_cascading_rollback(self, state_manager, temp_dir):
        """Test rollback en cascade après échec."""
        rollback_order = []
        
        # Phases avec handlers de rollback
        for i in range(5):
            def make_rollback(idx):
                return lambda: rollback_order.append(f"rollback_{idx}")
            
            state_manager.register_rollback(f"phase_{i}", make_rollback(i))
        
        # Exécuter phases 0-2 avec succès
        for i in range(3):
            with state_manager.run_phase(f"phase_{i}"):
                pass
        
        # Phase 3 échoue
        try:
            with state_manager.run_phase("phase_3", can_fail=False):
                raise ValueError("Phase 3 error")
        except PhaseError:
            pass
        
        # Seul le phase_3 devrait avoir rollback
        assert "rollback_3" in rollback_order
        assert "rollback_0" not in rollback_order  # Les phases précédentes ne rollback pas
    
    def test_retry_exhaustion(self, state_manager):
        """Test épuisement des retries."""
        attempts = 0
        
        from ao_etl.pipeline.state import retry_on_error
        
        @retry_on_error(max_retries=3, exceptions=(ValueError,))
        def always_fails():
            nonlocal attempts
            attempts += 1
            raise ValueError(f"Attempt {attempts}")
        
        with pytest.raises(ValueError):
            always_fails()
        
        assert attempts == 3
    
    def test_retry_with_partial_success(self, state_manager):
        """Test retry avec succès partiel."""
        attempts = 0
        
        from ao_etl.pipeline.state import retry_on_error
        
        @retry_on_error(max_retries=5, exceptions=(ValueError,))
        def succeeds_on_third():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ValueError(f"Attempt {attempts}")
            return f"Success on attempt {attempts}"
        
        result = succeeds_on_third()
        
        assert result == "Success on attempt 3"
        assert attempts == 3


# =============================================================================
# TESTS: Validation d'Intégrité
# =============================================================================

class TestIntegrity:
    """Tests d'intégrité des données."""
    
    def test_state_consistency_after_failure(self, state_manager):
        """Test cohérence de l'état après échec."""
        # Exécuter plusieurs phases
        with state_manager.run_phase("success1"):
            pass
        
        try:
            with state_manager.run_phase("failure", can_fail=False):
                raise ValueError("Error")
        except PhaseError:
            pass
        
        with state_manager.run_phase("success2"):
            pass
        
        # Vérifier cohérence
        assert state_manager.state.phases["success1"].status == PhaseStatus.SUCCESS
        assert state_manager.state.phases["failure"].status == PhaseStatus.FAILED
        assert state_manager.state.phases["success2"].status == PhaseStatus.SUCCESS
        
        assert state_manager.state.phases["failure"].error_message is not None
        assert state_manager.state.phases["failure"].error_traceback is not None
    
    def test_timestamp_consistency(self, state_manager):
        """Test cohérence des timestamps."""
        with state_manager.run_phase("timestamp_test") as phase:
            time.sleep(0.01)  # Petite pause
        
        phase = state_manager.state.phases["timestamp_test"]
        assert phase.start_time is not None
        assert phase.end_time is not None
        assert phase.end_time >= phase.start_time
    
    def test_no_orphan_state_files(self, temp_dir):
        """Test qu'il n'y a pas de fichiers d'état orphelins."""
        # Créer plusieurs state managers
        managers = []
        for i in range(10):
            m = PipelineStateManager(
                pipeline_id=f"orphan_test_{i}",
                state_dir=temp_dir / "states"
            )
            with m.run_phase("test"):
                pass
            m.mark_complete(success=True)
            managers.append(m)
        
        # Vérifier qu'il y a exactement 10 fichiers
        state_files = list((temp_dir / "states").glob("*.json"))
        assert len(state_files) == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
