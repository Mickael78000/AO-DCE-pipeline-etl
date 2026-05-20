"""Module de validation et scoring pour l'extraction de données - Version 2."""

from __future__ import annotations

import re
from typing import Iterable

from .base_v2 import FieldCandidate, ExtractionTrace

# =============================================================================
# BLACKLISTS - Titres génériques à rejeter
# =============================================================================

_TITLE_EXACT_BLACKLIST = {
    "titre",
    "détail de la consultation",
    "détail d'une consultation",
    "accord",
    "fourniture",
    "prestations de support",
    "prestations",
    "consultation",
    "marché",
    "appel d'offres",
    "appel d'offre",
    "tma",  # Trop générique seul
    "prestation",
    "-",
    "",
    "...",
    "n/a",
    "non disponible",
    "non précisé",
}

# =============================================================================
# BLACKLISTS - Acheteurs (catégories administratives, pas des noms)
# =============================================================================

_BUYER_EXACT_BLACKLIST = {
    "autres organismes",
    "autorité publique centrale",
    "autorité locale",
    "autorité régionale",
    "organisme de droit public",
    "services d'administration générale",
    "santé",
    "protection de l'environnement",
    "loisirs, culture et culte",
    "services publics",
    "état",
    "territoriale",
    "hospitalière",
    # Rôles organisationnels (pas des noms)
    "entreprise publique, contrôlée par une autorité publique centrale",
    "etablissements et organismes de l'enseignement supérieur, de la recherche et de l'innovation",
    "ted esender",
    "ted esender : avenue-web systèmes",
    # Génériques
    "acheteur",
    "organisme",
    "organisation",
    "autorité",
    "administration",
    "collectivité",
    # Placeholders
    "-",
    "",
    "...",
    "n/a",
    "non identifié",
    "acheteur non identifié",
    "organisme non identifié",
    "ville de",
}

_BUYER_CONTAINS_BLACKLIST = (
    "organisation qui fournit des informations complémentaires",
    "organisation chargée des procédures de recours",
    "organisation qui fournit des précisions concernant l'introduction des recours",
    "organisme qui fournit des informations complémentaires",
    "forme juridique de l'acheteur",
    "activité du pouvoir adjudicateur",
    "point de contact",
)

# =============================================================================
# REGEX
# =============================================================================

_URL_RE = re.compile(r"https?://|www\.", re.I)
_SPACE_RE = re.compile(r"\s+")
_DATE_RE = re.compile(r"\b\d{2}/\d{2}/\d{4}(?:\s*(?:à)?\s*\d{2}:\d{2})?\b")


# =============================================================================
# FONCTIONS DE NORMALISATION
# =============================================================================

def normalize_text(value: str | None) -> str:
    """Normalise le texte: espaces, caractères spéciaux, apostrophes typographiques."""
    if not value:
        return ""
    value = value.replace("\xa0", " ").replace("­", "")
    # Normaliser apostrophes typographiques → droites (cohérent avec legacy)
    value = value.replace("\u2019", "'").replace("\u2018", "'")
    value = value.replace("\u201c", '"').replace("\u201d", '"')
    value = _SPACE_RE.sub(" ", value).strip(" \n\r\t-:;,.")
    return value.strip()


def normalized_key(value: str | None) -> str:
    """Clé normalisée pour comparaison (casefold)."""
    return normalize_text(value).casefold()


def looks_like_url(value: str | None) -> bool:
    """Vérifie si la valeur ressemble à une URL."""
    return bool(_URL_RE.search(value or ""))


# =============================================================================
# FONCTIONS DE VALIDATION
# =============================================================================

def is_valid_title(value: str | None) -> tuple[bool, str | None]:
    """Vérifie si un titre est valide (pas un faux positif).
    
    Returns:
        (is_valid, reason_if_invalid)
    """
    text = normalize_text(value)
    key = normalized_key(text)
    
    if not text:
        return False, "empty"
    if key in _TITLE_EXACT_BLACKLIST:
        return False, "generic_exact_title"
    if len(text) < 12:
        return False, "too_short"
    if looks_like_url(text):
        return False, "url"
    
    return True, None


