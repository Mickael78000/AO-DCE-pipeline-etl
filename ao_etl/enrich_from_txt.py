"""
Module d'enrichissement basé exclusivement sur les fichiers .txt extraits.
Lit directement les descriptifs texte sans repasser par le HTML.
"""

import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from ao_etl.enrich_descriptif import (
    LotInfo, DescriptifEnrichi, parse_montant, parse_cpv, parse_lots
)

log = logging.getLogger(__name__)


def read_descriptif_txt(txt_path: Path) -> Optional[str]:
    """Lit un fichier descriptif .txt s'il existe."""
    if not txt_path.exists():
        return None
    
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        log.warning(f"Erreur lecture {txt_path}: {e}")
        return None


def find_txt_file(reference: str, html_dir: Path) -> Optional[Path]:
    """
    Trouve le fichier .txt correspondant à une référence.
    Essaie plusieurs stratégies de matching.
    """
    if not reference:
        return None
    
    # Nettoyer la référence
    ref_clean = reference.replace('/', '').replace('-', '').replace('_', '').lower()
    
    # Stratégie 1: Nom exact avec suffixe _descriptif.txt
    for txt_path in html_dir.glob("*_descriptif.txt"):
        # Extraire le nom de base (sans _descriptif.txt)
        base_name = txt_path.stem.replace('_descriptif', '').lower()
        
        # Vérifier correspondance
        if ref_clean == base_name.replace('-', '').replace('_', ''):
            return txt_path
        
        # Correspondance partielle
        if ref_clean in base_name or base_name.replace('-', '') in ref_clean:
            return txt_path
    
    # Stratégie 2: Patterns spécifiques (BOAMP, joue, etc.)
    # BOAMP: 3/boamp/2647639 → chercher 3boamp2647639
    boamp_match = re.search(r'(\d+)[/\\]boamp[/\\](\d+)', reference, re.IGNORECASE)
    if boamp_match:
        pattern = f"{boamp_match.group(1)}boamp{boamp_match.group(2)}"
        for txt_path in html_dir.glob("*_descriptif.txt"):
            if pattern in txt_path.stem.lower():
                return txt_path
    
    # joue: 13/joue/00267116 → chercher 13joue00267116
    joue_match = re.search(r'(\d+)[/\\]joue[/\\](\d+)', reference, re.IGNORECASE)
    if joue_match:
        pattern = f"{joue_match.group(1)}joue{joue_match.group(2)}"
        for txt_path in html_dir.glob("*_descriptif.txt"):
            if pattern in txt_path.stem.lower():
                return txt_path
    
    # Stratégie 3: Recherche dans le contenu des fichiers .txt
    for txt_path in html_dir.glob("*_descriptif.txt"):
        text = read_descriptif_txt(txt_path)
        if text and reference in text[:5000]:  # Chercher dans les 5000 premiers caractères
            return txt_path
    
    return None


