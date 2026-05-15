#!/usr/bin/env python3
"""Extraction de localisation, durée, reconduction, montant_estime depuis les HTML bruts.

Sources supportées :
- JOUE (FranceMarchés) : sections 5.1.x, data-labels-key
- BOAMP (FranceMarchés) : sections fr-text--bold + div.section
- MarchésOnline : texte semi-structuré <br/> separated
- PlaceNumeric (f2h/d3f/s2d/g7h/d4t) : labels col-md-4 + div col-md-8

Sortie : JSON structuré + patch CSV optionnel.
"""

import csv
import json
import re
import sys
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup, Tag


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _clean(text: str) -> str:
    """Nettoie un texte extrait : espaces multiples, retours chariot."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _extract_number(text: str) -> Optional[str]:
    """Extrait un nombre (éventuellement avec virgules/points) d'un texte."""
    m = re.search(r"[\d][,.\d\s]*[\d]", text)
    if m:
        return m.group(0).replace(" ", "").replace("\xa0", "")
    m = re.search(r"\d+", text)
    return m.group(0) if m else None


def _normalize_amount(raw: str) -> str:
    """Normalise un montant : '400,000' → '400000', '18,025,000' → '18025000'."""
    if not raw:
        return ""
    # Replace comma-as-thousand-sep: 1,440,000 → 1440000
    # But keep comma-as-decimal if pattern is X,XX (2 digits after)
    cleaned = raw.replace("\xa0", "").replace(" ", "")
    # If pattern is like 400,000 or 1,440,000 → thousands separator
    if re.match(r"^\d{1,3}(,\d{3})+$", cleaned):
        return cleaned.replace(",", "")
    # If pattern is like 18.02 (decimal) keep as-is
    return cleaned


def _format_amount(value: str, currency: str = "EUR") -> str:
    if not value:
        return ""
    normalized = _normalize_amount(value)
    return f"{normalized} {currency}" if normalized else ""


# ═══════════════════════════════════════════════════════════════════════════
# JOUE EXTRACTOR (FranceMarchés, data-labels-key)
# ═══════════════════════════════════════════════════════════════════════════

def _extract_joue(soup: BeautifulSoup) -> dict:
    """Extrait les champs depuis un avis JOUE (structuré avec data-labels-key)."""
    result = {
        "localisation": "", "duree": "", "reconduction": "",
        "montant_estime": "", "justifications": [],
    }

    # --- Localisation (sidebar) ---
    loc_span = soup.find("span", class_="js-weborama-annonce-tag-localisation")
    if loc_span:
        result["localisation"] = _clean(loc_span.get_text())
        result["justifications"].append(
            f"Localisation extraite du champ affiché FranceMarchés : {result['localisation']}")

    # --- Durée : section 5.1.3 ---
    durees = []
    for span in soup.find_all("span", attrs={"data-labels-key": "auxiliary|text|estimated-duration"}):
        container = span.find_parent("div", class_="subsection-content")
        if not container:
            continue
        dur_span = container.find("span", attrs={"data-labels-key": "business-term|name|BT-36"})
        if dur_span:
            # Next sibling data spans
            data_spans = dur_span.find_parent("div").find_all("span", class_="data")
            if data_spans:
                val = _clean(data_spans[0].get_text())
                unit = _clean(data_spans[1].get_text()) if len(data_spans) > 1 else "Mois"
                if val.isdigit():
                    durees.append((int(val), unit))

    if durees:
        # Take the first (or longest if multi-lot)
        val, unit = durees[0]
        if "an" in unit.lower():
            val = val * 12
        result["duree"] = f"{val} mois"
        result["justifications"].append(
            f"Durée extraite de la section 5.1.3 Durée estimée : {val} {unit}")

    # --- Reconduction : section 5.1.4 ---
    reconductions = []
    for span in soup.find_all("span", attrs={"data-labels-key": "auxiliary|text|renewal"}):
        container = span.find_parent("div", class_="subsection-content")
        if not container:
            continue
        # BT-58 = nombre max
        bt58 = container.find("span", attrs={"data-labels-key": "business-term|name|BT-58"})
        nb_max = ""
        if bt58:
            data = bt58.find_parent("div").find("span", class_="data")
            if data:
                nb_max = _clean(data.get_text())

        # BT-57 = détails
        bt57 = container.find("span", attrs={"data-labels-key": "business-term|name|BT-57"})
        detail = ""
        if bt57:
            data = bt57.find_parent("div").find("span", class_="data")
            if data:
                detail = _clean(data.get_text())

        reconductions.append({"nb_max": nb_max, "detail": detail})

    if reconductions:
        r = reconductions[0]
        parts = []
        if r["nb_max"]:
            parts.append(f"{r['nb_max']} reconduction(s)")
        if r["detail"]:
            parts.append(r["detail"])
        result["reconduction"] = " — ".join(parts) if parts else ""
        result["justifications"].append(
            f"Reconduction extraite de 5.1.4 : nb_max={r['nb_max']}, détail={r['detail'][:60]}")

    # --- Montant : section 2.1.3 or 5.1.5 (Valeur estimée hors TVA) ---
    for label_key in ["auxiliary|text|value", "field|name|BT-27-Procedure"]:
        for span in soup.find_all("span", attrs={"data-labels-key": label_key}):
            container = span.find_parent("div")
            if not container:
                continue
            ht_span = container.find("span", attrs={"data-labels-key": "business-term|name|BT-27"})
            if ht_span:
                data_spans = ht_span.find_parent("div").find_all("span", class_="data")
                if data_spans:
                    val = _clean(data_spans[0].get_text())
                    result["montant_estime"] = _format_amount(val, "EUR")
                    result["justifications"].append(
                        f"Montant estimé extrait de Valeur estimée hors TVA : {result['montant_estime']}")
                    break
        if result["montant_estime"]:
            break

    return result


