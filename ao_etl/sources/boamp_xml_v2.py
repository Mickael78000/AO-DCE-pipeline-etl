"""Extracteur pour les fichiers BOAMP XML - Version 2."""

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


class BoampExtractor(BaseExtractor):
    """Extracteur pour le format BOAMP XML.
    
    Caractéristiques:
    - Structure avec couples label/valeur
    - "Nom officiel", "Titre", "Identifiant interne"
    - "Valeur estimée hors TVA", "Date limite de réception des offres"
    """
    source_type = "BOAMP_XML"

    def extract(self) -> ExtractionResult:
        result = ExtractionResult(source_type=self.source_type)
        text = self.text()
        
        # 1. Collecter les candidats titre
        title_candidates = [
            FieldCandidate("title", self._value_after_label(text, "Titre"), "label_titre", score=40),
        ]
        
        # 2. Collecter les candidats acheteur
        buyer_candidates = [
            FieldCandidate("buyer", self._value_after_label(text, "Nom officiel"), "label_nom_officiel", score=40),
            FieldCandidate("buyer", self._value_after_label(text, "Acheteur"), "label_acheteur", score=30),
        ]
        
        # Rejeter explicitement les faux candidats
        org_info = self._value_after_label(
            text, 
            "Organisation qui fournit des informations complémentaires sur la procédure de passation de marché"
        )
        if org_info:
            buyer_candidates.append(FieldCandidate("buyer", org_info, "org_info_complementaires", score=-50))
        
        # 3. Champs structurés directs
        result.reference = self._value_after_label(text, "Identifiant interne")
        result.estimation = self._money_after_label(text, "Valeur estimée hors TVA")
        result.duration = self._duration(text)
        result.deadline = self._deadline(text)
        result.location = self._location(text)
        
        # 4. Sélectionner le meilleur titre
        result.title, traces = pick_best_candidate(title_candidates, is_valid_title, score_title)
        for trace in traces:
            result.add_trace(trace)
        
        # 5. Sélectionner le meilleur acheteur
        result.buyer, traces = pick_best_candidate(buyer_candidates, is_valid_buyer, score_buyer)
        for trace in traces:
            result.add_trace(trace)
        
        # 6. Marquer pour révision si champs critiques manquants
        if not result.title or not result.buyer:
            result.review_needed = True
        
        return result

    def _value_after_label(self, text: str, label: str) -> str:
        """Extrait la valeur après un label (pattern label\\n+valeur)."""
        pattern = re.compile(rf"{re.escape(label)}\s*\n+(.+?)(?:\n|$)", re.I)
        m = pattern.search(text)
        return normalize_text(m.group(1)) if m else ""

    def _money_after_label(self, text: str, label: str) -> str:
        """Extrait une valeur monétaire après un label."""
        pattern = re.compile(rf"{re.escape(label)}\s*\n+([\d.,\s]+)\s*\n+(Euro|EUR)", re.I)
        m = pattern.search(text)
        if m:
            value = normalize_text(m.group(1))
            currency = normalize_text(m.group(2))
            return f"{value} {currency}"
        return ""

    def _duration(self, text: str) -> str:
        """Extrait la durée (X Mois ou X Ans)."""
        # Pattern: Durée\\n+XX\\n+Mois/Années
        m = re.search(r"Dur[ée]e\s*\n+(\d+)\s*\n+(Mois|Ans|Ann[ée]es)", text, re.I)
        if m:
            value = m.group(1)
            unit = normalize_text(m.group(2))
            return f"{value} {unit}"
        return ""

    def _deadline(self, text: str) -> str:
        """Extrait la date limite de réception des offres."""
        # Pattern: Date limite de réception des offres\\n+DD/MM/YYYY\\n+à\\n+HH:MM
        m = re.search(
            r"Date limite de r[ée]ception des offres\s*\n+(\d{2}/\d{2}/\d{4})\s*\n+[àa]?\s*\n*(\d{2}:\d{2})",
            text,
            re.I
        )
        if m:
            date = m.group(1)
            time = m.group(2)
            return f"{date} {time}"
        return ""

    def _location(self, text: str) -> str:
        """Extrait la localisation (Ville + Code postal + NUTS)."""
        city = self._value_after_label(text, "Ville")
        cp = self._value_after_label(text, "Code postal")
        nuts = self._value_after_label(text, "Subdivision pays (NUTS)")
        
        parts = [p for p in [city, cp, nuts] if p]
        return " / ".join(parts) if parts else ""
