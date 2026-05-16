"""Extracteur pour les fichiers PLACE numérique (orgAcronyme) - Version 2."""

from __future__ import annotations

import re

from .base_v2 import BaseExtractor, ExtractionResult, FieldCandidate
from .validation_v2 import (
    normalize_text,
    pick_best_candidate,
    score_buyer,
    score_title,
    is_valid_buyer,
    is_valid_title,
)

# Patterns regex pour PLACE
REF_RE = re.compile(r"\b[A-Z]\d{2}-\d{5}-[A-Z]{2}\b")  # Ex: B26-01107-LS
DATE_RE = re.compile(r"\b\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}\b")  # Ex: 10/06/2026 16:00
DEPT_RE = re.compile(r"\(\d{2,3}\)\s+[^\n]+")  # Ex: (38) Isère


class PlaceNumericExtractor(BaseExtractor):
    """Extracteur pour le format PLACE numérique.
    
    Caractéristiques:
    - URL contient orgAcronyme
    - Contient souvent "Détail de la consultation" (titre générique à rejeter)
    - Structure avec "Entité d'Achat" (priorité acheteur)
    - Références au format XX-XXXXX-XX
    """
    source_type = "PLACE_NUMERIC"

    def extract(self) -> ExtractionResult:
        result = ExtractionResult(source_type=self.source_type)
        text = self.text()
        lines = [normalize_text(x) for x in text.splitlines() if normalize_text(x)]
        
        # 1. Référence (pattern XX-XXXXX-XX)
        ref_match = REF_RE.search(text)
        if ref_match:
            result.reference = ref_match.group(0)
        
        # 2. Date limite (pattern DD/MM/YYYY HH:MM)
        date_match = DATE_RE.search(text)
        if date_match:
            result.deadline = date_match.group(0)
        
        # 3. Localisation (pattern (XX) Département)
        dept_match = DEPT_RE.search(text)
        if dept_match:
            result.location = dept_match.group(0)
        
        # 4. Titre - collecter les candidats
        title_candidates = []
        buyer_candidates = []
        
        for i, line in enumerate(lines):
            # Candidats négatifs (à rejeter)
            if line.lower() == "détail de la consultation":
                title_candidates.append(FieldCandidate("title", line, "header_generic", score=-100))
            
            # Candidats positifs
            if result.reference and line == result.reference and i + 1 < len(lines):
                # La ligne après la référence est souvent le titre
                title_candidates.append(FieldCandidate("title", lines[i + 1], "line_after_reference", score=30))
            
            # Titres métiers commençant par des verbes d'action
            if (line.startswith("Prestations ") or 
                line.startswith("Assistance ") or 
                line.startswith("Maintenance ") or
                line.startswith("Fourniture ") or
                line.startswith("Travaux ") or
                line.startswith("Conception ") or
                line.startswith("Réalisation ")):
                title_candidates.append(FieldCandidate("title", line, "business_title_line", score=20))
            
            # Acheteurs faux (catégories)
            if line.lower() == "autres organismes":
                buyer_candidates.append(FieldCandidate("buyer", line, "category_label", score=-100))
            
            # Acheteurs réels (entités structurées)
            if "AO /" in line or "CEA /" in line or " / " in line:
                buyer_candidates.append(FieldCandidate("buyer", line, "entity_line", score=40))
            
            # Entité d'achat (priorité max)
            if "entité" in line.lower() and "/" in line:
                buyer_candidates.append(FieldCandidate("buyer", line, "entite_achat", score=50))
        
        # 5. Sélectionner le meilleur titre
        result.title, traces = pick_best_candidate(title_candidates, is_valid_title, score_title)
        for trace in traces:
            result.add_trace(trace)
        
        # 6. Sélectionner le meilleur acheteur
        result.buyer, traces = pick_best_candidate(buyer_candidates, is_valid_buyer, score_buyer)
        for trace in traces:
            result.add_trace(trace)
        
        # 6.5 Type de procédure, nature du marché, fonction publique
        result.raw['procedure_type'] = self._procedure_type(text)
        result.raw['contract_nature'] = self._contract_nature(text)
        result.raw['fonction_publique'] = self._fonction_publique(text, result.buyer)
        
        # 7. Marquer pour révision si champs critiques manquants
        if not result.title or not result.buyer:
            result.review_needed = True
        
        return result
    
    def _procedure_type(self, text: str) -> str:
        """Extrait le type de procédure."""
        patterns = [
            r"Type de proc[ée]dure\s*[:\-\n]\s*([^\n]+)",
            r"Proc[ée]dure\s*[:\-\n]\s*([^\n]+)",
            r"(Appel d'offres ouvert|Proc[ée]dure n[ée]goci[ée]e|March[ée] n[ée]goci[ée]|Dialogue comp[ée]titif)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return normalize_text(m.group(1))
        return ""
    
    def _contract_nature(self, text: str) -> str:
        """Extrait la nature du marché."""
        patterns = [
            r"Nature du march[ée]\s*[:\-\n]\s*([^\n]+)",
            r"Type de march[ée]\s*[:\-\n]\s*([^\n]+)",
            r"(Services|Fournitures|Travaux|Prestations intellectuelles)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                nature = normalize_text(m.group(1))
                if "service" in nature.lower() or "intellectuel" in nature.lower():
                    return "Services"
                elif "fourniture" in nature.lower():
                    return "Fournitures"
                elif "travail" in nature.lower() or "travaux" in nature.lower():
                    return "Travaux"
                return nature
        return ""
    
    def _fonction_publique(self, text: str, buyer: str) -> str:
        """Détecte la fonction publique."""
        forme_match = re.search(r"Forme juridique.*?acheteur\s*[:\-\n]\s*([^\n]+)", text, re.IGNORECASE)
        activite_match = re.search(r"Activit[ée].*?principale\s*[:\-\n]\s*([^\n]+)", text, re.IGNORECASE)
        
        forme = forme_match.group(1).strip() if forme_match else ""
        activite = activite_match.group(1).strip() if activite_match else ""
        buyer_str = buyer or ""
        
        if any(x in activite.lower() for x in ["santé", "hospital", "soin"]) or \
           any(x in buyer_str.lower() for x in ["chu ", "chru", "hôpital", "hopital"]):
            return "hospitaliere"
        elif any(x in forme.lower() for x in ["organisme de droit public", "établissement public", "ministère", "état"]):
            return "etat"
        elif any(x in forme.lower() for x in ["collectivité", "territoriale"]):
            return "territoriale"
        elif any(x in buyer_str.lower() for x in ["ministère", "dgfip"]):
            return "etat"

        if "santé" in text.lower() or "hospitalier" in text.lower():
            return "hospitaliere"
        elif "collectivité" in text.lower():
            return "territoriale"
        elif "ministère" in text.lower() or "état" in text.lower():
            return "etat"

        return "-"
