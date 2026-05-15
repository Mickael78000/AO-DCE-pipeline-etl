#!/usr/bin/env python3
"""
Pipeline d'extraction de données à partir de documents RC (Règlement de Consultation)
Version 2 avec OCR Tesseract intégré pour les PDFs scannés.
"""

import json
import subprocess
import os
import re
from pathlib import Path
from datetime import datetime
import tempfile

# Configuration
RC_DIR = Path("/home/michka/Documents/0-AO-DCE/public/rc")
OUTPUT_JSON = Path("/home/michka/Documents/0-AO-DCE/extraction_rc.json")
LOG_FILE = Path("/home/michka/Documents/0-AO-DCE/extraction_rc_v2.log")

# Marchés déjà traités (identifiants consolidés)
EXISTING_MARKETS = {
    "DGFiP-DRS-2500077", "M_3530", "HADPSM260413", "2026-22",
    "2026MDAF0063", "2026/DARC/N°03", "2026A0239", "2026-04",
    "2600006", "260424", "26910A", "26A0133001", "DAF_2026_000243",
    "B26-01107-LS", "MS26084", "2026-CHATBOT", "2026-0206-WEB"
}

# Fichiers correspondants aux marchés déjà traités
PROCESSED_FILES = {
    "DGFIP_DRS_2500077_RC.pdf",
    "AWS-MPI-1816545-RC.pdf",  # M_3530
    "AWS-MPI-1817964-RC.pdf",  # BRGM HADPSM260413
    "RC N° 2026-22.pdf",       # CGSS
    "RC_Assistance et infogerance.pdf",  # EPPGHV
    "Règlement de consultation.pdf",      # Institut Français
    "2026A0239_RC.pdf",
    "2600006 - SPL -  IT Réseau Cloud Sécurité - RC .pdf",
    "260424 - RC PRESTATIONS INFORMATIQUES .pdf",
    "26910A RC.pdf",
    "26A0133001_ RC.pdf",
    "AE20260004_PORTAILS_HISI V2_RC_V1.0.pdf",
    "B26-01107-LS_RC.pdf",
    "RC PHASE CANDIDATURES.pdf",
    "RC candidature -2026-04.pdf",
    "RC chatbot.pdf",
    "RC_20260206_WEB.pdf"
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
        # Vérifier si le PDF a des pages avec texte
        text_test = subprocess.run(
            ["pdftotext", "-f", "1", "-l", "1", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=30
        )
        has_text = len(text_test.stdout.strip()) > 100  # Au moins 100 caractères
        return has_text
    except Exception as e:
        log_message(f"Erreur vérification PDF {pdf_path}: {e}", "ERROR")
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
    except Exception as e:
        log_message(f"Erreur pdftotext {pdf_path}: {e}", "ERROR")
        return None


def extract_text_with_ocr(pdf_path):
    """Extrait le texte d'un PDF scanné avec OCR Tesseract"""
    try:
        # Import des bibliothèques OCR
        try:
            from pdf2image import convert_from_path
            import pytesseract
        except ImportError:
            log_message("Bibliothèques OCR non disponibles (pdf2image/pytesseract)", "ERROR")
            return None
        
        log_message(f"Conversion PDF en images pour OCR: {pdf_path.name}")
        
        # Convertir PDF en images
        images = convert_from_path(str(pdf_path), dpi=300, fmt='png')
        
        log_message(f"{len(images)} pages converties, OCR en cours...")
        
        # OCR sur chaque page
        full_text = []
        for i, image in enumerate(images):
            # OCR avec langue française
            text = pytesseract.image_to_string(image, lang='fra')
            full_text.append(f"\n--- Page {i+1} ---\n{text}")
            
            if (i + 1) % 5 == 0:
                log_message(f"OCR: {i+1}/{len(images)} pages traitées")
        
        return "\n".join(full_text)
        
    except Exception as e:
        log_message(f"Erreur OCR sur {pdf_path}: {e}", "ERROR")
        return None


def extract_text_from_pdf(pdf_path):
    """Extrait le texte d'un PDF (natif ou OCR)"""
    pdf_name = pdf_path.name
    
    # Vérifier si texte natif
    has_text = check_pdf_has_text(pdf_path)
    
    if has_text:
        log_message(f"{pdf_name}: Texte natif détecté → extraction directe")
        text = extract_text_native(pdf_path)
        if text and len(text.strip()) > 200:
            return text, "native"
    
    # Utiliser OCR
    log_message(f"{pdf_name}: PDF scanné ou peu de texte → OCR Tesseract", "WARNING")
    text = extract_text_with_ocr(pdf_path)
    if text and len(text.strip()) > 100:
        return text, "ocr"
    
    return None, "failed"


def clean_text(text):
    """Nettoie le texte extrait"""
    if not text:
        return ""
    # Normaliser les espaces
    text = re.sub(r'\s+', ' ', text)
    # Conserver les sauts de ligne structurels
    text = re.sub(r' (?=\n)', '', text)
    text = re.sub(r'\n ', '\n', text)
    # Supprimer les lignes vides multiples
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def parse_date_french(date_str):
    """Parse une date en français et retourne ISO 8601"""
    if not date_str:
        return None
    
    date_str = date_str.lower().strip()
    months_fr = {
        'janvier': '01', 'février': '02', 'fevrier': '02', 'mars': '03',
        'avril': '04', 'mai': '05', 'juin': '06', 'juillet': '07',
        'août': '08', 'aout': '08', 'septembre': '09', 'octobre': '10',
        'novembre': '11', 'décembre': '12', 'decembre': '12'
    }
    
    # Pattern 1: DD/MM/YYYY ou DD-MM-YYYY
    match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', date_str)
    if match:
        day, month, year = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    
    # Pattern 2: 8 juin 2026
    match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', date_str)
    if match:
        day, month_fr, year = match.groups()
        month = months_fr.get(month_fr, '01')
        return f"{year}-{month}-{int(day):02d}"
    
    # Pattern 3: ISO direct
    match = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if match:
        return date_str[:10]
    
    return None


def extract_field(text, patterns, default=None):
    """Extrait un champ en utilisant une liste de patterns"""
    if not text:
        return default
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if match:
            value = match.group(1).strip()
            value = re.sub(r'\s+', ' ', value)
            if len(value) > 3:  # Éviter les faux positifs trop courts
                return value
    return default


def parse_market_data(text, source_file, extraction_method="native"):
    """Parse les données du marché à partir du texte"""
    if not text:
        return None
    
    data = {
        "identifiant_marche": None,
        "acheteur": None,
        "objet": None,
        "type_procedure": None,
        "date_limite_remise": None,
        "criteres_attribution": [],
        "documents_exiges": [],
        "conditions_participation": None,
        "contact": None,
        "source_file": source_file,
        "extraction_method": extraction_method
    }
    
    # 1. Identifiant du marché
    id_patterns = [
        r'[Rr][ée]f[ée]rence\s*:?\s*([A-Z]?\d{4,8}[A-Z]?\d{0,4})',
        r'[Mm]arch[ée]\s+n[°o]?\s*:?\s*([A-Z]?\d{4,8}[A-Z]?\d{0,4})',
        r'[Cc]onsultation\s+n[°o]?\s*:?\s*([A-Z]?\d{4,8}[A-Z]?\d{0,4})',
        r'[Nn][°o]?\s*([A-Z]\d{2}-\d{4,8})',
        r'[Nn][°o]?\s*([A-Z]\d{4,8})',
    ]
    data["identifiant_marche"] = extract_field(text, id_patterns)
    
    # 2. Acheteur
    acheteur_patterns = [
        r'[Aa]cheteur\s*:?\s*([^\n]{10,100})',
        r'[Pp]ouvoir\s+[Aa]djudicateur\s*:?\s*([^\n]{10,100})',
        r'([A-Z][A-Za-z\s\-\']+(?:Direction|Minist[èe]re|Conseil|Institut|Agence|Centre|Service|Syndicat)[^\n]{10,80})',
    ]
    data["acheteur"] = extract_field(text, acheteur_patterns)
    
    # 3. Objet
    objet_patterns = [
        r'[Oo]bjet\s*:?\s*([^\n]{20,200})',
        r'[Oo]bjet\s+du\s+march[ée]\s*:?\s*([^\n]{20,200})',
        r'[Pp]restation[s]?\s+(?:de\s+)?([^\n]{20,200})',
    ]
    data["objet"] = extract_field(text, objet_patterns)
    
    # 4. Type de procédure
    procedure_patterns = [
        r'([Aa]ppel\s+d\'offres\s+ouvert)',
        r'([Aa]ppel\s+d\'offres\s+restreint)',
        r'([Mm]arch[ée]\s+n[ée]goci[ée])',
        r'([Pp]roc[ée]dure\s+adapt[ée]e)',
        r'([Pp]roc[ée]dure\s+avec\s+n[ée]gociation)',
        r'([Aa]ccord-cadre)',
    ]
    data["type_procedure"] = extract_field(text, procedure_patterns)
    
    # 5. Date limite de remise des offres
    date_patterns = [
        r'[Dd]ate\s+limite[^\n]{0,50}(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
        r'(\d{1,2}\s+(?:janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[ûu]t|septembre|octobre|novembre|d[ée]cembre)\s+\d{4})',
        r'remise\s+(?:des\s+)?(?:offres|plis|candidatures)[^\n]{0,100}(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
    ]
    date_str = extract_field(text, date_patterns)
    data["date_limite_remise"] = parse_date_french(date_str)
    
    # 6. Critères d'attribution
    criteres_match = re.search(
        r'[Cc]rit[èe]re[s]?\s+d[\'\']?(?:attribution|analyse|jugement|s[ée]lection)[^\n]*\n([^\n]{0,50}\n)?(.*?)(?:\n\n|\Z)',
        text, re.IGNORECASE | re.DOTALL
    )
    if criteres_match:
        criteres_text = criteres_match.group(2)
        # Extraire les critères avec pondérations
        critere_items = re.findall(
            r'([A-Z][^\n]{10,100}?)(?:\s+(\d+)\s*(?:points?|%|pourcent))',
            criteres_text
        )
        for crit, pond in critere_items[:5]:
            data["criteres_attribution"].append({
                "critere": crit.strip()[:100],
                "ponderation": f"{pond}%" if pond else "non précisé"
            })
    
    # 7. Documents exigés
    doc_standards = ["CCTP", "CCAP", "CCAG", "DC1", "DC2", "DC4", "BPU", "DPGF", "AE", "RC"]
    for doc in doc_standards:
        if re.search(rf'\b{doc}\b', text, re.IGNORECASE):
            data["documents_exiges"].append(doc)
    
    # 8. Conditions de participation
    conditions_patterns = [
        r'[Cc]ondition[s]?\s+de\s+(?:participation|candidature)[^:]*:?\s*([^\n]{50,300})',
    ]
    data["conditions_participation"] = extract_field(text, conditions_patterns)
    
    # 9. Contact
    contact_patterns = [
        r'[Cc]ontact[^:]*:?\s*([^\n]{20,150})',
        r'[Cc]ourriel[^:]*:?\s*([^\n]{10,80})',
        r'[Tt][ée]l[ée]phone[^:]*:?\s*([^\n]{10,50})',
    ]
    data["contact"] = extract_field(text, contact_patterns)
    
    return data


def is_duplicate(market_data, existing_refs):
    """Vérifie si le marché est un doublon"""
    if not market_data:
        return True
    
    market_id = market_data.get("identifiant_marche")
    if not market_id:
        return False
    
    # Normaliser l'identifiant
    market_id_norm = re.sub(r'\s+', '', market_id.upper())
    
    for existing in existing_refs:
        existing_norm = re.sub(r'\s+', '', existing.upper())
        if market_id_norm == existing_norm:
            return True
    
    return False


def process_pdf_files():
    """Traite tous les fichiers PDF non encore traités"""
    log_message("=" * 70)
    log_message("Démarrage du pipeline d'extraction RC v2 (avec OCR)")
    log_message("=" * 70)
    
    new_markets = []
    processed_count = 0
    error_count = 0
    ocr_count = 0
    native_count = 0
    
    # Lister tous les PDF
    pdf_files = sorted([f for f in RC_DIR.iterdir() if f.suffix.lower() == '.pdf'])
    
    log_message(f"Total fichiers PDF trouvés: {len(pdf_files)}")
    log_message(f"Fichiers déjà traités: {len(PROCESSED_FILES)}")
    
    for pdf_file in pdf_files:
        pdf_name = pdf_file.name
        
        # Vérifier si déjà traité
        if pdf_name in PROCESSED_FILES:
            log_message(f"{pdf_name}: Déjà traité → ignoré")
            continue
        
        log_message(f"\nTraitement: {pdf_name}")
        processed_count += 1
        
        # Extraction du texte (natif ou OCR)
        text, extraction_method = extract_text_from_pdf(pdf_file)
        
        if not text:
            log_message(f"{pdf_name}: Échec extraction (natif + OCR)", "ERROR")
            error_count += 1
            continue
        
        if extraction_method == "ocr":
            ocr_count += 1
        else:
            native_count += 1
        
        # Nettoyage
        text = clean_text(text)
        log_message(f"{pdf_name}: {len(text)} caractères extraits ({extraction_method})")
        
        # Parsing
        market_data = parse_market_data(text, pdf_name, extraction_method)
        
        if not market_data:
            log_message(f"{pdf_name}: Aucune donnée extraite", "WARNING")
            continue
        
        # Afficher les champs trouvés
        fields_found = [k for k, v in market_data.items() if v and v != [] and k not in ("source_file", "extraction_method")]
        log_message(f"{pdf_name}: Champs trouvés: {', '.join(fields_found)}")
        
        # Vérification doublon
        if is_duplicate(market_data, EXISTING_MARKETS):
            log_message(f"{pdf_name}: Doublon détecté ({market_data.get('identifiant_marche')}) → ignoré", "WARNING")
            continue
        
        # Ajouter à la liste
        new_markets.append(market_data)
        log_message(f"{pdf_name}: Nouveau marché ajouté ({market_data.get('identifiant_marche')})")
    
    # Résumé
    log_message("\n" + "=" * 70)
    log_message("RÉSUMÉ")
    log_message("=" * 70)
    log_message(f"Fichiers traités: {processed_count}")
    log_message(f"Nouveaux marchés extraits: {len(new_markets)}")
    log_message(f"Extraction native: {native_count}")
    log_message(f"Extraction OCR: {ocr_count}")
    log_message(f"Erreurs: {error_count}")
    
    return new_markets


def save_results(new_markets):
    """Sauvegarde les résultats dans le fichier JSON existant"""
    if not new_markets:
        log_message("\nAucun nouveau marché à sauvegarder")
        return
    
    try:
        # Lire le JSON existant
        with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
        
        # Convertir les nouveaux marchés au format existant
        formatted_markets = []
        for market in new_markets:
            extraction_note = f"Extrait {market.get('extraction_method', 'auto')}"
            
            formatted = {
                "reference": market["identifiant_marche"],
                "reference_source": market["identifiant_marche"],
                "reference_consolidee": market["identifiant_marche"],
                "identification_confiance": "moyen",
                "titre": market["objet"] or "non précisé",
                "acheteur": {
                    "nom": market["acheteur"] or "non précisé",
                    "structure_juridique": "non précisé",
                    "categorie_normee": "non_precise",
                    "identification_confiance": "moyen"
                },
                "lieu": {
                    "adresse": None,
                    "code_postal": None,
                    "ville": None,
                    "pays": "France",
                    "source_brute": "non précisé"
                },
                "date_limite_remise_offres": {
                    "valeur_iso": market["date_limite_remise"] + "T12:00:00+02:00" if market["date_limite_remise"] else None,
                    "valeur_brute": market["date_limite_remise"] or "non précisé",
                    "fuseau_horaire": "Europe/Paris",
                    "source_brute": market["date_limite_remise"] or "non précisé"
                },
                "plateforme_remise_offres": {
                    "nom": "non précisé",
                    "url": None,
                    "source_brute": "non précisé"
                },
                "type_marche": {
                    "source": market["objet"] or "non précisé",
                    "consolide": "services",
                    "categorie_normee": "services"
                },
                "procedure": {
                    "source": market["type_procedure"] or "non précisé",
                    "consolidee": market["type_procedure"] or "non précisé",
                    "regime": "droit_commun",
                    "niveau_preuve": "deduit"
                },
                "duree": {
                    "valeur": None,
                    "unite": "mois",
                    "structure": "non précisé",
                    "source_brute": "non précisé"
                },
                "montants": {
                    "global": {"valeur": None, "devise": "EUR", "precision": "non précisé", "source_brute": "non précisé", "nature": "non_precise"},
                    "estime": {"valeur": None, "devise": "EUR", "precision": "non précisé", "source_brute": "non précisé", "nature": "non_precise"},
                    "maximum": {"valeur": None, "devise": "EUR", "precision": "non précisé", "source_brute": "non précisé", "nature": "non_precise"},
                    "minimum": {"valeur": None, "devise": "EUR", "precision": "non précisé", "source_brute": "non précisé", "nature": "non_precise"},
                    "nature_marche": "services"
                },
                "allotissement": {
                    "statut": "non_alloti",
                    "nombre_lots": 0,
                    "source_brute": "non précisé"
                },
                "ccag": {
                    "mentionne": False,
                    "source_brute": "non précisé",
                    "principal": None,
                    "categorie_normee": "non_precise",
                    "mode_determination": "non_precise",
                    "niveau_preuve": "absent",
                    "hypothese": None
                },
                "lots": [],
                "criteres_selection": [
                    {
                        "critere": c["critere"],
                        "ponderation": c["ponderation"],
                        "commentaire": "Extrait automatiquement",
                        "source_brute": c["critere"]
                    }
                    for c in (market.get("criteres_attribution") or [])
                ],
                "dce": {
                    "pieces_constitutives": [
                        {"nom": doc, "type_piece": "technique", "obligatoire": True, "source_brute": doc}
                        for doc in (market.get("documents_exiges") or [])
                    ]
                },
                "conflits": [],
                "controle": {
                    "statut_verification": "partiellement_verifie",
                    "niveau_confiance": "moyen",
                    "qualite_extraction": "moyenne",
                    "commentaire": f"{extraction_note} depuis {market['source_file']}"
                },
                "source_extrait": {
                    "fichier": market["source_file"],
                    "page": 1,
                    "section": "Page de garde",
                    "citation_brute": market["objet"] or "non précisé"
                }
            }
            formatted_markets.append(formatted)
        
        # Ajouter aux marchés existants
        existing_data["marches"].extend(formatted_markets)
        
        # Sauvegarder
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
        
        log_message(f"\n{len(formatted_markets)} marchés ajoutés à {OUTPUT_JSON}")
        
    except Exception as e:
        log_message(f"Erreur sauvegarde JSON: {e}", "ERROR")


if __name__ == "__main__":
    # Vider le log
    if LOG_FILE.exists():
        LOG_FILE.unlink()
    
    # Traitement
    new_markets = process_pdf_files()
    
    # Sauvegarde
    save_results(new_markets)
    
    # Afficher résultat
    print("\n" + "=" * 70)
    print("EXTRACTION TERMINÉE")
    print("=" * 70)
    print(f"Log: {LOG_FILE}")