# ═══════════════════════════════════════════════════════════════════════════
# BOAMP EXTRACTOR (FranceMarchés, fr-text--bold)
# ═══════════════════════════════════════════════════════════════════════════

def _extract_boamp(soup: BeautifulSoup) -> dict:
    """Extrait les champs depuis un avis BOAMP (FranceMarchés, structure div.section)."""
    result = {
        "localisation": "", "duree": "", "reconduction": "",
        "montant_estime": "", "justifications": [],
    }

    # --- Localisation (sidebar) ---
    loc_span = soup.find("span", class_="js-weborama-annonce-tag-localisation")
    if loc_span:
        # Include the parenthesized code if present
        parent = loc_span.find_parent()
        if parent:
            full_text = _clean(parent.get_text())
            # Try to extract "Seine-Saint-Denis (93)" pattern
            result["localisation"] = full_text if full_text else _clean(loc_span.get_text())
        else:
            result["localisation"] = _clean(loc_span.get_text())
        result["justifications"].append(
            f"Localisation extraite du champ affiché : {result['localisation']}")

    # --- Structured sections via fr-text--bold ---
    bold_spans = soup.find_all("span", class_="fr-text--bold")

    for span in bold_spans:
        label = _clean(span.get_text())
        section_div = span.find_parent("div", class_="section")
        if not section_div:
            continue

        # Durée
        if label == "Durée estimée":
            dur_div = section_div.find("div", class_="section")
            if dur_div:
                texts = [_clean(s.get_text()) for s in dur_div.find_all("span")]
                # Look for pattern: "Durée" ":" "48" "" "Mois"
                for i, t in enumerate(texts):
                    if t.isdigit():
                        unit = texts[i + 1] if i + 1 < len(texts) else "Mois"
                        val = int(t)
                        if "an" in unit.lower():
                            val = val * 12
                        result["duree"] = f"{val} mois"
                        result["justifications"].append(
                            f"Durée extraite de la section 5.1.3 Durée estimée : {t} {unit}")
                        break

        # Valeur estimée hors TVA
        if "Valeur estimée hors TVA" in label:
            texts = [_clean(s.get_text()) for s in section_div.find_all("span")]
            for t in texts:
                num = _extract_number(t)
                if num and len(num) >= 3:
                    result["montant_estime"] = _format_amount(num, "EUR")
                    result["justifications"].append(
                        f"Montant estimé extrait de Valeur estimée hors TVA : {result['montant_estime']}")
                    break

        # Valeur maximale accord-cadre (fallback)
        if "Valeur maximale" in label and not result["montant_estime"]:
            texts = [_clean(s.get_text()) for s in section_div.find_all("span")]
            for t in texts:
                num = _extract_number(t)
                if num and len(num) >= 3:
                    result["montant_estime"] = _format_amount(num, "EUR")
                    result["justifications"].append(
                        f"Montant extrait de Valeur maximale accord-cadre : {result['montant_estime']}")
                    break

        # Reconduction
        if "Nombre maximum de reconductions" in label:
            data_spans = section_div.find_all("span")
            for s in data_spans:
                t = _clean(s.get_text())
                if t.isdigit():
                    result["reconduction"] = f"{t} reconduction(s)"
                    result["justifications"].append(
                        f"Reconduction : nombre max = {t}")
                    break

    # --- Also check for reconduction detail ---
    for span in bold_spans:
        label = _clean(span.get_text())
        if "Autres informations sur le renouvellement" in label:
            section_div = span.find_parent("div", class_="section")
            if section_div:
                texts = [_clean(s.get_text()) for s in section_div.find_all("span")
                         if "Autres informations" not in _clean(s.get_text())
                         and s.get("class") != ["fr-text--bold"]]
                detail = " ".join(t for t in texts if t and t != ":")
                if detail and result["reconduction"]:
                    result["reconduction"] += f" — {detail}"
                elif detail:
                    result["reconduction"] = detail
                result["justifications"].append(f"Détail reconduction : {detail[:80]}")

    # --- Lieu d'exécution (structured, NUTS) ---
    if not result["localisation"]:
        for span in bold_spans:
            if "Lieu d'exécution" in _clean(span.get_text()):
                section_div = span.find_parent("div", class_="section")
                if section_div:
                    nuts_div = section_div.find("div", class_="section")
                    if nuts_div:
                        texts = [_clean(s.get_text()) for s in nuts_div.find_all("span")
                                 if not s.get("class")]
                        loc = " ".join(t for t in texts if t and t != ":" and len(t) > 2)
                        if loc:
                            result["localisation"] = loc
                            result["justifications"].append(
                                f"Localisation extraite de Lieu d'exécution NUTS : {loc}")
                            break

    return result