def enrich_from_txt_file(txt_path: Path) -> Optional[DescriptifEnrichi]:
    """
    Enrichit les données à partir d'un fichier .txt.
    Similar to enrich_from_descriptif but reads from pre-extracted txt.
    """
    text = read_descriptif_txt(txt_path)
    if not text:
        log.warning(f"Impossible de lire {txt_path}")
        return None
    
    enrichi = DescriptifEnrichi(
        reference="",
        departements_publication=[],
        annonce_numero="",
        acheteur_nom="",
        acheteur_forme_juridique="",
        acheteur_activite="",
        procedure_type="",
        procedure_identifiant="",
        montant_estime=None,
        montant_maximum=None,
        montant_minimum=None,
        cpv_principal="",
        cpv_supplementaires=[],
        lots=[],
        criteres_attribution="",
        duree="",
        options_description="",
        conflits_detectes=[],
        devise="EUR"
    )
    
    # Départements
    match = re.search(r'Département\(s\) de publication\s*[:\s]+([\d,\s]+)', text)
    if match:
        deps = match.group(1).replace(" ", "").split(",")
        enrichi.departements_publication = [d.strip() for d in deps if d.strip()]
    
    # Annonce numéro
    match = re.search(r'Annonce n°\s*[:\s]+([^\n]+)', text)
    if match:
        enrichi.annonce_numero = match.group(1).strip()
    
    # Référence (Identifiant interne)
    match = re.search(r'Identifiant interne\s*[:\s]+([^\n]+)', text)
    if match:
        enrichi.reference = match.group(1).strip()
    
    # Acheteur
    match = re.search(r'Nom officiel\s*[:\s]+([^\n]+)', text)
    if match:
        enrichi.acheteur_nom = match.group(1).strip()
    
    match = re.search(r"Forme juridique de l'acheteur\s*[:\s]+([^\n]+)", text)
    if match:
        enrichi.acheteur_forme_juridique = match.group(1).strip()
    
    match = re.search(r"Activité du pouvoir adjudicateur\s*[:\s]+([^\n]+)", text)
    if match:
        enrichi.acheteur_activite = match.group(1).strip()
    
    # Type de procédure
    match = re.search(r'Type de procédure\s*[:\s]+([^\n]+)', text)
    if match:
        enrichi.procedure_type = match.group(1).strip()
    
    match = re.search(r'Identifiant de la procédure\s*[:\s]+([^\n]+)', text)
    if match:
        enrichi.procedure_identifiant = match.group(1).strip()
    
    # Valeurs globales
    match = re.search(r'Valeur estimée hors TVA\s*[:\s]+([\d\s,\.]+)', text)
    if match:
        enrichi.montant_estime = parse_montant(match.group(1))
    
    match = re.search(r'Valeur maximale.*?[:\s]+([\d\s,\.]+)', text)
    if match:
        enrichi.montant_maximum = parse_montant(match.group(1))
    
    match = re.search(r'Valeur minimale.*?[:\s]+([\d\s,\.]+)', text)
    if match:
        enrichi.montant_minimum = parse_montant(match.group(1))
    
    # CPV
    enrichi.cpv_principal, enrichi.cpv_supplementaires = parse_cpv(text)
    
    # Lots
    enrichi.lots = parse_lots(text)
    
    # Critères d'attribution
    match = re.search(r"Critères d'attribution\s*[:\s]+([^\n]+)", text, re.IGNORECASE)
    if match:
        enrichi.criteres_attribution = match.group(1).strip()
    else:
        match = re.search(r'Cout\s*:\s*(\d+)%.*?Technique\s*:\s*(\d+)%', text, re.IGNORECASE)
        if match:
            enrichi.criteres_attribution = f"Cout: {match.group(1)}%, Technique: {match.group(2)}%"
    
    # Durée
    match = re.search(r'Durée\s*[:\s]+([^\n]+)', text)
    if match:
        enrichi.duree = match.group(1).strip()
    
    # Options
    match = re.search(r'Description des options\s*[:\s]+([^\n]{20,300})', text)
    if match:
        enrichi.options_description = match.group(1).strip()
    
    # Détection de conflits
    conflits = []
    
    refs = re.findall(r'Identifiant interne\s*[:\s]+([^\n]+)', text)
    if len(set(refs)) > 1:
        conflits.append(f"References multiples: {set(refs)}")
    
    montants_lots = [l.montant_estime for l in enrichi.lots if l.montant_estime]
    if enrichi.montant_estime and montants_lots:
        total_lots = sum(montants_lots)
        if abs(total_lots - enrichi.montant_estime) > enrichi.montant_estime * 0.1:
            conflits.append(f"Somme lots ({total_lots}) != global ({enrichi.montant_estime})")
    
    enrichi.conflits_detectes = conflits
    
    log.info(f"Enrichissement TXT: {len(enrichi.lots)} lots, CPV={enrichi.cpv_principal}, "
             f"montant={enrichi.montant_estime}, conflits={len(conflits)}")
    
    return enrichi
