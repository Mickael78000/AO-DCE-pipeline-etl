"""
Gestion d'état robuste du pipeline ETL.

Ce module implémente un state machine avec:
- Tracking d'état par phase
- Gestion des erreurs et rollback
- Sauvegarde/restauration d'état
- Validation des transitions
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from contextlib import contextmanager
import traceback

log = logging.getLogger(__name__)


class PhaseStatus(Enum):
    """Statut possible d'une phase du pipeline."""
    PENDING = auto()      # Non démarrée
    RUNNING = auto()      # En cours
    SUCCESS = auto()      # Terminée avec succès
    FAILED = auto()       # Échouée
    SKIPPED = auto()     # Ignorée (optionnelle)
    ROLLED_BACK = auto()  # Rollback effectué


class PipelineError(Exception):
    """Exception de base pour le pipeline."""
    pass


class PhaseError(PipelineError):
    """Exception levée lorsqu'une phase échoue."""
    
    def __init__(self, phase_name: str, message: str, original_error: Optional[Exception] = None):
        self.phase_name = phase_name
        self.original_error = original_error
        super().__init__(f"Phase '{phase_name}' failed: {message}")


class ValidationError(PipelineError):
    """Exception levée lors de la validation."""
    pass


@dataclass
class PhaseState:
    """État d'une phase du pipeline."""
    name: str
    status: PhaseStatus = PhaseStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    stats: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'status': self.status.name,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'error_message': self.error_message,
            'error_traceback': self.error_traceback,
            'stats': self.stats,
            'metadata': self.metadata,
        }


@dataclass  
class PipelineState:
    """État complet du pipeline."""
    pipeline_id: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    phases: Dict[str, PhaseState] = field(default_factory=dict)
    global_metadata: Dict[str, Any] = field(default_factory=dict)
    is_complete: bool = False
    final_success: bool = False
    
    def get_phase(self, name: str) -> PhaseState:
        """Récupère ou crée l'état d'une phase."""
        if name not in self.phases:
            self.phases[name] = PhaseState(name=name)
        return self.phases[name]
    
    def to_dict(self) -> Dict:
        return {
            'pipeline_id': self.pipeline_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'phases': {name: phase.to_dict() for name, phase in self.phases.items()},
            'global_metadata': self.global_metadata,
            'is_complete': self.is_complete,
            'final_success': self.final_success,
        }
    
    def save(self, path: Path) -> None:
        """Sauvegarde l'état dans un fichier JSON."""
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False))
    
    @classmethod
    def load(cls, path: Path) -> 'PipelineState':
        """Charge l'état depuis un fichier JSON."""
        data = json.loads(path.read_text())
        state = cls(
            pipeline_id=data['pipeline_id'],
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            global_metadata=data.get('global_metadata', {}),
            is_complete=data.get('is_complete', False),
            final_success=data.get('final_success', False),
        )
        for name, phase_data in data.get('phases', {}).items():
            phase = PhaseState(
                name=phase_data['name'],
                status=PhaseStatus[phase_data['status']],
                start_time=datetime.fromisoformat(phase_data['start_time']) if phase_data['start_time'] else None,
                end_time=datetime.fromisoformat(phase_data['end_time']) if phase_data['end_time'] else None,
                error_message=phase_data.get('error_message'),
                error_traceback=phase_data.get('error_traceback'),
                stats=phase_data.get('stats', {}),
                metadata=phase_data.get('metadata', {}),
            )
            state.phases[name] = phase
        return state


