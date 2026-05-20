"""Construction déterministe des URLs de marchés publics.

Ce module fournit des fonctions pour construire ou reconstruire les URLs
publiques des marchés à partir de différentes sources (fichiers HTML,
URLs extraites, patterns de noms de fichiers).

Aucune dépendance LLM - extraction 100% déterministe.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

# Regex patterns pour extraction d'URLs
_PLACE_NUMERIC_RE = re.compile(r"^(\d+\?orgAcronyme=[a-z0-9]+)\.html$", re.IGNORECASE)
_PLACE_NUMERIC_ALT_RE = re.compile(r"^(\d+)-orgAcronyme-([a-z0-9]+)\.html$", re.IGNORECASE)
_CANONICAL_RE = re.compile(r'<link[^>]+rel=\s*["\']canonical["\'][^>]+href=\s*["\']([^"\']+)["\']', re.IGNORECASE)


def _extract_canonical_url(html_content: Optional[str]) -> Optional[str]:
    """Extrait l'URL canonique depuis la balise <link rel="canonical"> du HTML."""
    if not html_content:
        return None
    m = _CANONICAL_RE.search(html_content)
    if m:
        url = m.group(1).strip()
        # Vérifier que c'est une URL absolue valide
        if url.startswith("http://") or url.startswith("https://"):
            return url
    return None


def _is_reliable_url(url: Optional[str]) -> bool:
    """Vérifie si une URL est complète et fiable."""
    if not url:
        return False
    if url in ("-", "None", "none", ""):
        return False
    return url.startswith("http://") or url.startswith("https://")


