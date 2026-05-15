"""Configuration centralisée des chemins pour les scripts AO-DCE."""

from pathlib import Path
from dataclasses import dataclass
from typing import Optional


# ============================================================================
# BASE PATHS
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "output"
INPUT_DIR = DATA_DIR / "input"
HTML_DIR = DATA_DIR / "raw" / "html"


# ============================================================================
# DEFAULT FILENAMES
# ============================================================================

DEFAULT_CSV_INPUT = "AO-completed.csv"
DEFAULT_PIPELINE_OUTPUT = "AO-pipeline-v2.csv"
DEFAULT_CONSOLIDATED = "final-v3-consolidated.csv"
DEFAULT_CLASSIFIED_RULE = "final-v3-consolidated-classified-rule.csv"
DEFAULT_CLASSIFIED_LLM = "final-v3-consolidated-classified-llm.csv"
DEFAULT_JURIDIQUE = "final-v4-juridique.csv"


@dataclass
class ProjectPaths:
    """Chemins configurables pour les scripts."""
    
    project_root: Path = PROJECT_ROOT
    data_dir: Path = DATA_DIR
    output_dir: Path = OUTPUT_DIR
    input_dir: Path = INPUT_DIR
    html_dir: Path = HTML_DIR
    
    def get_input_csv(self, filename: Optional[str] = None) -> Path:
        """Retourne le chemin du CSV d'entrée."""
        name = filename or DEFAULT_CSV_INPUT
        return self.input_dir / name
    
    def get_output_csv(self, filename: str) -> Path:
        """Retourne le chemin d'un CSV de sortie."""
        return self.output_dir / filename
    
    def get_html_dir(self) -> Path:
        """Retourne le répertoire des fichiers HTML."""
        return self.html_dir


def get_project_root() -> Path:
    """Retourne la racine du projet."""
    return PROJECT_ROOT


def get_data_path(subpath: str = "") -> Path:
    """Retourne un chemin dans le répertoire data."""
    path = DATA_DIR
    if subpath:
        path = path / subpath
    return path


def get_output_path(filename: str) -> Path:
    """Retourne le chemin complet d'un fichier de sortie."""
    return OUTPUT_DIR / filename


def get_input_path(filename: str) -> Path:
    """Retourne le chemin complet d'un fichier d'entrée."""
    return INPUT_DIR / filename


def get_html_dir() -> Path:
    """Retourne le répertoire des fichiers HTML."""
    return HTML_DIR


def ensure_dir(path: Path) -> Path:
    """S'assure que le répertoire existe et retourne le chemin."""
    path.mkdir(parents=True, exist_ok=True)
    return path