# ═══════════════════════════════════════════════════════════════════════════
# MARCHES ONLINE EXTRACTOR (text/br based)
# ═══════════════════════════════════════════════════════════════════════════

def _extract_marches_online(soup: BeautifulSoup) -> dict:
    """Extrait depuis un avis MarchésOnline (texte <br/> séparé).

    Priorité : on prend la PREMIÈRE occurrence de chaque champ (= niveau marché),
    pas la dernière (= dernier lot).
    """
    result = {
        "localisation": "", "duree": "", "reconduction": "",
        "montant_estime": "", "justifications": [],
    }

    full_text = soup.get_text(separator="\n")
    lines = [_clean(l) for l in full_text.split("\n") if _clean(l)]

    for i, line in enumerate(lines):
        # Durée (première occurrence = marché global ou lot 1)
        if not result["duree"]:
            if re.match(r"^Durée\s*:", line, re.I) or "Durée estimée" in line:
                m = re.search(r"(\d+)\s*(mois|an|ans|Mois)", line, re.I)
                if not m and i + 1 < len(lines):
                    m = re.search(r"(\d+)\s*(mois|an|ans|Mois)", lines[i + 1], re.I)
                if m:
                    val = int(m.group(1))
                    unit = m.group(2).lower()
                    if "an" in unit:
                        val = val * 12
                    result["duree"] = f"{val} mois"
                    result["justifications"].append(f"Durée extraite : {m.group(0)}")

        # Valeur estimée hors TVA (première occurrence = marché global)
        if not result["montant_estime"] and "Valeur estimée hors TVA" in line:
            m = re.search(r"([\d,.\s\xa0]+)\s*(euro|EUR|€)", line, re.I)
            if m:
                result["montant_estime"] = _format_amount(m.group(1).strip(), "EUR")
                result["justifications"].append(
                    f"Montant extrait de Valeur estimée hors TVA : {result['montant_estime']}")

        # Valeur maximale accord-cadre (fallback, première occurrence)
        if not result["montant_estime"] and "Valeur maximale" in line:
            m = re.search(r"([\d,.\s\xa0]+)\s*(euro|EUR|€)", line, re.I)
            if m:
                result["montant_estime"] = _format_amount(m.group(1).strip(), "EUR")
                result["justifications"].append(
                    f"Montant extrait de Valeur maximale AC : {result['montant_estime']}")

        # Reconduction
        if not result["reconduction"] and "reconduction" in line.lower():
            m = re.search(r"Nombre maximum de reconductions\s*:?\s*(\d+)", line, re.I)
            if m:
                result["reconduction"] = f"{m.group(1)} reconduction(s)"
                result["justifications"].append(f"Reconduction : nb_max={m.group(1)}")
            else:
                # Détail textuel : ne capturer que si le texte parle vraiment de reconduction
                text = line.strip()
                if (len(text) > 15
                        and "reconduction" in text.lower()
                        and not re.match(r"^\d+\.\d+\.\d+\.?\s*Reconduction$", text, re.I)
                        and "Informations complémentaires" not in text):
                    result["reconduction"] = text[:120]
                    result["justifications"].append(f"Reconduction (texte) : {text[:80]}")

        # Localisation
        if not result["localisation"] and re.match(r"^Localisation\s*:", line, re.I):
            val = re.sub(r"^Localisation\s*:\s*", "", line, flags=re.I).strip()
            if val:
                result["localisation"] = val
                result["justifications"].append(f"Localisation extraite : {val}")

    return result


