"""
ao_etl/extract.py — Extraction HTML champ par champ.
Chaque fonction prend un soup/text et retourne une valeur métier normalisée.
Aucun I/O. Importe uniquement utils et config.
"""

import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup

from ao_etl.config import AVIS_DOMAINS, RECON_REJECT_RE
from ao_etl.utils import normaliser_texte, normaliser_date, parse_nombre_europeen

log = logging.getLogger(__name__)


def extraire_url_source(soup: BeautifulSoup) -> str:
    """Canonical > og:url > premier lien <a> vers un domaine d'avis connu."""
    for tag in soup.find_all("link", rel="canonical"):
        href = tag.get("href", "")
        if href.startswith("https"):
            return href
    tag = soup.find("meta", property="og:url")
    if tag:
        c = tag.get("content", "")
        if c.startswith("https"):
            return c
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("https") and any(d in href for d in AVIS_DOMAINS):
            return href
    return ""


def extraire_reference(soup: BeautifulSoup, filename: str) -> str:
    """Identifiant interne dans la page (BOAMP), puis dérivé du nom de fichier."""
    text = soup.get_text("\n", strip=True)
    m = re.search(r"Identifiant interne\s*[:\s]+([^\n]+)", text)
    if m:
        val = normaliser_texte(m.group(1))
        if val and len(val) < 60:
            return val
    stem = Path(filename).stem
    for pattern in [
        r"^((?:3boamp|13joue|36parisien|37ao)\d+)",
        r"^(ao-\d+-\d+)",
        r"^(\d+-\d+)",
    ]:
        mp = re.match(pattern, stem)
        if mp:
            return mp.group(1)
    return stem.split("-")[0]


