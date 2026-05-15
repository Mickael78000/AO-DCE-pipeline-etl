"""Router de détection et d'extraction par source."""

import re
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

from ao_etl.models.market import MarketData, SourceType
from ao_etl.sources.base import BaseExtractor

# Import des extracteurs spécifiques (à créer)
from ao_etl.sources.france_marches import FranceMarchesExtractor
from ao_etl.sources.marches_online import MarchesOnlineExtractor
from ao_etl.sources.place_numeric import PlaceNumericExtractor
from ao_etl.sources.boamp_xml import BoampXmlExtractor
from ao_etl.sources.standard import StandardExtractor


def detect_source(filepath: Path, content: str) -> SourceType:
    """Détecte le type de source d'un fichier HTML.
    
    La détection se fait par heuristiques sur le nom de fichier et le contenu,
    dans l'ordre de spécificité décroissante.
    
    Args:
        filepath: Chemin vers le fichier HTML
        content: Contenu brut du fichier
        
    Returns:
        Type de source détecté
    """
    name = filepath.name.lower()
    
    # 1. Marchés Online: nom commence par "ao-" ou contient marchesonline.com
    if 'marchesonline.com' in content or name.startswith('ao-'):
        return SourceType.MARCHES_ONLINE
    
    # 2. PLACE numérique: nom contient orgAcronyme ou consultation_depot dans le contenu
    if 'orgacronyme' in name or 'consultation_depot' in content:
        return SourceType.PLACE_NUMERIC
    
    # 3. France Marchés: contient weboramaItemTag avec title_article
    if 'weboramaitemtag' in content.lower() and 'title_article' in content:
        return SourceType.FRANCE_MARCHES
    
    # 4. BOAMP XML: nom commence par "26-" ou contient "boamp"
    if name.startswith('26-') or 'boamp' in name:
        return SourceType.BOAMP_XML
    
    # 5. Fallback: standard
    return SourceType.STANDARD


def get_extractor(filepath: Path, soup: BeautifulSoup, content: str) -> BaseExtractor:
    """Retourne l'extracteur approprié pour le fichier.
    
    Args:
        filepath: Chemin vers le fichier HTML
        soup: Instance BeautifulSoup parsée
        content: Contenu brut du fichier
        
    Returns:
        Instance de l'extracteur approprié
    """
    source_type = detect_source(filepath, content)
    
    extractors = {
        SourceType.FRANCE_MARCHES: FranceMarchesExtractor,
        SourceType.MARCHES_ONLINE: MarchesOnlineExtractor,
        SourceType.PLACE_NUMERIC: PlaceNumericExtractor,
        SourceType.BOAMP_XML: BoampXmlExtractor,
        SourceType.STANDARD: StandardExtractor,
    }
    
    extractor_class = extractors.get(source_type, StandardExtractor)
    return extractor_class(filepath, soup, content)


def extract_for_source(filepath: Path) -> MarketData:
    """Extrait les données d'un fichier HTML en détectant automatiquement la source.
    
    C'est la fonction principale d'extraction qui orchestre:
    1. Lecture du fichier
    2. Parsing BeautifulSoup
    3. Détection de la source
    4. Extraction par l'extracteur approprié
    5. Gestion des alias
    
    Args:
        filepath: Chemin vers le fichier HTML
        
    Returns:
        Données extraites (même partielles en cas d'erreur)
    """
    path = Path(filepath)
    
    try:
        content = path.read_text(encoding='utf-8', errors='ignore')
        soup = BeautifulSoup(content, 'html.parser')
        
        # Détection et création de l'extracteur
        extractor = get_extractor(path, soup, content)
        
        # Extraction
        data = extractor.extract()
        
        return data
        
    except Exception as e:
        # En cas d'erreur, retourner un MarketData minimal avec l'erreur
        return MarketData(
            filename=path.name,
            source_type=SourceType.UNKNOWN,
            status=ExtractionStatus.FAILED,
            extraction_notes=[f"ERREUR: {str(e)}"]
        )


# Import pour ExtractionStatus
from ao_etl.models.market import ExtractionStatus
