"""Scraper de contenu URL pour enrichissement LLM."""

import logging
import re
import time
from typing import Optional, Dict, Any
from urllib.parse import urlparse

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

log = logging.getLogger(__name__)

# Cache simple pour éviter de re-scraper les mêmes URLs
_url_cache: Dict[str, tuple[str, float]] = {}
_CACHE_TTL = 3600  # 1 heure

# Headers pour simuler un navigateur
_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


def _is_cache_valid(url: str) -> bool:
    """Vérifie si l'URL est en cache et valide."""
    if url not in _url_cache:
        return False
    content, timestamp = _url_cache[url]
    return (time.time() - timestamp) < _CACHE_TTL


def scrape_url(url: str, timeout: int = 10) -> Optional[str]:
    """
    Scrape le contenu HTML d'une URL.
    
    Args:
        url: URL à scraper
        timeout: Timeout en secondes
        
    Returns:
        Contenu HTML ou None si erreur
    """
    if not HAS_REQUESTS:
        log.warning("requests non installé, scraping impossible")
        return None
    
    if not url or not url.startswith("http"):
        return None
    
    # Vérifier le cache
    if _is_cache_valid(url):
        log.debug(f"Cache hit pour {url}")
        return _url_cache[url][0]
    
    try:
        log.info(f"Scraping URL: {url}")
        response = requests.get(
            url,
            headers=_DEFAULT_HEADERS,
            timeout=timeout,
            allow_redirects=True
        )
        response.raise_for_status()
        
        # Vérifier que c'est bien du HTML
        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' not in content_type:
            log.warning(f"Contenu non-HTML: {content_type}")
            return None
        
        content = response.text
        
        # Mettre en cache
        _url_cache[url] = (content, time.time())
        
        log.info(f"✓ Scraping réussi: {len(content)} caractères")
        return content
        
    except requests.exceptions.Timeout:
        log.warning(f"Timeout scraping {url}")
        return None
    except requests.exceptions.HTTPError as e:
        log.warning(f"HTTP error {e.response.status_code} pour {url}")
        return None
    except Exception as e:
        log.warning(f"Erreur scraping {url}: {e}")
        return None


def _extract_relevant_text(html: str, max_length: int = 5000) -> str:
    """Extrait le texte pertinent du HTML pour le LLM."""
    try:
        soup = BeautifulSoup(html, "html.parser")
        
        # Supprimer les éléments non pertinents
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        
        # Extraire le texte
        text = soup.get_text(separator="\n", strip=True)
        
        # Nettoyer les lignes vides multiples
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        text = "\n".join(lines)
        
        # Limiter la taille
        if len(text) > max_length:
            text = text[:max_length] + "\n[... contenu tronqué ...]"
        
        return text
        
    except Exception as e:
        log.warning(f"Erreur extraction texte: {e}")
        return html[:max_length] if len(html) > max_length else html


def _should_scrape(row: Dict[str, Any]) -> bool:
    """Détermine si on doit scraper l'URL (données manquantes)."""
    # Champs à vérifier
    critical_fields = [
        "Estimation_auto", "Estimation_manual", "Estimation du marché",
        "Date_limite_auto", "Date_limite_manual", "Date limite de remise des offres",
        "Localisation_auto", "Localisation_manual", "Localisation",
        "Durée initiale du marché", "Reconduction(s)"
    ]
    
    missing_count = 0
    for field in critical_fields:
        value = row.get(field, "")
        if not value or value in ("-", "", "None", "null"):
            missing_count += 1
    
    # Scraper si au moins 2 champs critiques sont manquants
    return missing_count >= 2


def enrich_row_with_url_content(
    row: Dict[str, Any],
    url_field: str = "URL source HTTPS",
    max_content_length: int = 5000
) -> Dict[str, Any]:
    """
    Enrichit une row avec le contenu scrappé depuis l'URL.
    
    Args:
        row: Dictionnaire de données du marché
        url_field: Nom du champ contenant l'URL
        max_content_length: Longueur maximale du contenu
        
    Returns:
        Row enrichie avec 'url_content' si scraping réussi
    """
    # Copier la row pour ne pas modifier l'original
    enriched = dict(row)
    
    # Vérifier si on a besoin de scraper
    if not _should_scrape(row):
        log.debug("Pas besoin de scraper, données suffisantes")
        return enriched
    
    # Récupérer l'URL
    url = row.get(url_field, "")
    if not url or url in ("-", "", "None"):
        return enriched
    
    # Scraper
    html_content = scrape_url(url)
    if not html_content:
        return enriched
    
    # Extraire le texte pertinent
    relevant_text = _extract_relevant_text(html_content, max_content_length)
    
    # Ajouter à la row
    enriched["_url_scraped_content"] = relevant_text
    enriched["_url_scraped_at"] = time.time()
    
    log.info(f"✓ Row enrichie avec contenu URL: {len(relevant_text)} caractères")
    
    return enriched


def clear_cache():
    """Vide le cache de scraping."""
    global _url_cache
    _url_cache = {}
    log.info("Cache de scraping vidé")
