"""Utilitaires de traitement de texte pour les scripts AO-DCE."""

import re
import unicodedata
from typing import List


def strip_accents(text: str) -> str:
    """
    Supprime les accents d'une chaîne.
    
    Args:
        text: Texte à traiter
        
    Returns:
        Texte sans accents
    """
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize(text: str) -> str:
    """
    Normalise un texte pour la comparaison:
    - Minuscules
    - Sans accents
    - Espaces normalisés
    
    Args:
        text: Texte à normaliser
        
    Returns:
        Texte normalisé
    """
    if not text:
        return ""
    return " ".join(strip_accents(text).lower().split())


def contains_any(haystack: str, keywords: List[str], use_norm: bool = True) -> bool:
    """
    Vérifie si le texte contient l'un des mots-clés.
    
    Args:
        haystack: Texte à analyser
        keywords: Liste de mots-clés à chercher
        use_norm: Si True, normalise les deux chaînes avant comparaison
        
    Returns:
        True si un mot-clé est trouvé
    """
    if use_norm:
        haystack_norm = normalize(haystack)
        keywords_norm = [normalize(k) for k in keywords]
    else:
        haystack_norm = haystack
        keywords_norm = keywords
    
    return any(kw in haystack_norm for kw in keywords_norm)


def starts_with_any(haystack: str, prefixes: List[str], use_norm: bool = True) -> bool:
    """
    Vérifie si le texte commence par l'un des préfixes.
    
    Args:
        haystack: Texte à analyser
        prefixes: Liste de préfixes à tester
        use_norm: Si True, normalise les deux chaînes avant comparaison
        
    Returns:
        True si un préfixe correspond
    """
    if use_norm:
        haystack_norm = normalize(haystack)
        prefixes_norm = [normalize(p) for p in prefixes]
    else:
        haystack_norm = haystack
        prefixes_norm = prefixes
    
    return any(haystack_norm.startswith(p) for p in prefixes_norm)


def normalize_keywords(keywords: List[str]) -> List[str]:
    """
    Normalise une liste de mots-clés en une seule opération.
    
    Args:
        keywords: Liste de mots-clés
        
    Returns:
        Liste de mots-clés normalisés
    """
    return [normalize(k) for k in keywords]


def extract_pattern(text: str, pattern: str, group: int = 1, flags: int = re.IGNORECASE) -> str:
    """
    Extrait un pattern regex du texte.
    
    Args:
        text: Texte source
        pattern: Pattern regex
        group: Numéro du groupe à extraire
        flags: Flags regex
        
    Returns:
        Texte extrait ou chaîne vide
    """
    if not text:
        return ""
    match = re.search(pattern, text, flags)
    if match and len(match.groups()) >= group:
        return match.group(group).strip()
    return ""


def clean_whitespace(text: str) -> str:
    """Normalise les espaces dans un texte."""
    if not text:
        return ""
    return " ".join(text.split())
