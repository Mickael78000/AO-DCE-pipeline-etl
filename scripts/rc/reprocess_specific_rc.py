#!/usr/bin/env python3
"""
Re-traitement des 7 marchés spécifiques avec OCR pour nettoyer et corriger les données.
"""

import json
import subprocess
import os
import re
from pathlib import Path
from datetime import datetime

# Configuration
RC_DIR = Path("/home/michka/Documents/0-AO-DCE/public/rc")
JSON_FILE = Path("/home/michka/Documents/0-AO-DCE/extraction_rc.json")
LOG_FILE = Path("/home/michka/Documents/0-AO-DCE/reprocess_rc.log")

# Les 7 fichiers à re-traiter
TARGET_FILES = {
    "RC candidature -2026-04.pdf": "2026-04",
    "2600006 - SPL -  IT Réseau Cloud Sécurité - RC .pdf": "2600006",
    "260424 - RC PRESTATIONS INFORMATIQUES .pdf": "260424",
    "26910A RC.pdf": "26910A",
    "26A0133001_ RC.pdf": "26A0133001",
    "RC chatbot.pdf": "2026-CHATBOT",
    "RC_20260206_WEB.pdf": "2026-0206-WEB"
}


def log_message(message, level="INFO"):
    """Log un message avec timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [{level}] {message}"
    print(log_line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_line + "\n")


def check_pdf_has_text(pdf_path):
    """Vérifie si le PDF contient du texte extractible"""
    try:
        text_test = subprocess.run(
            ["pdftotext", "-f", "1", "-l", "1", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=30
        )
        return len(text_test.stdout.strip()) > 100
    except Exception as e:
        return False


def extract_text_native(pdf_path):
    """Extrait le texte natif d'un PDF"""
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.stdout
    except:
        return None


def extract_text_with_ocr(pdf_path):
    """Extrait le texte d'un PDF scanné avec OCR Tesseract"""
    try:
        from pdf2image import convert_from_path
        import pytesseract
        
        log_message(f"Conversion PDF en images pour OCR: {pdf_path.name}")
        images = convert_from_path(str(pdf_path), dpi=300, fmt='png')
        
        log_message(f"{len(images)} pages converties, OCR en cours...")
        
        full_text = []
        for i, image in enumerate(images):
            text = pytesseract.image_to_string(image, lang='fra')
            full_text.append(f"\n--- Page {i+1} ---\n{text}")
            if (i + 1) % 5 == 0:
                log_message(f"OCR: {i+1}/{len(images)} pages traitées")
        
        return "\n".join(full_text)
    except Exception as e:
        log_message(f"Erreur OCR: {e}", "ERROR")
        return None


