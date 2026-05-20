"""
Module d'enrichissement basé sur extract_descriptif.py.
Extrait les données structurées du descriptif texte pour compléter le CSV.
"""

import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from ao_etl.parsing.extract_descriptif import extract_descriptif

log = logging.getLogger(__name__)


@dataclass
class LotInfo:
    """Information sur un lot."""
    numero: str
    titre: str
    objet: str
    description: str
    cpv_principal: str
    cpv_supplementaires: List[str]
    montant_estime: Optional[float]
    montant_maximum: Optional[float]


@dataclass
class DescriptifEnrichi:
    """Données enrichies extraites du descriptif."""
    # Champs obligatoires (sans valeur par défaut)
    reference: str
    departements_publication: List[str]
    annonce_numero: str
    
    # Acheteur détaillé
    acheteur_nom: str
    acheteur_forme_juridique: str
    acheteur_activite: str
    
    # Procédure
    procedure_type: str
    procedure_identifiant: str
    
    # Valeurs
    montant_estime: Optional[float]
    montant_maximum: Optional[float]
    montant_minimum: Optional[float]
    
    # CPV
    cpv_principal: str
    cpv_supplementaires: List[str]
    
    # Lots
    lots: List[LotInfo]
    
    # Critères
    criteres_attribution: str
    
    # Délai
    duree: str
    
    # Options/Reconduction
    options_description: str
    
    # Conflits détectés
    conflits_detectes: List[str]
    
    # Champs avec valeur par défaut (à la fin)
    devise: str = "EUR"


def parse_montant(val_str: str) -> Optional[float]:
    """Parse un montant en euro, gère les formats européens."""
    if not val_str:
        return None
    # Nettoyer et extraire le nombre
    val_str = val_str.replace(" ", "").replace(".", "").replace(",", ".")
    match = re.search(r'(\d+(?:\.\d+)?)', val_str)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return None


def parse_cpv(text: str) -> tuple:
    """Extrait le CPV principal et les CPV supplémentaires."""
    cpv_principal = ""
    cpv_supp = []
    
    # Pattern: "cpv): 72500000 Services informatiques"
    cpv_pattern = r'\(\s*cpv\s*\)\s*[:\s]+(\d+)\s+([^\n]+)'
    matches = re.findall(cpv_pattern, text, re.IGNORECASE)
    
    for i, (code, libelle) in enumerate(matches):
        cpv_entry = f"{code} {libelle.strip()}"
        if i == 0:
            cpv_principal = code
        else:
            cpv_supp.append(code)
    
    return cpv_principal, cpv_supp


def parse_lots(text: str) -> List[LotInfo]:
    """Parse les sections de lots (Section 5)."""
    lots = []
    
    # Diviser par sections de lots
    lot_sections = re.split(r'Section\s*5\s*-\s*Lot', text, flags=re.IGNORECASE)
    
    for i, section in enumerate(lot_sections[1:], 1):  # Skip avant première section
        lot = LotInfo(
            numero="",
            titre="",
            objet="",
            description="",
            cpv_principal="",
            cpv_supplementaires=[],
            montant_estime=None,
            montant_maximum=None
        )
        
        # Numéro du lot (5.1 Identifiant technique du lot : LOT-0001)
        match = re.search(r'Identifiant technique du lot\s*[:\s]+([^\n]+)', section, re.IGNORECASE)
        if match:
            lot.numero = match.group(1).strip()
        
        # Titre
        match = re.search(r'Titre\s*[:\s]+([^\n]{10,100})', section, re.IGNORECASE)
        if match:
            lot.titre = match.group(1).strip()
        
        # Description
        match = re.search(r'Description\s*[:\s]+([^\n]{10,200})', section, re.IGNORECASE)
        if match:
            lot.description = match.group(1).strip()
        
        # CPV du lot
        lot.cpv_principal, lot.cpv_supplementaires = parse_cpv(section)
        
        # Montants du lot
        match = re.search(r'Valeur estimée hors TVA\s*[:\s]+([\d\s,\.]+)', section, re.IGNORECASE)
        if match:
            lot.montant_estime = parse_montant(match.group(1))
        
        match = re.search(r'Valeur maximale.*?[:\s]+([\d\s,\.]+)', section, re.IGNORECASE)
        if match:
            lot.montant_maximum = parse_montant(match.group(1))
        
        # Objet
        match = re.search(r'Nature du marché\s*[:\s]+([^\n]+)', section, re.IGNORECASE)
        if match:
            lot.objet = match.group(1).strip()
        
        if lot.numero or lot.titre:
            lots.append(lot)
    
    return lots


def enrich_from_descriptif(html_path: Path) -> Optional[DescriptifEnrichi]:
    """Enrichit les données à partir du descriptif texte."""
    
    # Extraire le texte brut
    text = extract_descriptif(str(html_path))
    if not text:
        log.warning(f"Impossible d'extraire le descriptif de {html_path}")
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
    
    # Valeurs globales (Section 2)
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
        # Chercher les pondérations
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
    
    # Références incohérentes
    refs = re.findall(r'Identifiant interne\s*[:\s]+([^\n]+)', text)
    if len(set(refs)) > 1:
        conflits.append(f"References multiples: {set(refs)}")
    
    # Montants contradictoires
    montants_lots = [l.montant_estime for l in enrichi.lots if l.montant_estime]
    if enrichi.montant_estime and montants_lots:
        total_lots = sum(montants_lots)
        if abs(total_lots - enrichi.montant_estime) > enrichi.montant_estime * 0.1:
            conflits.append(f"Somme lots ({total_lots}) != global ({enrichi.montant_estime})")
    
    enrichi.conflits_detectes = conflits
    
    log.info(f"Enrichissement: {len(enrichi.lots)} lots, CPV={enrichi.cpv_principal}, "
             f"montant={enrichi.montant_estime}, conflits={len(conflits)}")
    
    return enrichi


def enrich_csv_row(row: Dict[str, Any], enrichi: DescriptifEnrichi) -> Dict[str, Any]:
    """Fusionne les données enrichies avec une ligne CSV existante."""
    
    # Ne pas écraser si déjà présent, sauf si la valeur enrichie est plus précise
    
    if not row.get('Estimation du marché') and enrichi.montant_estime:
        row['Estimation du marché'] = enrichi.montant_estime
    
    if not row.get('Estimation (devise)') and enrichi.devise:
        row['Estimation (devise)'] = enrichi.devise
    
    # Ajouter les nouvelles colonnes enrichies
    row['cpv_principal'] = enrichi.cpv_principal
    row['cpv_supplementaires'] = ", ".join(enrichi.cpv_supplementaires)
    row['nombre_lots'] = len(enrichi.lots)
    row['lots_detail'] = "; ".join([
        f"Lot {l.numero}: {l.titre[:50]}... (CPV {l.cpv_principal})" 
        for l in enrichi.lots
    ])
    row['criteres_attribution'] = enrichi.criteres_attribution
    row['duree_reelle'] = enrichi.duree
    row['options_reconduction'] = enrichi.options_description
    row['departements_publication'] = ", ".join(enrichi.departements_publication)
    row['annonce_numero'] = enrichi.annonce_numero
    
    # Détecter les conflits
    if enrichi.conflits_detectes:
        row['conflits_detectes'] = "; ".join(enrichi.conflits_detectes)
        row['niveau_confiance'] = 'moyen' if row.get('niveau_confiance') == 'eleve' else 'faible'
    
    return row