class PipelineStateManager:
    """
    Gestionnaire d'état du pipeline avec support pour:
    - Tracking d'état par phase
    - Rollback automatique
    - Reprise après erreur
    - Journalisation complète
    """
    
    def __init__(self, pipeline_id: Optional[str] = None, state_dir: Optional[Path] = None):
        self.pipeline_id = pipeline_id or f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.state = PipelineState(pipeline_id=self.pipeline_id)
        self.state_dir = state_dir or Path("reports/state")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        # Callbacks pour rollback
        self._rollback_handlers: Dict[str, List[Callable]] = {}
        self._cleanup_handlers: Dict[str, List[Callable]] = {}
        
        # Fichiers temporaires créés par phase
        self._phase_outputs: Dict[str, List[Path]] = {}
    
    def register_rollback(self, phase_name: str, handler: Callable) -> None:
        """Enregistre un handler de rollback pour une phase."""
        if phase_name not in self._rollback_handlers:
            self._rollback_handlers[phase_name] = []
        self._rollback_handlers[phase_name].append(handler)
    
    def register_cleanup(self, phase_name: str, handler: Callable) -> None:
        """Enregistre un handler de cleanup pour une phase."""
        if phase_name not in self._cleanup_handlers:
            self._cleanup_handlers[phase_name] = []
        self._cleanup_handlers[phase_name].append(handler)
    
    def track_output(self, phase_name: str, path: Path) -> None:
        """Track un fichier de sortie créé par une phase."""
        if phase_name not in self._phase_outputs:
            self._phase_outputs[phase_name] = []
        self._phase_outputs[phase_name].append(path)
    
    @contextmanager
    def run_phase(self, phase_name: str, can_skip: bool = False, can_fail: bool = True):
        """
        Context manager pour exécuter une phase avec gestion d'état.
        
        Args:
            phase_name: Nom de la phase
            can_skip: Si True, la phase peut être ignorée sans échec
            can_fail: Si True, l'échec n'arrête pas le pipeline
        
        Yields:
            PhaseState: L'état de la phase en cours
        
        Raises:
            PhaseError: Si la phase échoue et can_fail=False
        """
        phase = self.state.get_phase(phase_name)
        
        # Vérifier si on peut reprendre
        if phase.status == PhaseStatus.SUCCESS:
            log.info(f"Phase {phase_name} déjà complétée - skip")
            yield phase
            return
        
        phase.status = PhaseStatus.RUNNING
        phase.start_time = datetime.now()
        phase.error_message = None
        phase.error_traceback = None
        
        log.info(f"[START] Phase {phase_name}")
        self._save_state()
        
        try:
            yield phase
            
            phase.status = PhaseStatus.SUCCESS
            phase.end_time = datetime.now()
            self.state.updated_at = datetime.now()
            log.info(f"[SUCCESS] Phase {phase_name} terminée")
            
        except Exception as e:
            phase.status = PhaseStatus.FAILED
            phase.end_time = datetime.now()
            phase.error_message = str(e)
            phase.error_traceback = traceback.format_exc()
            self.state.updated_at = datetime.now()
            
            log.error(f"[FAILED] Phase {phase_name}: {e}")
            
            # Rollback si handlers définis
            self._rollback_phase(phase_name)
            
            if not can_fail:
                raise PhaseError(phase_name, str(e), e)
        
        finally:
            self._save_state()
    
    def _rollback_phase(self, phase_name: str) -> None:
        """Exécute le rollback pour une phase."""
        phase = self.state.get_phase(phase_name)
        
        # Exécuter handlers de rollback
        if phase_name in self._rollback_handlers:
            log.info(f"[ROLLBACK] Phase {phase_name}")
            for handler in self._rollback_handlers[phase_name]:
                try:
                    handler()
                except Exception as e:
                    log.warning(f"Rollback handler failed for {phase_name}: {e}")
        
        # Nettoyer fichiers de sortie
        if phase_name in self._phase_outputs:
            for path in self._phase_outputs[phase_name]:
                if path.exists():
                    try:
                        path.unlink()
                        log.info(f"[CLEANUP] Supprimé: {path}")
                    except Exception as e:
                        log.warning(f"Cannot remove {path}: {e}")
        
        phase.status = PhaseStatus.ROLLED_BACK
    
    def cleanup_all(self) -> None:
        """Nettoie toutes les ressources temporaires."""
        log.info("[CLEANUP] Nettoyage global")
        
        for phase_name in self._phase_outputs:
            if phase_name in self._cleanup_handlers:
                for handler in self._cleanup_handlers[phase_name]:
                    try:
                        handler()
                    except Exception as e:
                        log.warning(f"Cleanup handler failed for {phase_name}: {e}")
    
    def _save_state(self) -> None:
        """Sauvegarde l'état courant."""
        state_file = self.state_dir / f"{self.pipeline_id}.json"
        self.state.save(state_file)
    
    def mark_complete(self, success: bool) -> None:
        """Marque le pipeline comme terminé."""
        self.state.is_complete = True
        self.state.final_success = success
        self.state.updated_at = datetime.now()
        self._save_state()
        
        if success:
            log.info(f"[COMPLETE] Pipeline {self.pipeline_id} terminé avec succès")
        else:
            log.warning(f"[COMPLETE] Pipeline {self.pipeline_id} terminé avec erreurs")
    
    def get_summary(self) -> Dict[str, Any]:
        """Retourne un résumé de l'exécution."""
        phases_summary = []
        for name, phase in self.state.phases.items():
            duration = None
            if phase.start_time and phase.end_time:
                duration = (phase.end_time - phase.start_time).total_seconds()
            
            phases_summary.append({
                'name': name,
                'status': phase.status.name,
                'duration_seconds': duration,
                'has_error': phase.error_message is not None,
            })
        
        return {
            'pipeline_id': self.pipeline_id,
            'is_complete': self.state.is_complete,
            'final_success': self.state.final_success,
            'phases': phases_summary,
            'total_phases': len(phases_summary),
            'successful_phases': sum(1 for p in phases_summary if p['status'] == 'SUCCESS'),
            'failed_phases': sum(1 for p in phases_summary if p['status'] == 'FAILED'),
        }


# =============================================================================
# Decorators pour instrumentation
# =============================================================================

def retry_on_error(max_retries: int = 3, exceptions: tuple = (Exception,)):
    """Décorateur pour réessayer une fonction en cas d'erreur."""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    log.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(0.5 * (attempt + 1))  # Backoff exponentiel
            raise last_error
        return wrapper
    return decorator


def validate_inputs(**validators):
    """
    Décorateur pour valider les inputs d'une fonction.
    
    Exemple:
        @validate_inputs(html_dir=lambda x: x.exists(), min_files=lambda x: x > 0)
        def process(html_dir: Path, min_files: int): ...
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            # Mapper les arguments
            import inspect
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            
            for arg_name, validator in validators.items():
                if arg_name in bound.arguments:
                    value = bound.arguments[arg_name]
                    if not validator(value):
                        raise ValidationError(f"Validation failed for '{arg_name}': {value}")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator
