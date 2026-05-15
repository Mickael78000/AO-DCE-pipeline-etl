"""
ao_etl/utils.py — Utilitaires de normalisation purs.
Sans état, sans I/O. Testables unitairement de façon isolée.
"""

import re

from ao_etl.config import AMBIGUOUS_RE


def normaliser_texte(s) -> str:
    """Normalise les espaces et retourne une chaine propre."""
    if not s:
        return ""
    return " ".join(str(s).split())


def normaliser_date(s: str) -> str:
    """Retourne DD/MM/YYYY ou '' si non parsable."""
    s = normaliser_texte(s)
    m = re.search(r"(\d{2}/\d{2}/\d{4})", s)
    if m:
        return m.group(1)
    m2 = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m2:
        return f"{m2.group(3)}/{m2.group(2)}/{m2.group(1)}"
    return ""


def nettoyer_valeur_vide(s: str) -> str:
    """Retourne '' si la valeur est vide ou ambiguë."""
    s = normaliser_texte(s)
    if not s or AMBIGUOUS_RE.match(s):
        return ""
    return s


def parse_nombre_europeen(raw: str) -> float | None:
    """
    Décode les nombres à notation européenne.
      '400,000'  -> 400000  (virgule = séparateur de milliers si 3 chiffres après)
      '1,5'      -> 1.5     (virgule = décimale si != 3 chiffres après)
      '1.500'    -> 1500    (point = séparateur de milliers si 3 chiffres après)
    """
    raw = raw.strip().replace("\u00a0", "").replace(" ", "")
    nb_commas = raw.count(",")
    nb_dots   = raw.count(".")

    if nb_commas == 1 and nb_dots == 0:
        after = raw.split(",")[1]
        raw = raw.replace(",", "") if len(after) == 3 else raw.replace(",", ".")
    elif nb_commas > 1:
        raw = raw.replace(",", "")
    elif nb_dots == 1 and nb_commas == 0:
        after = raw.split(".")[1]
        if len(after) == 3:
            raw = raw.replace(".", "")
    elif nb_dots > 1:
        raw = raw.replace(".", "")
    try:
        return float(raw)
    except ValueError:
        return None
