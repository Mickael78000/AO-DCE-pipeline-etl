"""Pont d'intégration entre le nouveau système sources/ et le legacy.

Ce module permet d'utiliser les nouveaux extracteurs modulaires
avec le pipeline legacy existant (detect.py, extract.py).
"""

from pathlib import Path
from typing import Optional

from ao_etl.sources.router import extract_for_source
from ao_etl.models.market import MarketData


def extract_record(html_path: Path) -> dict:
    """Extrait les données d'un fichier HTML au format legacy (dict).
    
    Cette fonction fait le pont entre le nouveau système MarketData
    et l'ancien format dict attendu par le pipeline legacy.
    
    Args:
        html_path: Chemin vers le fichier HTML
        
    Returns:
        Dictionnaire au format attendu par detect.py/extract.py legacy
    """
    data = extract_for_source(html_path)
    
    # Conversion MarketData → dict legacy
    return {
        "filename": data.filename,
        "filepath": str(html_path),
        "source_type": data.source_type.value,
        "title": data.title,
        "reference": data.reference,
        "buyer": data.buyer,
        "cpv_codes": data.cpv,
        "url_source": data.url_source,
        "location": data.location,
        "date_publication": data.date_publication,
        "date_limite": data.date_limite,
        "duree_mois": data.duree_mois,
        "estimation_eur": data.estimation_eur,
        "is_alias": data.is_alias,
        "alias_of": data.alias_of,
        "status": data.status.name,
        "extraction_notes": data.extraction_notes,
    }


def extract_record_new(html_path: Path) -> MarketData:
    """Version moderne retournant directement MarketData.
    
    À utiliser pour les nouveaux développements.
    """
    return extract_for_source(html_path)


def should_use_new_extractor(html_path: Path) -> bool:
    """Détermine si le nouveau système doit être utilisé pour ce fichier.
    
    Stratégie:
    - Toujours utiliser le nouveau système pour Marchés Online (bug 1838554 corrigé)
    - Toujours utiliser pour France Marchés (Unicode décodé)
    - Laisser legacy pour les autres sources pendant la transition
    
    Args:
        html_path: Chemin vers le fichier HTML
        
    Returns:
        True si le nouveau système doit être utilisé
    """
    data = extract_for_source(html_path)
    
    # Utiliser le nouveau système pour les sources corrigées
    return data.source_type.value in {
        "MARCHES_ONLINE",  # Bug 1838554 corrigé
        "FRANCE_MARCHES",  # Unicode décodé
    }


class ExtractionResult:
    """Wrapper unifié pour les résultats d'extraction (legacy + nouveau).
    
    Permet une transition graduelle entre les deux systèmes.
    """
    
    def __init__(self, market_data: MarketData):
        self._data = market_data
    
    @property
    def filename(self) -> str:
        return self._data.filename
    
    @property
    def reference(self) -> str:
        return self._data.reference
    
    @property
    def title(self) -> str:
        return self._data.title
    
    @property
    def buyer(self) -> str:
        return self._data.buyer
    
    @property
    def cpv_codes(self) -> list:
        return self._data.cpv
    
    @property
    def source_type(self) -> str:
        return self._data.source_type.value
    
    def to_dict(self) -> dict:
        """Export au format legacy."""
        return {
            "filename": self._data.filename,
            "title": self._data.title,
            "reference": self._data.reference,
            "buyer": self._data.buyer,
            "cpv_codes": self._data.cpv,
            "source_type": self._data.source_type.value,
            "is_alias": self._data.is_alias,
            "alias_of": self._data.alias_of,
        }
    
    def __repr__(self) -> str:
        return f"ExtractionResult({self._data.filename}: {self._data.reference})"


def unified_extract(html_path: Path, prefer_new: bool = False) -> ExtractionResult:
    """Extraction unifiée utilisant le meilleur système disponible.
    
    Args:
        html_path: Chemin vers le fichier HTML
        prefer_new: Si True, toujours utiliser le nouveau système
        
    Returns:
        ExtractionResult wrapper
    """
    if prefer_new or should_use_new_extractor(html_path):
        data = extract_for_source(html_path)
    else:
        # Fallback sur legacy (à implémenter si nécessaire)
        data = extract_for_source(html_path)  # Par défaut, nouveau système
    
    return ExtractionResult(data)