# ═══════════════════════════════════════════════════════════════════════════
# PLACE NUMERIC EXTRACTOR (f2h, d3f, s2d, g7h, d4t)
# ═══════════════════════════════════════════════════════════════════════════

def _extract_place_numeric(soup: BeautifulSoup) -> dict:
    """Extrait depuis une plateforme PlaceNumeric (structure label/value col-md)."""
    result = {
        "localisation": "", "duree": "", "reconduction": "",
        "montant_estime": "", "justifications": [],
    }

    # Find label/value pairs
    for label_el in soup.find_all("label", class_="col-md-4"):
        label_text = _clean(label_el.get_text())
        value_el = label_el.find_next_sibling("div", class_="col-md-8")
        if not value_el:
            continue
        value_text = _clean(value_el.get_text())

        if "Lieu" in label_text and "exécution" in label_text.lower():
            result["localisation"] = value_text
            result["justifications"].append(
                f"Localisation extraite du champ '{label_text}' : {value_text}")

        if "Durée" in label_text.lower() and not result["duree"]:
            m = re.search(r"(\d+)\s*(mois|an|ans)", value_text, re.I)
            if m:
                val = int(m.group(1))
                if "an" in m.group(2).lower():
                    val = val * 12
                result["duree"] = f"{val} mois"
                result["justifications"].append(
                    f"Durée extraite du champ '{label_text}' : {value_text}")

        if "montant" in label_text.lower() or "estimation" in label_text.lower():
            m = re.search(r"([\d,.\s]+)\s*(EUR|€|euro)", value_text, re.I)
            if m:
                result["montant_estime"] = _format_amount(m.group(1).strip(), "EUR")
                result["justifications"].append(
                    f"Montant extrait du champ '{label_text}' : {value_text[:60]}")

        if "reconduction" in label_text.lower():
            result["reconduction"] = value_text[:120]
            result["justifications"].append(
                f"Reconduction extraite du champ '{label_text}' : {value_text[:60]}")

    return result


# ═══════════════════════════════════════════════════════════════════════════
# DÉTECTION DE SOURCE ET DISPATCH
# ═══════════════════════════════════════════════════════════════════════════

def detect_source(soup: BeautifulSoup, filename: str) -> str:
    """Détecte le type de source à partir du HTML."""
    text = soup.get_text()[:3000]

    # PlaceNumeric platforms
    if "orgAcronyme=" in filename:
        return "place_numeric"

    # MarchesOnline
    if filename.startswith("ao-") or "marches-online" in text.lower() or "marchés en ligne" in text.lower():
        return "marches_online"

    # JOUE vs BOAMP on FranceMarchés
    if soup.find("span", attrs={"data-labels-key": True}):
        # Check if it has JOUE-style data-labels-key
        if soup.find("span", attrs={"data-labels-key": "auxiliary|text|estimated-duration"}):
            return "joue"
        return "boamp"

    if soup.find("span", class_="fr-text--bold"):
        return "boamp"

    # Fallback
    if "francemarches" in text.lower():
        if "JOUE" in text[:5000]:
            return "joue"
        return "boamp"

    return "unknown"


