"""Classe de base pour les extracteurs de source."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

from ao_etl.models.market import MarketData, SourceType


class BaseExtractor(ABC):
    """Classe abstraite pour tous les extracteurs de source.
    
    Chaque extracteur spécifique (France Marchés, Marchés Online, etc.)
    doit hériter de cette classe et implémenter les méthodes abstraites.
    """
    
    source_type: SourceType = SourceType.UNKNOWN
    
    def __init__(self, filepath: Path, soup: BeautifulSoup, content: str):
        """Initialise l'extracteur avec le fichier à traiter.
        
        Args:
            filepath: Chemin vers le fichier HTML
            soup: Instance BeautifulSoup parsée
            content: Contenu brut du fichier (pour regex fallback)
        """
        self.filepath = filepath
        self.soup = soup
        self.content = content
        self.data = MarketData(filename=filepath.name, source_type=self.source_type)
    
    @abstractmethod
    def can_extract(self) -> bool:
        """Vérifie si cet extracteur peut traiter ce fichier.
        
        Returns:
            True si le fichier est compatible avec cet extracteur
        """
        pass
    
    @abstractmethod
    def extract(self) -> MarketData:
        """Extrait toutes les données métier du fichier.
        
        Returns:
            MarketData peuplée avec les données extraites
        """
        pass
    
    def _clean_text(self, text: Optional[str]) -> str:
        """Nettoie le texte extrait (espaces, retours à la ligne).
        
        Args:
            text: Texte brut à nettoyer
            
        Returns:
            Texte nettoyé
        """
        if not text:
            return ""
        # Remplacer les espaces multiples
        cleaned = " ".join(text.split())
        # Supprimer les espaces autour
        return cleaned.strip()
    
    def _decode_unicode_escapes(self, text: str) -> str:
        """Décode les séquences Unicode échappées (\u0022, \u00E9, etc.).
        
        Utilisé principalement pour France Marchés qui encode le JSON
        avec des séquences Unicode.
        
        Args:
            text: Texte avec séquences échappées
            
        Returns:
            Texte décodé
        """
        if not text:
            return ""
        
        import re as _re
        
        def _replace_escape(m):
            try:
                return chr(int(m.group(1), 16))
            except (ValueError, OverflowError):
                return m.group(0)
        
        return _re.sub(r'\\u([0-9A-Fa-f]{4})', _replace_escape, text)
