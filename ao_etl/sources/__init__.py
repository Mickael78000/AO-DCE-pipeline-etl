"""Extracteurs par type de source HTML.

Architecture V2 avec feature flag legacy|v2.

Usage:
    # Par défaut: legacy (prudent tant que non régressé)
    from ao_etl.sources import extract_for_source
    data = extract_for_source(filepath)
    
    # Forcer V2 via variable d'environnement:
    export AO_EXTRACTOR_VERSION=v2
    
    # Forcer V2 via paramètre (prime sur env):
    data = extract_for_source(filepath, version='v2')
"""

import os
from pathlib import Path
from typing import Literal, Optional

from ao_etl.sources.router import detect_source as _detect_source_legacy
from ao_etl.sources.router import extract_for_source as _extract_for_source_legacy
from ao_etl.sources.base import BaseExtractor

# Imports V2
from ao_etl.sources.router_v2 import (
    extract_from_html as _extract_from_html_v2,
    build_context as _build_context_v2,
)
from ao_etl.sources.base_v2 import ExtractionResult


def _get_version_from_env() -> Literal['legacy', 'v2']:
    """Lit la version depuis la variable d'environnement."""
    env_version = os.environ.get('AO_EXTRACTOR_VERSION', 'legacy').lower()
    return 'v2' if env_version == 'v2' else 'legacy'


def extract_for_source(
    filepath: Path,
    version: Optional[Literal['legacy', 'v2']] = None
):
    """Extrait les données d'un fichier HTML avec sélection V1/V2.
    
    Args:
        filepath: Chemin vers le fichier HTML
        version: 'legacy' ou 'v2'. Si None, utilise AO_EXTRACTOR_VERSION env.
                 Le paramètre prime sur la variable d'environnement.
    
    Returns:
        MarketData (legacy) ou ExtractionResult (v2) selon version
    
    Note:
        Par défaut 'legacy' tant que la non-régression n'est pas prouvée.
    """
    # Déterminer la version à utiliser
    effective_version = version or _get_version_from_env()
    
    if effective_version == 'v2':
        # Route vers V2
        html = filepath.read_text(encoding='utf-8', errors='ignore')
        return _extract_from_html_v2(filepath, html)
    else:
        # Route vers legacy (défaut prudent)
        return _extract_for_source_legacy(filepath)


def detect_source(filepath: Path, content: str, version: Optional[Literal['legacy', 'v2']] = None):
    """Détecte le type de source avec sélection V1/V2.
    
    Args:
        filepath: Chemin vers le fichier
        content: Contenu brut HTML
        version: 'legacy' ou 'v2'. Par défaut utilise l'environnement.
    
    Returns:
        SourceType (legacy) ou str (v2) selon version
    """
    effective_version = version or _get_version_from_env()
    
    if effective_version == 'v2':
        from ao_etl.sources.router_v2 import detect_source_type
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')
        return detect_source_type(filepath, content, soup)
    else:
        return _detect_source_legacy(filepath, content)


__all__ = [
    "detect_source",
    "extract_for_source",
    "BaseExtractor",
    # Exports V2 pour usage direct si nécessaire
    "ExtractionResult",
]
