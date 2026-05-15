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
        
        # 7. Marquer pour révision si champs critiques manquants
        if not result.title or not result.buyer:
            result.review_needed = True
        
        return result
