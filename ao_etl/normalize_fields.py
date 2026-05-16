"""
Normalisation déterministe des champs finaux du CSV.

Source unique de vérité pour les taxonomies autorisées et les fonctions
de normalisation. Toutes les phases du pipeline doivent passer par ce
module pour écrire dans les colonnes finales.

Taxonomies autorisées :
  Fonction publique : etat | territoriale | hospitaliere | -
  Type d'AO         : texte libre issu du parsing déterministe | -
  Type (marché)     : Services | Fournitures | Travaux | CCAG TIC | CCAG PI
                      | CCAG Travaux | CCAG Fournitures | CCAG Services | -

Règle absolue : toute valeur hors domaine → "-".
"""

from __future__ import annotations

import re
from typing import Optional

# =============================================================================
# TAXONOMIES — SOURCE UNIQUE DE VÉRITÉ
# =============================================================================

ALLOWED_FONCTION_PUBLIQUE = frozenset(["etat", "territoriale", "hospitaliere", "-"])

ALLOWED_TYPE = frozenset([
    "Services", "Fournitures", "Travaux",
    "CCAG TIC", "CCAG PI", "CCAG Travaux", "CCAG Fournitures", "CCAG Services",
    "-",
])

# =============================================================================
# NORMALISATION : Fonction publique
# =============================================================================

# Mapping depuis les labels internes d'extract.py (majuscule/accentué)
_FP_INTERNAL_MAP = {
    "Hospitalière": "hospitaliere",
    "Hospitaliere": "hospitaliere",
    "hospitalière": "hospitaliere",
    "Etat":         "etat",
    "État":         "etat",
    "Territoriale": "territoriale",
}

# Mapping depuis les libellés JOUE bruts (acheteur_activite des fichiers .txt)
# + Forme juridique de l'acheteur
_FP_JOUE_RULES = [
    # Hospitalier
    (re.compile(r"sant[eé]\b|hospitalier|h[oô]pital|EHPAD|soins",
                re.IGNORECASE), "hospitaliere"),
    # État — administration centrale, établissements publics nationaux
    (re.compile(
        r"administration g[eé]n[eé]rale|autorit[eé] publique centrale"
        r"|d[eé]fense|justice|[eé]ducation|enseignement|recherche"
        r"|organisme de droit public"
        r"|loisirs.*culture|culture.*loisirs"
        r"|protection de l.environnement"
        r"|services? g[eé]n[eé]raux",
        re.IGNORECASE), "etat"),
    # Territorial
    (re.compile(
        r"autorit[eé] locale|collectivit[eé]|territorial"
        r"|logement.*d[eé]veloppement|am[eé]nagement|transport"
        r"|protection sociale",
        re.IGNORECASE), "territoriale"),
]


def normalize_fonction_publique(value: str) -> str:
    """Normalise une valeur de Fonction publique vers la taxonomie stricte.

    Sources acceptées :
    - Labels internes d'extract.py ("Hospitalière", "Etat", "Territoriale")
    - Libellés bruts JOUE ("Loisirs, culture et culte", etc.)
    - Forme juridique de l'acheteur
    - Valeurs déjà normalisées

    Toute valeur non classifiable → "-".
    """
    if not value or value.strip() in ("", "-"):
        return "-"
    v = value.strip()

    # Déjà dans la taxonomie finale
    if v in ALLOWED_FONCTION_PUBLIQUE:
        return v

    # Labels internes (majuscule/accent)
    if v in _FP_INTERNAL_MAP:
        return _FP_INTERNAL_MAP[v]

    # Libellés JOUE bruts
    for pattern, canonical in _FP_JOUE_RULES:
        if pattern.search(v):
            return canonical

    return "-"


# =============================================================================
# NORMALISATION : Type d'AO (procédure)
# =============================================================================

_TYPE_AO_RULES = [
    (re.compile(r"proc[eé]dure adapt[eé]e|MAPA\b|adapt[eé]e\b",
                re.IGNORECASE), "MAPA"),
    (re.compile(r"appel d.offres? ouvert|proc[eé]dure ouverte|ouverte\b",
                re.IGNORECASE), "AOO"),
    (re.compile(r"n[eé]goci[eé]e?\b", re.IGNORECASE), "Procédure négociée"),
    (re.compile(r"restreinte\b", re.IGNORECASE), "Procédure restreinte"),
    (re.compile(r"dialogue comp[eé]titif\b", re.IGNORECASE), "Dialogue compétitif"),
]

_ALLOWED_TYPE_AO = frozenset([
    "MAPA", "AOO", "Procédure négociée", "Procédure restreinte",
    "Dialogue compétitif", "-",
])


def normalize_type_ao(value: str) -> str:
    """Normalise une valeur de Type d'AO vers la taxonomie reconnue.

    Toute valeur hors domaine ou non classifiable → "-".
    Interdit tout champ legacy LLM (type_ao, etc.).
    """
    if not value or value.strip() in ("", "-"):
        return "-"
    v = value.strip()
    if v in _ALLOWED_TYPE_AO:
        return v
    for pattern, canonical in _TYPE_AO_RULES:
        if pattern.search(v):
            return canonical
    return "-"


# =============================================================================
# NORMALISATION : Type (nature du marché)
# =============================================================================

_TYPE_MARCHE_RULES = [
    (re.compile(r"CCAG.?TIC\b|technologies de l.information",
                re.IGNORECASE), "CCAG TIC"),
    (re.compile(r"CCAG.?PI\b|propri[eé]t[eé] intellectuelle",
                re.IGNORECASE), "CCAG PI"),
    (re.compile(r"CCAG.?[Tt]ravaux\b", re.IGNORECASE), "CCAG Travaux"),
    (re.compile(r"CCAG.?[Ff]ournitures\b", re.IGNORECASE), "CCAG Fournitures"),
    (re.compile(r"CCAG.?[Ss]ervices\b", re.IGNORECASE), "CCAG Services"),
    (re.compile(r"\b[Ss]ervices?\b"), "Services"),
    (re.compile(r"\b[Ff]ournitures?\b"), "Fournitures"),
    (re.compile(r"\b[Tt]ravaux\b"), "Travaux"),
]


def normalize_type_marche(value: str) -> str:
    """Normalise une valeur de Type (nature du marché) vers la taxonomie stricte.

    Toute valeur non reconnue → "-".
    """
    if not value or value.strip() in ("", "-"):
        return "-"
    v = value.strip()
    if v in ALLOWED_TYPE:
        return v
    for pattern, canonical in _TYPE_MARCHE_RULES:
        if pattern.search(v):
            return canonical
    return "-"


# =============================================================================
# VALIDATION FINALE — appliquée avant tout export CSV
# =============================================================================

def validate_and_fix_row(row: dict) -> dict:
    """Applique la validation finale sur les colonnes contractuelles.

    À appeler comme couche unique avant écriture CSV dans toute phase.
    Normalise et rejette toute valeur hors taxonomie.

    Colonnes traitées :
      - "Fonction publique" → etat | territoriale | hospitaliere | -
      - "Type d'AO"         → MAPA | AOO | Procédure négociée | ... | -
      - "Type"              → Services | Fournitures | Travaux | CCAG * | -

    Ne touche pas aux autres colonnes.
    """
    fp = row.get("Fonction publique", "")
    row["Fonction publique"] = normalize_fonction_publique(fp)

    type_ao = row.get("Type d'AO", "")
    row["Type d'AO"] = normalize_type_ao(type_ao)

    type_marche = row.get("Type", "")
    row["Type"] = normalize_type_marche(type_marche)

    return row
