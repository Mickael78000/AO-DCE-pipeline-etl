"""Routeur de détection de source HTML et instanciation d'extracteurs - Version 2."""

from __future__ import annotations

from pathlib import Path
from datetime import datetime

from bs4 import BeautifulSoup

from .base import ExtractionContext, ExtractionResult
from .boamp_xml import BoampExtractor
from .france_marches import FranceMarchesExtractor
from .joue import JoueExtractor
from .marches_online import MarchesOnlineExtractor
from .place_numeric import PlaceNumericExtractor
from ao_etl.models.market import MarketData, SourceType, ExtractionStatus

# Import de la fonction de construction d'URL (quand disponible)
try:
    from ao_etl.pipeline.consolidate import build_market_url
    HAS_BUILD_MARKET_URL = True
except ImportError:
    HAS_BUILD_MARKET_URL = False


def extraction_result_to_market_data(result: ExtractionResult) -> MarketData:
    """
    Pont de conversion: ExtractionResult (V2) → MarketData (Legacy).
    
    Cette fonction permet aux extracteurs V2 de fonctionner avec le pipeline
    legacy qui attend des objets MarketData.
    
    Args:
        result: Résultat d'extraction V2
        
    Returns:
        MarketData compatible avec le pipeline legacy
    """
    # Mapping des types de source
    source_type_map = {
        "PLACE_NUMERIC": SourceType.PLACE_NUMERIC,
        "BOAMP_XML": SourceType.BOAMP_XML,
        "FRANCE_MARCHES": SourceType.FRANCE_MARCHES,
        "MARCHES_ONLINE": SourceType.MARCHES_ONLINE,
        "JOUE": SourceType.BOAMP_XML,  # JOUE mapped to BOAMP for legacy compatibility
        "STANDARD": SourceType.STANDARD,
        "UNKNOWN": SourceType.UNKNOWN,
    }
    
    # Convertir la deadline (string) en datetime si possible
    date_limite = None
    if result.deadline and result.deadline not in ("-", ""):
        try:
            # Essayer plusieurs formats
            for fmt in ["%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d"]:
                try:
                    date_limite = datetime.strptime(result.deadline.strip(), fmt)
                    break
                except ValueError:
                    continue
        except Exception:
            pass
    
    # Convertir l'estimation (string) en float si possible
    estimation_eur = None
    if result.estimation and result.estimation not in ("-", ""):
        try:
            # Extraire les chiffres (ex: "450000 EUR" → 450000)
            import re
            numbers = re.findall(r'\d+', result.estimation.replace(' ', '').replace(',', ''))
            if numbers:
                estimation_eur = float(numbers[0])
        except Exception:
            pass
    
    # Déterminer le statut
    status = ExtractionStatus.SUCCESS if result.confidence >= 70 else ExtractionStatus.PARTIAL
    if not result.title or not result.buyer:
        status = ExtractionStatus.PARTIAL
    if result.review_needed:
        status = ExtractionStatus.PARTIAL
    
    # Construire l'URL source avec build_market_url (si disponible) ou fallback
    url_source = ""
    filename = result.raw.get('filename', '')
    
    if HAS_BUILD_MARKET_URL:
        # Utiliser la fonction complète de consolidate.py
        # Récupérer le HTML brut pour extraction canonical si disponible
        html_content = result.raw.get('html_content', '')
        
        # Essayer d'abord l'URL extraite par l'extracteur
        extracted_url = result.raw.get('url_source', '')
        
        market_url, url_source_type = build_market_url(
            source_file=filename,
            source_platform=result.source_type,
            source_url=extracted_url if extracted_url else None,
            html_content=html_content if html_content else None,
        )
        url_source = market_url or ""
    else:
        # Fallback: utiliser l'URL extraite par l'extracteur
        url_source = result.raw.get('url_source', '')
    
    return MarketData(
        filename=result.raw.get('filename', ''),
        source_type=source_type_map.get(result.source_type, SourceType.UNKNOWN),
        title=result.title,
        reference=result.reference,
        buyer=result.buyer,
        cpv=result.raw.get('cpv_codes', []),
        url_source=url_source,
        location=result.location,
        procedure_type=result.raw.get('procedure_type', ''),
        contract_nature=result.raw.get('contract_nature', ''),
        date_limite=date_limite,
        duree_mois=result.raw.get('duration_months'),
        estimation_eur=estimation_eur,
        status=status,
        extraction_notes=result.extraction_notes,
    )


def extract_for_source(file_path: Path) -> MarketData:
    """
    Extrait les données d'un fichier HTML et retourne un MarketData.

    Fonction canonique d'extraction (anciennement V2).
    
    Args:
        file_path: Chemin du fichier HTML
        
    Returns:
        MarketData prêt pour le pipeline de merge
    """
    try:
        html = file_path.read_text(encoding='utf-8')
        result = extract_from_html(file_path, html)
        return extraction_result_to_market_data(result)
    except Exception as e:
        # Retourner un MarketData d'erreur
        return MarketData(
            filename=file_path.name,
            source_type=SourceType.UNKNOWN,
            status=ExtractionStatus.FAILED,
            extraction_notes=[f"ERROR: {e}"],
        )


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
    
    # 2. JOUE: Journal Officiel de l'Union Européenne (PRIORITAIRE - avant BOAMP)
    # Car les fichiers JOUE peuvent contenir "nom officiel" qui trigger BOAMP
    if (name.startswith("13joue") or 
        "13/joue/" in html_lower or
        "journal officiel de l'union européenne" in text or
        "ted.europa.eu" in html_lower):
        return "JOUE"
    
    # 3. PLACE: format orgAcronyme avec "Détail de la consultation"
    if "orgacronyme" in name or ("détail de la consultation" in text and "heure de paris" in text):
        return "PLACE_NUMERIC"
    
    # 4. BOAMP: structure avec sections numérotées et labels (marches-publics.gouv.fr)
    if ("marches-publics.gouv.fr" in html_lower or 
        ("identifiant interne" in text and 
         "nom officiel" in text and 
         "section 1 -" in text)):
        return "BOAMP_XML"
    
    # 5. France Marchés: texte légal structuré
    if ("intitulé de l'appel d'offre public" in text or 
        "nom et adresse officiels de l'organisme acheteur public" in text or
        "weboramaitemtag" in html_lower):
        return "FRANCE_MARCHES"
    
    # Fallback par patterns de nom de fichier
    if "boamp" in name or name.startswith("3"):
        return "BOAMP_XML"
    
    if "s2d" in name:
        return "PLACE_NUMERIC"
    
    if "joue" in name or name.startswith("13"):
        return "JOUE"
    
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
        "JOUE": JoueExtractor,
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
    result = extractor.extract()
    
    # Stocker le HTML brut et le nom de fichier pour build_market_url
    result.raw['html_content'] = html
    result.raw['filename'] = file_path.name
    
    return result