def build_market_url(
    source_file: str,
    source_platform: str,
    source_url: Optional[str] = None,
    html_content: Optional[str] = None,
) -> tuple[Optional[str], str]:
    """Construit l'URL publique canonique du marché de façon déterministe.

    Returns:
        Tuple (url, source_type) où source_type indique la provenance :
        - 'source_url' : URL fiable fournie en entrée
        - 'canonical' : URL extraite de la balise <link rel="canonical">
        - 'fallback_francemarches' : URL reconstruite pour France Marchés
        - 'fallback_place' : URL reconstruite pour PLACE
        - '' : URL non déterminée

    Priorité générale :
    1. Si source_url existe et est une URL complète fiable → l'utiliser
    2. Sinon, si le HTML source est disponible → chercher <link rel="canonical" href="...">
    3. Sinon, appliquer un fallback déterministe spécifique à la plateforme
    4. Sinon, retourner (None, '') (le caller ajoutera missing_market_url à quality_flags)

    Règles par plateforme :

    FRANCE_MARCHES:
    - Chercher d'abord la balise canonical dans le HTML
    - Si absente, fallback sûr : retirer .html du source_file, préfixer avec
      https://www.francemarches.com/appel-offre/

    MARCHES_ONLINE:
    - Ne jamais reconstruire l'URL à partir du seul nom de fichier ao-XXXXXXX-1.html
    - Si source_url existe et est fiable → l'utiliser
    - Sinon, si le HTML contient une balise canonical → utiliser cette valeur
    - Sinon retourner (None, '')

    PLACE_NUMERIC:
    - Si source_url existe et est fiable → l'utiliser
    - Sinon, si le HTML contient une canonical → l'utiliser
    - Sinon fallback par pattern sur source_file :
      * 2956468-orgAcronyme-g7h.html ou 2956468?orgAcronyme=g7h.html
      * devient https://www.marches-publics.gouv.fr/app.php/entreprise/consultation/2956468?orgAcronyme=g7h

    BOAMP_XML:
    - Si source_url existe et est fiable → l'utiliser
    - Sinon, si le HTML contient une canonical ou une URL publique explicite → l'utiliser
    - Sinon retourner (None, '')

    JOUE:
    - Si source_url existe et est fiable → l'utiliser
    - Sinon, si le HTML contient une canonical → l'utiliser
    - Sinon fallback JOUE/TED: construire depuis le nom de fichier
      * Pattern: 13joueXXXXXXXX-YYYY-...
    """
    sf = (source_file or "").strip()
    platform = (source_platform or "").upper()
    existing = (source_url or "").strip()

    # Normalise les valeurs vides/génériques héritées du CSV
    if existing in ("-", "None", "none"):
        existing = ""

    # Extraction canonique du HTML (si disponible)
    canonical_url = _extract_canonical_url(html_content)

    # ── FRANCE_MARCHES ──
    if platform == "FRANCE_MARCHES":
        # 1. source_url fiable ?
        if _is_reliable_url(existing):
            return existing, "source_url"
        # 2. canonical dans HTML ?
        if canonical_url:
            return canonical_url, "canonical"
        # 3. Fallback sûr : retirer .html et préfixer
        if sf.endswith(".html"):
            slug = sf[:-5]
            return f"https://www.francemarches.com/appel-offre/{slug}", "fallback_francemarches"
        return None, ""

    # ── MARCHES_ONLINE ──
    if platform == "MARCHES_ONLINE":
        # 1. source_url fiable ?
        if _is_reliable_url(existing):
            return existing, "source_url"
        # 2. canonical dans HTML ? (ex: ao-9597894-1.html contient le slug titre)
        if canonical_url:
            return canonical_url, "canonical"
        # 3. Ne jamais reconstruire à partir du nom de fichier seul
        return None, ""

    # ── PLACE_NUMERIC ──
    if platform == "PLACE_NUMERIC":
        # 1. source_url fiable ?
        if _is_reliable_url(existing):
            return existing, "source_url"
        # 2. canonical dans HTML ?
        if canonical_url:
            return canonical_url, "canonical"
        # 3. Fallback par pattern sur source_file
        # Pattern 1: 2956468?orgAcronyme=g7h.html
        m = _PLACE_NUMERIC_RE.match(sf)
        if m:
            query_part = m.group(1)
            return (
                f"https://www.marches-publics.gouv.fr/"
                f"app.php/entreprise/consultation/{query_part}"
            ), "fallback_place"
        # Pattern 2: 2956468-orgAcronyme-g7h.html
        m = _PLACE_NUMERIC_ALT_RE.match(sf)
        if m:
            id_part = m.group(1)
            org_part = m.group(2)
            return (
                f"https://www.marches-publics.gouv.fr/"
                f"app.php/entreprise/consultation/{id_part}?orgAcronyme={org_part}"
            ), "fallback_place"
        return None, ""

    # ── BOAMP_XML ──
    if platform == "BOAMP_XML":
        # 1. source_url fiable ?
        if _is_reliable_url(existing):
            return existing, "source_url"
        # 2. canonical dans HTML ou URL publique explicite ?
        if canonical_url:
            return canonical_url, "canonical"
        # 3. Fallback BOAMP: construire depuis le nom de fichier si pattern boamp
        if "boamp" in sf.lower():
            # Extraire l'ID du nom de fichier
            m = re.search(r'(\d+)', sf)
            if m:
                boamp_id = m.group(1)
                return f"https://www.boamp.fr/avis/detail/{boamp_id}", "fallback_boamp"
        return None, ""

    # ── JOUE ──
    if platform == "JOUE":
        # 1. source_url fiable ?
        if _is_reliable_url(existing):
            return existing, "source_url"
        # 2. canonical dans HTML ?
        if canonical_url:
            return canonical_url, "canonical"
        # 3. Fallback JOUE/TED: construire depuis le nom de fichier
        # Pattern: 13joueXXXXXXXX-YYYY-...
        m = re.match(r"13joue(\d{8,12})", sf, re.I)
        if m:
            numero = m.group(1)
            # Format TED: 2026/S 123-456789
            if len(numero) >= 10:
                annee = numero[:2] if numero.startswith('20') else numero[2:4]
                return f"https://ted.europa.eu/udl?uri=TED:NOTICE:{numero}-20{annee}:TEXT:FR", "fallback_joue"
        return None, ""

    # ── Plateformes non reconnues : source_url si fiable, sinon None ──
    if _is_reliable_url(existing):
        return existing, "source_url"
    return None, ""
