"""
ao_etl/clean_html.py — Nettoyage préliminaire des fichiers HTML.
Fonctions pures qui nettoient le HTML brut avant parsing BeautifulSoup.
Objectif : réduire le bruit (scripts, styles, JSON embarqué, tracking)
pour améliorer la précision de l'extraction métier.
"""

import re
import logging
from pathlib import Path

log = logging.getLogger(__name__)


# Patterns pour éliminer le bruit HTML
_NOISE_PATTERNS = [
    # Scripts JavaScript (y compris JSON embarqué dans scripts)
    (re.compile(r'<script[^>]*>.*?</script>', re.DOTALL | re.IGNORECASE), ''),
    # Styles CSS
    (re.compile(r'<style[^>]*>.*?</style>', re.DOTALL | re.IGNORECASE), ''),
    # Noscript tags
    (re.compile(r'<noscript[^>]*>.*?</noscript>', re.DOTALL | re.IGNORECASE), ''),
    # SVG icons
    (re.compile(r'<svg[^>]*>.*?</svg>', re.DOTALL | re.IGNORECASE), ''),
    # Commentaires HTML
    (re.compile(r'<!--.*?-->', re.DOTALL), ''),
    # Data attributes JSON (weborama, etc)
    (re.compile(r'var\s+weboramaItemTag\s*=\s*JSON\.parse\([^)]+\);', re.DOTALL), ''),
    # GTM dataLayer avec JSON
    (re.compile(r"dataLayer\.push\([^)]+JSON\.parse[^)]+\);", re.DOTALL | re.IGNORECASE), ''),
    # Tracking pixels / images 1x1
    (re.compile(r'<img[^>]*(?:width=["\']?1["\']?[^>]*height=["\']?1["\']?|height=["\']?1["\']?[^>]*width=["\']?1["\']?)[^>]*>', re.IGNORECASE), ''),
]

# Patterns pour nettoyer le texte extrait
_TEXT_CLEAN_PATTERNS = [
    # URLs longues collées
    (re.compile(r'https?://[^\s<>"\']{50,}'), ' '),
    # Slugs techniques (base64, tokens)
    (re.compile(r'[a-zA-Z0-9_-]{50,}'), ' '),
    # Séquences d'espaces multiples
    (re.compile(r'\s{3,}'), '   '),
]


def clean_html_content(raw_html: str) -> str:
    """
    Nettoie le contenu HTML brut en éliminant le bruit non-métier.
    Retourne le HTML nettoyé prêt pour BeautifulSoup.
    """
    if not raw_html:
        return ""

    # Éliminer les balises de bruit
    cleaned = raw_html
    for pattern, replacement in _NOISE_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)

    # Limiter les lignes vides multiples
    cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)

    return cleaned


def clean_extracted_text(text: str) -> str:
    """
    Nettoie le texte après extraction BeautifulSoup.
    Élimine les artefacts de parsing et le bruit résiduel.
    """
    if not text:
        return ""

    cleaned = text

    # Appliquer les patterns de nettoyage
    for pattern, replacement in _TEXT_CLEAN_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)

    # Normaliser les sauts de ligne
    cleaned = re.sub(r'[ \t]*\n[ \t]*', '\n', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

    # Trim
    cleaned = cleaned.strip()

    return cleaned


def read_and_clean_html(filepath: Path) -> tuple[str, str]:
    """
    Lit un fichier HTML et applique le nettoyage complet.
    Retourne (raw_original, cleaned_html).
    """
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            raw = f.read()
    except Exception as e:
        log.error("Erreur lecture %s: %s", filepath, e)
        return "", ""

    cleaned = clean_html_content(raw)
    log.debug("HTML nettoyé: %s (%d → %d caractères)", filepath.name, len(raw), len(cleaned))

    return raw, cleaned