def extract_fields(html_path: Path) -> dict:
    """Extrait les 4 champs d'un fichier HTML."""
    with open(html_path, encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f, "html.parser")

    source = detect_source(soup, html_path.name)

    if source == "joue":
        result = _extract_joue(soup)
    elif source == "boamp":
        result = _extract_boamp(soup)
    elif source == "marches_online":
        result = _extract_marches_online(soup)
    elif source == "place_numeric":
        result = _extract_place_numeric(soup)
    else:
        # Try all extractors and merge non-empty fields
        result = _extract_boamp(soup)
        if not any([result["localisation"], result["duree"],
                     result["reconduction"], result["montant_estime"]]):
            result = _extract_marches_online(soup)

    result["source_type"] = source
    result["fichier"] = html_path.name
    return result


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    html_dir = Path("data/raw/html")
    csv_path = Path("data/output/final-v3-consolidated-classified-rule.csv")

    # Load current CSV to map fichier_source_html → reference
    file_to_ref = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            src = row.get("fichier_source_html", "").strip()
            if src:
                file_to_ref[src] = row["reference"]

    # Process all HTML files
    results = []
    for html_file in sorted(html_dir.glob("*.html")):
        ref = file_to_ref.get(html_file.name, "")

        extraction = extract_fields(html_file)

        results.append({
            "reference": ref,
            "fichier": html_file.name,
            "source_type": extraction["source_type"],
            "localisation": extraction["localisation"],
            "duree": extraction["duree"],
            "reconduction": extraction["reconduction"],
            "montant_estime": extraction["montant_estime"],
            "justifications": extraction.get("justifications", []),
        })

    # Print summary
    n = len(results)
    matched = sum(1 for r in results if r["reference"])
    loc_filled = sum(1 for r in results if r["localisation"])
    dur_filled = sum(1 for r in results if r["duree"])
    rec_filled = sum(1 for r in results if r["reconduction"])
    mont_filled = sum(1 for r in results if r["montant_estime"])

    print(f"Fichiers traités : {n} ({matched} avec référence CSV)")
    print(f"Localisation     : {loc_filled}/{n} ({loc_filled/n*100:.0f}%)")
    print(f"Durée            : {dur_filled}/{n} ({dur_filled/n*100:.0f}%)")
    print(f"Reconduction     : {rec_filled}/{n} ({rec_filled/n*100:.0f}%)")
    print(f"Montant estimé   : {mont_filled}/{n} ({mont_filled/n*100:.0f}%)")
    print()

    # Output JSON
    output = []
    for r in results:
        output.append({
            "reference": r["reference"],
            "localisation": r["localisation"],
            "duree": r["duree"],
            "reconduction": r["reconduction"],
            "montant_estime": r["montant_estime"],
            "source_extrait": f"{r['source_type']}:{r['fichier']}",
            "justification_courte": " | ".join(r["justifications"]) if r["justifications"] else "Aucune donnée trouvée",
        })

    json_path = Path("data/output/extraction-champs-html.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"JSON écrit : {json_path}")

    # Print detailed results for matched references
    print("\n" + "=" * 100)
    print("RÉSULTATS DÉTAILLÉS (références CSV)")
    print("=" * 100)
    for r in results:
        if not r["reference"]:
            continue
        print(f"\n{'─' * 80}")
        print(f"Ref: {r['reference']}")
        print(f"  Fichier       : {r['fichier']}")
        print(f"  Source        : {r['source_type']}")
        print(f"  Localisation  : {r['localisation'] or '(vide)'}")
        print(f"  Durée         : {r['duree'] or '(vide)'}")
        print(f"  Reconduction  : {r['reconduction'] or '(vide)'}")
        print(f"  Montant       : {r['montant_estime'] or '(vide)'}")
        for j in r["justifications"]:
            print(f"  → {j}")


if __name__ == "__main__":
    main()