def clean_text(text):
    """Nettoie le texte extrait"""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r' (?=\n)', '', text)
    text = re.sub(r'\n ', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def parse_date_french(date_str):
    """Parse une date en français"""
    if not date_str:
        return None
    
    date_str = date_str.lower().strip()
    months_fr = {
        'janvier': '01', 'février': '02', 'fevrier': '02', 'mars': '03',
        'avril': '04', 'mai': '05', 'juin': '06', 'juillet': '07',
        'août': '08', 'aout': '08', 'septembre': '09', 'octobre': '10',
        'novembre': '11', 'décembre': '12', 'decembre': '12'
    }
    
    match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', date_str)
    if match:
        day, month, year = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    
    match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', date_str)
    if match:
        day, month_fr, year = match.groups()
        month = months_fr.get(month_fr, '01')
        return f"{year}-{month}-{int(day):02d}"
    
    return None


def extract_field(text, patterns, default=None):
    """Extrait un champ avec patterns"""
    if not text:
        return default
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if match:
            value = match.group(1).strip()
            value = re.sub(r'\s+', ' ', value)
            if len(value) > 3:
                return value
    return default


def parse_market_data(text, source_file, expected_ref):
    """Parse les données du marché"""
    if not text:
        return None
    
    data = {
        "identifiant_marche": expected_ref,  # Utiliser la référence connue
        "acheteur": None,
        "objet": None,
        "type_procedure": None,
        "date_limite_remise": None,
        "criteres_attribution": [],
        "documents_exiges": [],
        "conditions_participation": None,
        "contact": None,
        "source_file": source_file,
        "extraction_method": "reprocess_v2"
    }
    
    # Acheteur
    acheteur_patterns = [
        r'[Aa]cheteur\s*:?\s*([^\n]{10,100})',
        r'[Pp]ouvoir\s+[Aa]djudicateur\s*:?\s*([^\n]{10,100})',
        r'([A-Z][A-Za-z\s\-\']+(?:Direction|Minist[èe]re|Conseil|Institut|Agence|Centre|Service|Syndicat|Région)[^\n]{10,80})',
    ]
    data["acheteur"] = extract_field(text, acheteur_patterns)
    
    # Objet
    objet_patterns = [
        r'[Oo]bjet\s*:?\s*([^\n]{20,200})',
        r'[Oo]bjet\s+du\s+march[ée]\s*:?\s*([^\n]{20,200})',
        r'[Pp]restation[s]?\s+(?:de\s+)?([^\n]{20,200})',
    ]
    data["objet"] = extract_field(text, objet_patterns)
    
    # Type de procédure
    procedure_patterns = [
        r'([Aa]ppel\s+d\'offres\s+ouvert)',
        r'([Aa]ppel\s+d\'offres\s+restreint)',
        r'([Mm]arch[ée]\s+n[ée]goci[ée])',
        r'([Pp]roc[ée]dure\s+adapt[ée]e)',
        r'([Pp]roc[ée]dure\s+avec\s+n[ée]gociation)',
        r'([Aa]ccord-cadre)',
    ]
    data["type_procedure"] = extract_field(text, procedure_patterns)
    
    # Date limite
    date_patterns = [
        r'[Dd]ate\s+limite[^\n]{0,50}(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
        r'(\d{1,2}\s+(?:janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[ûu]t|septembre|octobre|novembre|d[ée]cembre)\s+\d{4})',
        r'remise\s+(?:des\s+)?(?:offres|plis|candidatures)[^\n]{0,100}(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
    ]
    date_str = extract_field(text, date_patterns)
    data["date_limite_remise"] = parse_date_french(date_str)
    
    # Critères
    criteres_match = re.search(
        r'[Cc]rit[èe]re[s]?\s+d[\'\']?(?:attribution|analyse|jugement|s[ée]lection)[^\n]*\n([^\n]{0,50}\n)?(.*?)(?:\n\n|\Z)',
        text, re.IGNORECASE | re.DOTALL
    )
    if criteres_match:
        criteres_text = criteres_match.group(2)
        critere_items = re.findall(
            r'([A-Z][^\n]{10,100}?)(?:\s+(\d+)\s*(?:points?|%|pourcent))',
            criteres_text
        )
        for crit, pond in critere_items[:5]:
            data["criteres_attribution"].append({
                "critere": crit.strip()[:100],
                "ponderation": f"{pond}%" if pond else "non précisé"
            })
    
    # Documents
    doc_standards = ["CCTP", "CCAP", "CCAG", "DC1", "DC2", "DC4", "BPU", "DPGF", "AE", "RC"]
    for doc in doc_standards:
        if re.search(rf'\b{doc}\b', text, re.IGNORECASE):
            data["documents_exiges"].append(doc)
    
    return data


def process_specific_pdfs():
    """Traite les 7 fichiers PDF spécifiques"""
    log_message("=" * 70)
    log_message("Re-traitement des 7 marchés spécifiques")
    log_message("=" * 70)
    
    new_markets = []
    
    for pdf_name, expected_ref in TARGET_FILES.items():
        pdf_path = RC_DIR / pdf_name
        
        if not pdf_path.exists():
            log_message(f"{pdf_name}: Fichier non trouvé", "ERROR")
            continue
        
        log_message(f"\nTraitement: {pdf_name} (référence attendue: {expected_ref})")
        
        # Extraction du texte
        has_text = check_pdf_has_text(pdf_path)
        
        if has_text:
            log_message(f"{pdf_name}: Texte natif détecté")
            text = extract_text_native(pdf_path)
            extraction_method = "native"
        else:
            log_message(f"{pdf_name}: PDF scanné → OCR", "WARNING")
            text = extract_text_with_ocr(pdf_path)
            extraction_method = "ocr"
        
        if not text:
            log_message(f"{pdf_name}: Échec extraction", "ERROR")
            continue
        
        text = clean_text(text)
        log_message(f"{pdf_name}: {len(text)} caractères extraits")
        
        # Parsing
        market_data = parse_market_data(text, pdf_name, expected_ref)
        
        if not market_data:
            log_message(f"{pdf_name}: Aucune donnée extraite", "WARNING")
            continue
        
        # Afficher les champs trouvés
        fields_found = [k for k, v in market_data.items() if v and v != [] and k not in ("source_file", "extraction_method")]
        log_message(f"{pdf_name}: Champs trouvés: {', '.join(fields_found)}")
        
        new_markets.append(market_data)
        log_message(f"{pdf_name}: Marché {expected_ref} prêt pour mise à jour")
    
    log_message("\n" + "=" * 70)
    log_message(f"Marchés traités: {len(new_markets)}")
    
    return new_markets


def update_json(new_markets):
    """Met à jour le JSON en remplaçant les anciennes entrées"""
    if not new_markets:
        log_message("Aucun marché à mettre à jour")
        return
    
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    marches = data.get("marches", [])
    
    # Supprimer les anciennes entrées des 7 marchés
    refs_to_update = {m["identifiant_marche"] for m in new_markets}
    cleaned_marches = [m for m in marches if m.get("reference_consolidee") not in refs_to_update]
    
    removed_count = len(marches) - len(cleaned_marches)
    log_message(f"Anciennes entrées supprimées: {removed_count}")
    
    # Ajouter les nouvelles entrées
    for market in new_markets:
        formatted = {
            "reference": market["identifiant_marche"],
            "reference_source": market["identifiant_marche"],
            "reference_consolidee": market["identifiant_marche"],
            "identification_confiance": "moyen",
            "titre": market["objet"] or "non précisé",
            "acheteur": {
                "nom": market["acheteur"] or "non précisé",
                "structure_juridique": "non précisé",
                "categorie_normee": "non_precise"
            },
            "lieu": {"adresse": None, "code_postal": None, "ville": None, "pays": "France", "source_brute": "non précisé"},
            "date_limite_remise_offres": {
                "valeur_iso": market["date_limite_remise"] + "T12:00:00+02:00" if market["date_limite_remise"] else None,
                "valeur_brute": market["date_limite_remise"] or "non précisé",
                "fuseau_horaire": "Europe/Paris"
            },
            "plateforme_remise_offres": {"nom": "non précisé", "url": None},
            "type_marche": {"source": market["objet"] or "non précisé", "consolide": "services", "categorie_normee": "services"},
            "procedure": {"source": market["type_procedure"] or "non précisé", "consolidee": market["type_procedure"] or "non précisé", "regime": "droit_commun"},
            "duree": {"valeur": None, "unite": "mois", "structure": "non précisé"},
            "montants": {
                "global": {"valeur": None, "devise": "EUR", "precision": "non précisé", "source_brute": "non précisé", "nature": "non_precise"},
                "estime": {"valeur": None, "devise": "EUR", "precision": "non précisé", "source_brute": "non précisé", "nature": "non_precise"},
                "maximum": {"valeur": None, "devise": "EUR", "precision": "non précisé", "source_brute": "non précisé", "nature": "non_precise"},
                "minimum": {"valeur": None, "devise": "EUR", "precision": "non précisé", "source_brute": "non précisé", "nature": "non_precise"},
                "nature_marche": "services"
            },
            "allotissement": {"statut": "non_alloti", "nombre_lots": 0},
            "ccag": {"mentionne": False, "source_brute": "non précisé", "principal": None, "categorie_normee": "non_precise", "mode_determination": "non_precise", "niveau_preuve": "absent", "hypothese": None},
            "lots": [],
            "criteres_selection": [{"critere": c["critere"], "ponderation": c["ponderation"], "commentaire": "Extrait automatiquement", "source_brute": c["critere"]} for c in (market.get("criteres_attribution") or [])],
            "dce": {"pieces_constitutives": [{"nom": doc, "type_piece": "technique", "obligatoire": True, "source_brute": doc} for doc in (market.get("documents_exiges") or [])]},
            "conflits": [],
            "controle": {"statut_verification": "partiellement_verifie", "niveau_confiance": "moyen", "qualite_extraction": "moyenne", "commentaire": f"Re-traité {market.get('extraction_method')} depuis {market['source_file']}"},
            "source_extrait": {"fichier": market["source_file"], "page": 1, "section": "Page de garde", "citation_brute": market["objet"] or "non précisé"}
        }
        cleaned_marches.append(formatted)
    
    data["marches"] = cleaned_marches
    
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    log_message(f"JSON mis à jour: {len(new_markets)} marchés ajoutés")
    log_message(f"Total marchés dans JSON: {len(cleaned_marches)}")


if __name__ == "__main__":
    if LOG_FILE.exists():
        LOG_FILE.unlink()
    
    new_markets = process_specific_pdfs()
    update_json(new_markets)
    
    print("\n" + "=" * 70)
    print("RE-TRAITEMENT TERMINÉ")
    print("=" * 70)
    print(f"Log: {LOG_FILE}")
