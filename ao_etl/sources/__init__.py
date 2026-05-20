"""Extracteurs HTML par type de source.

Un seul chemin d'extraction (ex-V2). Plus de switch d'environnement.

Usage:
    from ao_etl.sources import extract_for_source, detect_source
    result = extract_for_source(Path('mon_fichier.html'))
"""

from pathlib import Path

from ao_etl.sources.base import BaseExtractor, ExtractionResult, ExtractionContext
from ao_etl.sources.router import (
    extract_for_source as _extract_impl,
    extract_from_html,
    detect_source_type,
    build_context,
)


def extract_for_source(filepath: Path):
    """Extrait les données d'un fichier HTML.

    Returns:
        MarketData (compatible pipeline)
    """
    return _extract_impl(filepath)


def detect_source(filepath: Path, content: str) -> str:
    """Détecte le type de source d'un fichier HTML."""
    from bs4 import BeautifulSoup
    return detect_source_type(filepath, content, BeautifulSoup(content, "html.parser"))


__all__ = [
    "extract_for_source",
    "detect_source",
    "extract_from_html",
    "build_context",
    "BaseExtractor",
    "ExtractionResult",
    "ExtractionContext",
]