def is_valid_buyer(value: str | None) -> tuple[bool, str | None]:
    """Vérifie si un acheteur est valide (pas une catégorie administrative).
    
    Returns:
        (is_valid, reason_if_invalid)
    """
    raw_key = (value or "").strip().casefold()
    text = normalize_text(value)
    key = normalized_key(text)

    if looks_like_url(text):
        return False, "url"
    if key in _BUYER_EXACT_BLACKLIST or raw_key in _BUYER_EXACT_BLACKLIST:
        return False, "generic_exact_buyer"
    if not text:
        return False, "empty"
    for bad in _BUYER_CONTAINS_BLACKLIST:
        if bad in key:
            return False, "generic_contains_buyer"
    if len(text) < 3:
        return False, "too_short"
    
    return True, None


# =============================================================================
# FONCTIONS DE SCORING
# =============================================================================

def score_title(value: str) -> int:
    """Score un titre candidat (plus haut = meilleur)."""
    text = normalize_text(value)
    score = 0
    
    if len(text) >= 20:
        score += 20
    if len(text) >= 40:
        score += 10
    if len(text) >= 60:
        score += 5
    
    # Mix majuscules/minuscules = texte naturel
    if any(c.islower() for c in text) and any(c.isupper() for c in text):
        score += 5
    
    # Pénalité si contient une date (souvent titre générique)
    if _DATE_RE.search(text):
        score -= 10
    
    return score


def score_buyer(value: str) -> int:
    """Score un acheteur candidat (plus haut = meilleur)."""
    text = normalize_text(value)
    score = 0
    
    if len(text) >= 8:
        score += 10
    if len(text) >= 20:
        score += 5
    
    # Tokens qui indiquent un vrai organisme
    tokens = ("ville", "commune", "centre", "direction", "minist", "bureau", 
              "syndicat", "région", "département", "hôpital", "centre hospitalier",
              "agence", "établissement", "université", "collège", "lycée",
              "brgm", "cea", "cnrs", "dgfip", "inra", "ird", "onf",
              "chaînes", "service", "unité")
    if any(token in text.lower() for token in tokens):
        score += 10
    
    # Structure hiérarchique (ex: "AO / CEA / GRENOBLE")
    if "/" in text:
        score += 5
    
    return score


# =============================================================================
# SÉLECTION DU MEILLEUR CANDIDAT
# =============================================================================

def pick_best_candidate(
    candidates: Iterable[FieldCandidate],
    validator,
    scorer,
) -> tuple[str, list[ExtractionTrace]]:
    """Sélectionne le meilleur candidat parmi une liste.
    
    Args:
        candidates: Liste de candidats
        validator: Fonction (value) -> (bool, reason)
        scorer: Fonction (value) -> int
        
    Returns:
        (best_value, list_of_traces)
    """
    traces: list[ExtractionTrace] = []
    accepted: list[FieldCandidate] = []

    for candidate in candidates:
        value = normalize_text(candidate.value)
        ok, reason = validator(value)
        score = scorer(value) + candidate.score
        
        if ok:
            accepted.append(FieldCandidate(
                field_name=candidate.field_name,
                value=value,
                rule=candidate.rule,
                score=score,
                meta=candidate.meta,
            ))
            traces.append(ExtractionTrace(
                field_name=candidate.field_name,
                rule=candidate.rule,
                value=value,
                score=score,
                accepted=True,
            ))
        else:
            traces.append(ExtractionTrace(
                field_name=candidate.field_name,
                rule=candidate.rule,
                value=value,
                score=score,
                accepted=False,
                reason=reason,
            ))

    # Trier par score décroissant
    accepted.sort(key=lambda c: c.score, reverse=True)
    
    if not accepted:
        return "", traces
    
    return accepted[0].value, traces
