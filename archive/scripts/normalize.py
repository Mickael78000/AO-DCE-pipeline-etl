"""
ao_etl/normalize.py — Normalisation post-extraction de Acheteur et Localisation.
Fonctions pures, sans I/O, sans dépendance interne au package.
"""

import re

# ── Mapping département nom → code (fréquents dans le corpus) ────────────────

_DEPT_NAME_TO_CODE: dict[str, str] = {
    "ain": "01", "allier": "03", "alpes-de-haute-provence": "04",
    "hautes-alpes": "05", "alpes-maritimes": "06", "ardèche": "07",
    "ardèche": "07", "ardéche": "07",
    "ardennes": "08", "ariège": "09", "aube": "10",
    "aude": "11", "aveyron": "12", "bouches-du-rhône": "13",
    "calvados": "14", "cantal": "15", "charente": "16",
    "charente-maritime": "17", "cher": "18", "corrèze": "19",
    "corse-du-sud": "2a", "haute-corse": "2b",
    "côte-d'or": "21", "côtes-d'armor": "22", "creuse": "23",
    "dordogne": "24", "doubs": "25", "drôme": "26",
    "eure": "27", "eure-et-loir": "28", "finistère": "29",
    "gard": "30", "haute-garonne": "31", "gers": "32",
    "gironde": "33", "hérault": "34", "ille-et-vilaine": "35",
    "indre": "36", "indre-et-loire": "37", "isère": "38",
    "jura": "39", "landes": "40", "loir-et-cher": "41",
    "loire": "42", "haute-loire": "43", "loire-atlantique": "44",
    "loiret": "45", "lot": "46", "lot-et-garonne": "47",
    "lozère": "48", "maine-et-loire": "49", "manche": "50",
    "marne": "51", "haute-marne": "52", "mayenne": "53",
    "meurthe-et-moselle": "54", "meuse": "55", "morbihan": "56",
    "moselle": "57", "nièvre": "58", "nord": "59",
    "oise": "60", "orne": "61", "pas-de-calais": "62",
    "puy-de-dôme": "63", "pyrénées-atlantiques": "64",
    "hautes-pyrénées": "65", "pyrénées-orientales": "66",
    "bas-rhin": "67", "haut-rhin": "68", "rhône": "69",
    "haute-saône": "70", "saône-et-loire": "71", "sarthe": "72",
    "savoie": "73", "haute-savoie": "74", "paris": "75",
    "seine-maritime": "76", "seine-et-marne": "77", "yvelines": "78",
    "deux-sèvres": "79", "somme": "80", "tarn": "81",
    "tarn-et-garonne": "82", "var": "83", "vaucluse": "84",
    "vendée": "85", "vienne": "86", "haute-vienne": "87",
    "vosges": "88", "yonne": "89", "territoire de belfort": "90",
    "essonne": "91", "hauts-de-seine": "92", "seine-saint-denis": "93",
    "val-de-marne": "94", "val-d'oise": "95",
    "guadeloupe": "971", "martinique": "972", "guyane": "973",
    "la réunion": "974", "mayotte": "976",
}

