"""
ao_etl/detect.py — Détection du type de source et construction du record.
Orchestre les appels extract.* pour produire un dict complet depuis un fichier HTML.
Nettoyage HTML en Python intégré avant parsing BeautifulSoup.
"""

import logging
import re
import warnings
from pathlib import Path

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from ao_etl import extract
from ao_etl.utils import normaliser_texte
from ao_etl.clean_html import read_and_clean_html, clean_extracted_text

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

log = logging.getLogger(__name__)


def detecter_site(raw: str, filename: str) -> str:
    """Retourne 'marchesonline' | 'boamp_xml' | 'francemarches'."""
    if "marchesonline.com" in raw[:8000] or filename.startswith("ao-"):
        return "marchesonline"
    if (
        "Avis de march" in raw[:300]
        and "Section 1 -" in raw[:2000]
        and "francemarches" not in raw[:5000]
    ):
        return "boamp_xml"
    return "francemarches"


def _infer_plateforme(filename: str, canonical: str) -> str:
    fname = filename.lower()
    if "3boamp" in fname or "boamp" in canonical.lower():
        return "BOAMP"
    if "13joue" in fname:
        return "JOUE"
    if "36parisien" in fname:
        return "PQR"
    if "37ao" in fname:
        return "SCRAPPING REDPOINT"
    if "marchesonline" in canonical.lower() or fname.startswith("ao-"):
        return "Marchés Online"
    return ""


def build_record(filepath: Path) -> dict:
    """
    Lit un fichier HTML, applique le nettoyage Python, et retourne un dict
    avec tous les champs extraits.
    """
    # Étape 1: Nettoyage HTML en Python (remplace tout prétraitement Bash)
    raw, cleaned_html = read_and_clean_html(filepath)
    if not cleaned_html:
        log.warning("Fichier vide ou illisible: %s", filepath.name)
        return {}

    filename  = filepath.name
    site_type = detecter_site(raw, filename)

    # Étape 2: Parsing BeautifulSoup sur HTML nettoyé
    soup      = BeautifulSoup(cleaned_html, "lxml")
    main      = soup.find("main") or soup.find("article") or soup.find("body")
    raw_text  = (main.get_text("\n", strip=True)
                 if main else soup.get_text("\n", strip=True))

    # Étape 3: Nettoyage post-extraction du texte
    text = clean_extracted_text(raw_text)

    # Étape 4: Extraction métier champ par champ
    url      = extract.extraire_url_source(soup)
    ref      = extract.extraire_reference(soup, filename)
    intitule = extract.extraire_intitule(soup, text)
    acheteur = extract.extraire_acheteur(text)
    loc      = extract.extraire_localisation(text, site_type)
    proc     = extract.extraire_procedure(text)
    typ      = extract.extraire_type(text)
    fonc     = extract.extraire_fonction_publique(acheteur, text)
    date     = extract.extraire_date_limite(text)
    dur, rec = extract.extraire_duree(text)
    estim    = extract.extraire_estimation(text)
    plat     = _infer_plateforme(filename, url)

    # Extraction de l'identifiant interne
    int_ref = ""
    m = re.search(r"Identifiant interne\s*[:\s]+([^\n]+)", text)
    if m:
        int_ref = normaliser_texte(m.group(1))

    # Traçabilité du nettoyage
    log.debug("build_record: %s - texte brut: %d chars, nettoyé: %d chars",
              filename, len(raw_text), len(text))

    return {
        "Référence":                        ref,
        "_internal_ref":                    int_ref,
        "_filename":                        filename,
        "Intitulé synthétique":             intitule,
        "Type d'AO":                        proc,
        "Type":                             typ,
        "Fonction publique":                fonc,
        "Acheteur":                         acheteur,
        "Localisation":                     loc,
        "URL source HTTPS":                 url,
        "Date limite de remise des offres": date,
        "Durée initiale du marché":         dur,
        "Reconduction(s)":                  rec,
        "Estimation du marché":             estim,
        "Plateforme":                       plat,
        "_html_cleaned":                    True,
        "_text_length":                     len(text),
    }