def extraire_intitule(soup: BeautifulSoup, text: str) -> str:
    """Label structuré > h1 > balise title HTML."""
    for pat in [
        r"Intitul[eé] du march[eé]\s*[:\s]+([^\n]+)",
        r"Intitul[eé] de l.appel d.offre public\s*[:\s]+([^\n]+)",
        r"[Tt]itre\s*[:\s]+([^\n]{10,})",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = normaliser_texte(m.group(1))
            if len(val) > 5:
                return val
    h1 = soup.find("h1")
    if h1:
        val = normaliser_texte(h1.get_text())
        if len(val) > 5:
            return val
    if soup.title:
        t = normaliser_texte(soup.title.string or "")
        t = re.sub(r"^Appel d.offres?\s*:\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r",\s*[A-Z][A-Z\s\-\']+$", "", t)
        if len(t) > 5:
            return t
    return ""


def extraire_acheteur(text: str) -> str:
    """Nom officiel de l'acheteur. Rejette les valeurs suspectes."""
    REJECTED = re.compile(
        r"^(Acheteur|Organisation|https?://|Section|R[oô]le|Tribunal|Pouvoir)",
        re.IGNORECASE,
    )
    for pat in [
        r"Nom complet de l.acheteur\s*[:\s]+([^\n]+)",
        r"Nom officiel\s*[:\s]+([^\n]+)",
        r"Nom et adresse officiels[^\n]*\n([^\n]{3,80})",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = normaliser_texte(m.group(1))
            if val and len(val) >= 3 and not REJECTED.match(val):
                return val
    return ""


# Valeurs non-géographiques à rejeter (faux positifs fréquents)
_NON_GEO_VALUES_RE = re.compile(
    r"^(?:date\s+(?:de\s+)?cl[oô]ture|cl[oô]ture|consultation|tranche|march[eé]|"
    r"prestation|lot|la\s+consultation|le\s+march[eé]|les\s+prestations|"
    r"\d{2}/\d{2}/\d{4}|(?:\d{2}[/-]){2}\d{4})",
    re.IGNORECASE,
)


def extraire_localisation(text: str, site_type: str) -> str:
    """
    Extrait ville / département.
    MarchesOnline : '13 - MARSEILLE M' -> 'MARSEILLE (13)'.
    Filtre les faux positifs (dates, labels non-géographiques).
    """
    if site_type == "marchesonline":
        # Pattern 1: Format avec saut de ligne '13 - \n MARSEILLE'
        m = re.search(r"(\d{2})\s*-\s*\n\s*([A-Z][A-Z\s]+?)(?:\s+M)?(?:\s*\n|$)", text)
        if m:
            dept = m.group(1)
            city = normaliser_texte(m.group(2))
            return f"{city} ({dept})"
        # Pattern 2: Format avec espaces '13 -   MARSEILLE' (après nettoyage)
        m = re.search(r"(\d{2})\s*-\s+([A-Z][A-Z\s]+?)(?:\s+M)?(?:\s*\n|$)", text)
        if m:
            dept = m.group(1)
            city = normaliser_texte(m.group(2))
            return f"{city} ({dept})"

    # Patterns d'extraction avec captures plus contrôlées
    # [^\n]{2,60} limite la taille et évite les faux positifs sur labels adjacents
    for pat in [
        r"Lieu principal d.ex[eé]cution[^\n]*[:\s]+([^\n]{2,60})",
        r"[Ll]ocalisation\s*[:\s]+([^\n]{2,60})",
        r"Ville\s*[:\s]+([^\n]{2,60})",
        r"Subdivision pays[^\n]*\n([^\n]{2,60})",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = normaliser_texte(m.group(1))
            # Validation: ni vide, ni trop long, ni URL, ni faux positif
            if not val:
                continue
            if len(val) >= 80 or val.startswith("http"):
                log.debug("Localisation rejetée (URL/trop longue): %r", val)
                continue
            if _NON_GEO_VALUES_RE.match(val):
                log.debug("Localisation rejetée (faux positif): %r", val)
                continue
            # Rejeter si la valeur contient un autre label (cas MarchesOnline)
            if re.search(r":\s*$|date\s+de|cl[oô]ture|dur[eé]e\s+du\s+march", val, re.IGNORECASE):
                log.debug("Localisation rejetée (contient un label): %r", val)
                continue
            return val
    return ""


def extraire_procedure(text: str) -> str:
    """Retourne : MAPA / AOO / Procédure négociée."""
    RULES = [
        (r"proc[eé]dure adapt[eé]e|MAPA\b|adapt[eé]e\b",                       "MAPA"),
        (r"appel d.offres? ouvert|proc[eé]dure (ouverte|formalis[eé]e)"
         r"|[Tt]ype\s*[:\s]+Ouverte\b",                                         "AOO"),
        (r"n[eé]goci[eé]e?\b",                                                  "Procédure négociée"),
        (r"restreinte\b",                                                        "AOO"),
    ]
    m = re.search(r"[Tt]ype de proc[eé]dure\s*[:\s]+([^\n]+)", text)
    proc_val = m.group(1) if m else ""
    for pattern, label in RULES:
        src = proc_val if proc_val else text[:2000]
        if re.search(pattern, src, re.IGNORECASE):
            return label
    if not proc_val:
        for pattern, label in RULES:
            if re.search(pattern, text[:3000], re.IGNORECASE):
                return label
    return ""


def extraire_type(text: str) -> str:
    """CCAG TIC / PI / Travaux / Fournitures / Services."""
    CCAG = [
        (r"CCAG.?TIC\b|technologies de l.information",  "CCAG TIC"),
        (r"CCAG.?PI\b|propri[eé]t[eé] intellectuelle",  "CCAG PI"),
        (r"CCAG.?Travaux\b",                             "CCAG Travaux"),
        (r"CCAG.?Fournitures\b",                         "CCAG Fournitures"),
        (r"CCAG.?Services\b",                            "CCAG Services"),
    ]
    sample = text[:5000]
    for pattern, label in CCAG:
        if re.search(pattern, sample, re.IGNORECASE):
            return label
    m = re.search(r"[Nn]ature\s+(?:du|principale du)\s*march[eé]\s*[:\s]+([^\n]+)", sample)
    if m:
        val = m.group(1).strip()
        if re.search(r"service",    val, re.IGNORECASE): return "Services"
        if re.search(r"fourniture", val, re.IGNORECASE): return "Fournitures"
        if re.search(r"travaux",    val, re.IGNORECASE): return "Travaux"
    if re.search(r"\bservices?\b",    sample[:1000], re.IGNORECASE): return "Services"
    if re.search(r"\bfournitures?\b", sample[:1000], re.IGNORECASE): return "Fournitures"
    return ""


def extraire_fonction_publique(acheteur: str, text: str) -> str:
    """
    Extrait et normalise la fonction publique vers la taxonomie stricte :
    etat | territoriale | hospitaliere | -
    Ordre : hospitaliere d'abord pour éviter faux positifs sur 'CH'.
    """
    RULES = [
        (r"\b[Cc]entre [Hh]ospitalier\b|\bhospitalier\b|\b[Hh][oô]pital\b"
         r"|\bCHU\b|\bCHR\b|\bGCS\b|\bUNIHA\b|\bUniHA\b|\bGCS-UNIHA\b|\bCASPV\b",
         "hospitaliere"),
        (r"\b[Mm]inist[eè]re\b|\bDGFiP\b|\bDGFIP\b|\bDNum\b|\bDNUM\b"
         r"|\bAIFE\b|\bBRGM\b|\b[Aa]cad[eé]mie [Ff]ran[cç]aise\b|\bESCP\b"
         r"|\b[Ii]nstitut [Ff]ran[cç]ais\b|\b[Cc]onservatoire national\b"
         r"|\bHaute Autorit[eé] de Sant[eé]\b|\bJustice\b"
         r"|\b[Mm]inarm\b|\bMINARM\b|\bCND\b"
         r"|\bInstitut g[eé]ographique national\b|\bIGN\b"
         r"|\bCompagnie Nationale du Rh[oô]ne\b"
         r"|\bIF\.?C\.?E\b|\bF[eé]mis\b|\bFEMIS\b|\bEnsmis\b|\bEPMO\b"
         r"|\bUNICANCER\b|\bAutorit[eé] publique centrale\b"
         r"|\bCNAF\b|\bCNAM\b|\bCNAV\b|\bCNIL\b|\bANSSI\b|\bANSS\b"
         r"|\bI\.?F\.?C\.?E\.?\b|\bInstitut [Ff]ran[cç]ais du [Cc]heval\b",
         "etat"),
        (r"\b[Vv]ille\b|\b[Cc]ommune\b|\b[Cc]onseil [Dd][eé]partemental\b"
         r"|\b[Rr][eé]gion\b|\bterritorial\b|\bintercommunal\b"
         r"|\bSICIO\b|\bCASVP\b|\bEPPGHV\b|\bParlement [Ww]allon\b",
         "territoriale"),
    ]
    combined = acheteur + " " + text[:4000]
    for pattern, label in RULES:
        if re.search(pattern, combined, re.IGNORECASE):
            return label
    return "-"


def extraire_date_limite(text: str) -> str:
    """
    Date limite de remise des offres, normalisée en DD/MM/YYYY.
    Aplatit les sauts de ligne avant matching (format JOUE multi-lignes).
    Priorité aux labels explicites ; date+heure en dernier recours.
    """
    flat = re.sub(r"[ \t]*\n[ \t]*", " ", text)
    PATTERNS = [
        (r"date\s+(?:et\s+heure\s+)?limite\s+de\s+(?:remise|r[eé]ception)\s+des\s+"
         r"(?:plis|offres|candidatures)\s*[^\d]*(\d{2}/\d{2}/\d{4})"),
        (r"date\s+(?:limite|butoir)\s*(?:de\s+r[eé]ponse|de\s+remise|de\s+r[eé]ception)?"
         r"\s*[^\d]*(\d{2}/\d{2}/\d{4})"),
        (r"date\s+de\s+cl[oô]ture\s*[^\d]*(\d{2}/\d{2}/\d{4})"),
        (r"limite\s+de\s+r[eé]ponse\s*[:\s]*(\d{2}/\d{2}/\d{4})"),
        (r"cl[oô]t[uû]re\s*[:\s]*(\d{2}/\d{2}/\d{4})"),
        (r"r[eé]ception\s+des\s+offres\s*[:\s]*(\d{2}/\d{2}/\d{4})"),
        (r"(\d{2}/\d{2}/\d{4})\s*[àa]\s*\d{2}[h:]\d{2}"),
    ]
    for pat in PATTERNS:
        m = re.search(pat, flat, re.IGNORECASE)
        if m:
            return normaliser_date(m.group(1))
    return ""


def extraire_duree(text: str) -> tuple[str, str]:
    """
    Retourne (duree_initiale, reconductions).
    - Labels structurés uniquement.
    - Valide : mois <= 120, ans <= 15.
    - Reconduction via labels stricts (rejette les slugs).
    """
    duree = ""
    recon = ""

    if re.search(r"[Aa]utre dur[eé]e\s*[:\s]*Inconnu", text):
        duree = ""
    else:
        DUR_PATTERNS = [
            r"[Dd]ur[eé]e du march[eé][^\n]*\(en mois\)[^\d\n]*\n?\s*(\d+)",
            r"[Dd]ur[eé]e estim[eé]e\s*\n\s*[Dd]ur[eé]e\s*\n\s*:\s*\n\s*(\d+)\s*\n\s*(Mois|An|ans?)",
            r"[Dd]ur[eé]e estim[eé]e\s*\n\s*[Dd]ur[eé]e\s*[:\s]+(\d+)\s*(Mois|An|ans?|mois)",
            r"[Dd]ur[eé]e\s*\n\s*:\s*\n\s*(\d+)\s*\n\s*(Mois|An|ans?)",
            r"[Dd]ur[eé]e\s*[:\s]+(\d+)\s*(Mois|mois|An|ans?|jours?)",
            r"[Dd]ur[eé]e du march[eé]\s*[\(\[]?en mois[\)\]]?\s*[:\s]+(\d+)",
        ]
        UNIT_NORM = {
            "mois": "mois", "Mois": "mois",
            "an": "an(s)", "ans": "an(s)", "An": "an(s)",
            "jour": "jour(s)", "jours": "jour(s)",
        }
        for pat in DUR_PATTERNS:
            m = re.search(pat, text)
            if not m:
                continue
            val_str  = m.group(1)
            unit_raw = (m.group(2).strip()
                        if m.lastindex and m.lastindex >= 2
                        else "mois")
            unit = UNIT_NORM.get(unit_raw, "mois")
            try:
                v = int(val_str)
                if unit == "mois"       and v > 120:
                    log.debug("Duree ignoree (aberrante) : %d mois", v)
                    continue
                if unit.startswith("an") and v > 15:
                    log.debug("Duree ignoree (aberrante) : %d ans", v)
                    continue
                duree = f"{v} {unit}"
                break
            except ValueError:
                continue

    RECON_PATTERNS = [
        r"Nombre max(?:imal)? de renouvellements?\s*[:\s]+(\d+[^\n]{0,80})",
        r"Nombre max(?:imal)? de renouvellements?\s*\n\s*(\d+[^\n]{0,80})",
        r"[Aa]utres informations sur le renouvellement\s*[:\s]+([^\n]{15,150})",
        r"[Pp]ossibilit[eé] de reconduction\s*[:\s]+(Oui[^\n]{0,80}|Non\b[^\n]{0,30})",
        r"(reconductible\s+(?:\d+\s+fois|annuellement|tacitement)[^\n\.]{0,80})",
    ]
    for pat in RECON_PATTERNS:
        m = re.search(pat, text)
        if not m:
            continue
        val = normaliser_texte(m.group(1))
        if len(val) < 3 or RECON_REJECT_RE.match(val):
            log.debug("Reconduction rejetee : %r", val)
            continue
        recon = val[:150]
        break

    return duree, recon


def extraire_estimation(text: str) -> str:
    """
    Valeur estimée du marché en euros HT.
    - Labels structurés uniquement.
    - Tronque avant les tableaux tarifaires MarchesOnline.
    - Rejette les années (2000-2100).
    - Décode les nombres européens.
    """
    tarif_m = re.search(r"[Tt]arifs?\s+HT\b|€\s*HT/[Mm]ois\b|HT/[Mm]ois\b", text)
    if tarif_m:
        text = text[:tarif_m.start()]

    ESTIM_PATTERNS = [
        r"[Vv]aleur estim[eé]e hors TVA\s*[:\s]+([\d][0-9\s,\.]+)\s*(Euro|EUR|€)?",
        r"[Vv]aleur max(?:imale)? de l.accord.cadre\s*[:\s]+([\d][0-9\s,\.]+)\s*(Euro|EUR|€)?",
        r"[Mm]ontant estim[eé]\s*[:\s]+([\d][0-9\s,\.]+)\s*(Euro|EUR|€|k€|M€)?",
        r"[Ee]stimation du march[eé]\s*[:\s]+([\d][0-9\s,\.]+)\s*(Euro|EUR|€|k€|M€)?",
    ]
    for pat in ESTIM_PATTERNS:
        m = re.search(pat, text)
        if not m:
            continue
        raw_val = m.group(1).strip()
        num = parse_nombre_europeen(raw_val)
        if num is None or num <= 0:
            continue
        if 2000 <= num <= 2100:
            log.debug("Estimation ignoree (annee probable) : %s", num)
            continue
        if num >= 1_000_000:
            fmt = f"{num / 1_000_000:.2f}".rstrip("0").rstrip(".")
            return f"{fmt} M€ HT"
        elif num >= 1_000:
            return f"{int(num):,} € HT".replace(",", " ")
        else:
            return f"{int(num)} € HT"
    return ""