# Normalisation des accents pour la lookup
def _norm_key(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")

_DEPT_LOOKUP: dict[str, str] = {_norm_key(k): v for k, v in _DEPT_NAME_TO_CODE.items()}

# ── Regex utilitaires ─────────────────────────────────────────────────────────

# Suffixe géographique en fin de chaîne : ", Ville (NN, Région)" ou ", Ville (NN)" ou ", Ville"
# Accepte majuscule ou article "Le/La/Les"
_GEO_SUFFIX_RE = re.compile(
    r",\s*(?:Le\s+|La\s+|Les\s+|L\u2019)?[A-ZÀ-Ÿ][A-Za-zÀ-ÿ\u2011\-\s\'\.]+(\s*\(\s*\d{2,3}[^)]*\))?\s*$"
)

# Suffixes parasites "France entière", "exécution partout en France", "siège …"
_FRANCE_ENTIERE_RE = re.compile(
    r"[,;\s]*\(?[Ff][Rr][Aa][Nn][Cc][Ee]\s+enti[eè]re\)?",
)
_EXEC_FRANCE_RE = re.compile(
    r"[,;\s]*ex[eé]cution\s+partout\s+en\s+[Ff]rance[^)]*",
    re.IGNORECASE,
)
_SIEGE_RE = re.compile(
    r"[,;\s]*\(?\s*si[eè]ge\s+[^)]{0,60}?(?=\)|,|;|$)[)]*",
    re.IGNORECASE,
)

# URL parasite (fragment type xxx.apps.yyy ou domaine collé, avec ou sans virgule)
_URL_PARASITE_RE = re.compile(
    r"[a-z0-9\-]+(?:\.[a-z0-9\-]+){1,4}\.[a-z]{2,6}$",
    re.IGNORECASE,
)
# URL collée sans virgule en fin (ex: "(CASVP), Parisa06-v7.apps.paris")
_URL_COLLE_RE = re.compile(
    r",?\s*[A-Za-z0-9][A-Za-z0-9\-]*[a-z0-9](?:[\-\.][a-z0-9][a-z0-9\-]*){2,}\s*$",
)
# Slug alpha pur collé sans séparateur après entière/France (ex: "France entièrelacentraledesmarches")
_SLUG_COLLE_RE = re.compile(
    r"(?<=[a-zèéêàâ])[a-z]{5,}$"
)

# Valeurs de localisation non géographiques issues du parser HTML
_NON_GEO_RE = re.compile(
    r"^(date\b|clot[uû]re|consultation\b|tranche|march[eé]\b|prestation|lot\b"
    r"|la\s+consultation\b|le\s+march[eé]\b|les\s+prestation|dur[eé]e\b)",
    re.IGNORECASE,
)

# Pattern pour détecter les artefacts de parsing MarchesOnline
_MARCHESONLINE_ARTIFACT_RE = re.compile(
    r"date\s+de\s+cl[oô]ture|cl[oô]ture\s*:|dur[eé]e\s+du\s+march[eé]",
    re.IGNORECASE,
)

# Ville + département dans une chaîne mêlée : "Marseille (13, Provence…)" ou "Marseille (13)"
# Le groupe ville n'accepte pas '(' pour éviter de capturer la région dans "(13, Provence…)"
_VILLE_DEPT_RE = re.compile(
    r",\s*([A-ZÀ-Ÿ][A-Za-zÀ-ÿ\u2011\-\s\'\.\u1d49]{1,50}?)\s*\(\s*(\d{2,3})\s*[,\)]"
)

# Ville seule en fin (après virgule, majuscule, pas de parenthèse)
_VILLE_SEULE_RE = re.compile(
    r",\s*([A-ZÀ-Ÿ][A-Za-zÀ-ÿ\-\s\'\.ᵉ]{2,40})\s*$"
)

# Localisation déjà propre : "Ville (NN)"
_PROPRE_RE = re.compile(r"^[A-ZÀ-Ÿ][A-Za-zÀ-ÿ\-\s\'\.ᵉ]+\s*\(\d{2,3}\)$")

# Département seul avec code : "Seine-Saint-Denis (93)"
_DEPT_AVEC_CODE_RE = re.compile(
    r"^([A-ZÀ-Ÿ][A-Za-zÀ-ÿ\-\s\'\.]+)\s*\(\s*(\d{2,3})\s*\)$"
)

# Acheteur non identifié
_NON_IDENTIFIE_RE = re.compile(
    r"Acheteur non clairement identifi[eé][^(]*"
    r"\(r[eé]f\.\s*([^)]+)\)",
    re.IGNORECASE,
)
_NON_IDENTIFIE_PLATFORM_RE = re.compile(
    r"extrait\s+([A-Za-zÀ-ÿ\s]+?)\s+\(",
    re.IGNORECASE,
)


# ── Fonctions publiques ───────────────────────────────────────────────────────

def clean_acheteur(val: str) -> str:
    """
    Retourne l'entité principale de l'acheteur, sans suffixes géographiques,
    URL parasites, mentions France entière / siège.
    Ne modifie pas les valeurs qui ne correspondent pas aux patterns reconnus.
    """
    if not val or not val.strip():
        return ""

    s = val.strip()

    # Cas "Acheteur non clairement identifié (extrait Platform, réf. XXX)"
    m = _NON_IDENTIFIE_RE.search(s)
    if m:
        ref = m.group(1).strip()
        mp = _NON_IDENTIFIE_PLATFORM_RE.search(s)
        platform = mp.group(1).strip() if mp else "source"
        return f"Acheteur non clairement identifié ({platform}, réf. {ref})"

    # Supprimer slug alpha pur collé AVANT suppression France entière
    # (ex: "France entièrelacentraledesmarches" → "France entière")
    s = _SLUG_COLLE_RE.sub("", s)
    # Supprimer les mentions parasites (dans l'ordre pour éviter les résidus)
    s = _FRANCE_ENTIERE_RE.sub("", s)
    s = _EXEC_FRANCE_RE.sub("", s)
    s = _SIEGE_RE.sub("", s)

    # Supprimer l'URL parasite collée en fin (avec ou sans virgule)
    m_url = _URL_COLLE_RE.search(s)
    if m_url:
        s = s[:m_url.start()]

    # Supprimer le suffixe géographique final ", Ville (NN, Région)" ou ", Ville"
    m_geo = _GEO_SUFFIX_RE.search(s)
    if m_geo:
        s = s[:m_geo.start()]

    # Nettoyage résiduel
    s = s.strip().rstrip(",;").strip()

    # Supprimer mentions entre parenthèses résiduelles de type "(75, Paris ; exécution…)"
    s = re.sub(r"\s*\(\s*\d{2,3}\s*,\s*[A-Za-zÀ-ÿ\s]+(?:;[^)]+)?\)", "", s)
    s = s.strip().rstrip(",;").strip()

    # Supprimer résidu de code département orphelin en fin ex: "33)" ou ", 33)"
    s = re.sub(r"[,\s]+\d{2,3}\)\s*$", "", s).strip()

    # Supprimer point final résiduel issu des suppressions précédentes
    s = s.rstrip(".").strip()

    return s if s else val.strip()


def clean_localisation(val_loc: str, val_acheteur: str = "") -> str:
    """
    Retourne une localisation courte et normalisée.
    Priorité : val_loc existante → extraction depuis val_acheteur.
    Formats cibles : 'Ville (NN)', 'France entière', 'Commune non nommée (France)',
                     'Département (NN)', ou val_loc telle quelle si déjà propre.
    """
    loc = val_loc.strip() if val_loc else ""
    ach = val_acheteur.strip() if val_acheteur else ""

    # Rejeter les valeurs clairement non géographiques issues du parser HTML
    if loc and _NON_GEO_RE.match(loc):
        loc = ""

    # Rejeter les artefacts de parsing MarchesOnline
    if loc and _MARCHESONLINE_ARTIFACT_RE.search(loc):
        loc = ""

    # Localisation anonymisée explicite
    if re.search(r"ville\s+(de\s+)?…|ville\s+n.est\s+pas\s+nomm|non\s+nomm",
                 loc + ach, re.IGNORECASE):
        return "Commune non nommée (France)"

    # France entière (loc ou acheteur)
    if re.search(r"[Ff][Rr][Aa][Nn][Cc][Ee]\s+enti[eè]re", loc + ach):
        return "France entière"

    # Localisation déjà sous forme "Ville (NN)" — ne rien faire
    if loc and _PROPRE_RE.match(loc):
        return loc

    # Département avec code déjà présent "Seine-Saint-Denis (93)"
    m = _DEPT_AVEC_CODE_RE.match(loc)
    if m:
        return f"{m.group(1).strip()} ({m.group(2)})"

    # "Paris" seul → "Paris (75)" (avant la lookup générique)
    if loc.strip().lower() in ("paris", "paris (75)"):
        return "Paris (75)"

    # Département seul sans code → lookup table
    if loc and not re.search(r"\d", loc):
        code = _DEPT_LOOKUP.get(_norm_key(loc))
        if code:
            return f"{loc} ({code})"

    # Ville seule en fin de loc (ex: "Haute Autorité de Santé (HAS), Paris")
    m_vs = _VILLE_SEULE_RE.search(loc)
    if m_vs:
        ville = m_vs.group(1).strip()
        code = _DEPT_LOOKUP.get(_norm_key(ville))
        if code:
            return f"{ville} ({code})"

    # Cas spécial : "(NN, NomVille ; ...)" sans ville avant la parenthèse
    # ex: "CNAF – … (75, Paris ; exécution partout en France)"
    # Uniquement si _VILLE_DEPT_RE ne trouve pas de ville+dept dans la chaîne
    if not _VILLE_DEPT_RE.search(loc):
        m_nn = re.search(r"\(\s*(\d{2,3})\s*,\s*([A-ZÀ-Ÿ][A-Za-zÀ-ÿ\u2011\-]+)", loc)
        if m_nn:
            dept  = m_nn.group(1)
            ville = m_nn.group(2).strip()
            return f"{ville} ({dept})"

    # Si loc == acheteur (non résolue), tenter extraction depuis acheteur uniquement
    sources_to_try = [loc, ach] if loc != ach else [ach]

    for source in sources_to_try:
        if not source:
            continue
        # Ville + dept : ", Grenoble (38, Auvergne…)" ou ", Grenoble (38)"
        # Prendre le PREMIER match (ville la plus proche du nom de l'acheteur, pas la région)
        matches = _VILLE_DEPT_RE.findall(source)
        if matches:
            ville = matches[0][0].strip().rstrip("ᵉ°").strip()
            dept  = matches[0][1]
            return f"{ville} ({dept})"

        # "Ville de Croissy-sur-Seine (78, Yvelines)" — ville enchâssée dans "Ville de"
        m2 = re.search(
            r"[Vv]ille\s+de\s+([A-ZÀ-Ÿ][A-Za-zÀ-ÿ\-\s\'\.]+?)\s*\(\s*(\d{2,3})",
            source,
        )
        if m2:
            return f"{m2.group(1).strip()} ({m2.group(2)})"

    # Si loc non vide et pas améliorable, retourner telle quelle
    if loc:
        return loc

    return ""
