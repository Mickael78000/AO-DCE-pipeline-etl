"""Configuration pytest pour les tests ETL."""

import pytest
from pathlib import Path

# Fixtures globales si nécessaires

@pytest.fixture
def fixtures_dir() -> Path:
    """Retourne le chemin vers le répertoire de fixtures."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def html_ao_dir() -> Path:
    """Retourne le chemin vers le répertoire html_ao réel."""
    return Path(__file__).parent.parent / "html_ao"
