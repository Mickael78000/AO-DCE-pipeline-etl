"""Routeur de détection de source HTML et instanciation d'extracteurs - Version 2."""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from .base_v2 import ExtractionContext
from .boamp_xml_v2 import BoampExtractor
from .france_marches_v2 import FranceMarchesExtractor
from .marches_online_v2 import MarchesOnlineExtractor
from .place_numeric_v2 import PlaceNumericExtractor


def detect_source_type(file_path: Path, html: str, soup: BeautifulSoup) -> str:
    """Détecte le type de source HTML.
    
    Args:
        file_path: Chemin du fichier
        html: Contenu brut HTML
        soup: BeautifulSoup parsé
        
    Returns:
        Type de source: PLACE_NUMERIC, BOAMP_XML, FRANCE_MARCHES, MARCHES_ONLINE, UNKNOWN
    """
    text = soup.get_text("\n", strip=True).lower()
    name = file_path.name.lower()
    html_lower = html.lower()
    
    # 1. Marchés Online: PRIORITAIRE - nom de fichier ao-XXX ou patterns spécifiques
    # Doit être avant BOAMP car les fichiers ao- peuvent contenir "nom officiel"
    if (name.startswith("ao-") or
        "marchesonline" in html_lower or
        "marchés online" in html_lower or 
        "infopro-digital" in html_lower or
        "title-avis" in html_lower):
        return "MARCHES_ONLINE"
    
    # 2. PLACE: format orgAcronyme avec "Détail de la consultation"
    if "orgacronyme" in name or ("détail de la consultation" in text and "heure de paris" in text):
        return "PLACE_NUMERIC"
    
    # 3. BOAMP: structure avec sections numérotées et labels (marches-publics.gouv.fr)
    if ("marches-publics.gouv.fr" in html_lower or 
        ("identifiant interne" in text and 
         "nom officiel" in text and 
         "section 1 -" in text)):
        return "BOAMP_XML"
    
    # 4. France Marchés: texte légal structuré
    if ("intitulé de l'appel d'offre public" in text or 
        "nom et adresse officiels de l'organisme acheteur public" in text or
        "weboramaitemtag" in html_lower):
        return "FRANCE_MARCHES"
    
    # Fallback par patterns de nom de fichier
    if "boamp" in name or name.startswith("3"):
        return "BOAMP_XML"
    
    if "s2d" in name:
        return "PLACE_NUMERIC"
    
    return "UNKNOWN"


def get_extractor(context: ExtractionContext):
    """Instancie l'extracteur approprié pour le contexte.
    
    Args:
        context: Contexte d'extraction avec fichier HTML
        
    Returns:
        Instance de BaseExtractor
    """
    source_type = detect_source_type(context.file_path, context.html, context.soup)
    
    mapping = {
        "PLACE_NUMERIC": PlaceNumericExtractor,
        "BOAMP_XML": BoampExtractor,
        "FRANCE_MARCHES": FranceMarchesExtractor,
        "MARCHES_ONLINE": MarchesOnlineExtractor,
    }
    
    extractor_cls = mapping.get(source_type, FranceMarchesExtractor)
    return extractor_cls(context)


def build_context(file_path: Path, html: str) -> ExtractionContext:
    """Construit un contexte d'extraction à partir d'un fichier.
    
    Args:
        file_path: Chemin du fichier HTML
        html: Contenu brut HTML
        
    Returns:
        ExtractionContext prêt à utiliser
    """
    soup = BeautifulSoup(html, "html.parser")
    return ExtractionContext(file_path=file_path, html=html, soup=soup)


def extract_from_html(file_path: Path, html: str):
    """Fonction principale: extrait les données d'un fichier HTML.
    
    Args:
        file_path: Chemin du fichier
        html: Contenu brut HTML
        
    Returns:
        ExtractionResult avec tous les champs extraits
    """
    context = build_context(file_path, html)
    extractor = get_extractor(context)
    return extractor.extract()
