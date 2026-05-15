"""Extracteur pour les fichiers France Marchés - Version 2."""

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


class FranceMarchesExtractor(BaseExtractor):
    """Extracteur pour le format France Marchés.
    
    Caractéristiques:
    - Couche éditoriale avec "Intitulé de l'appel d'offre public"
    - Couche légale structurée avec labels
    - JSON weboramaItemTag parfois présent
    """
    source_type = "FRANCE_MARCHES"

    def extract(self) -> ExtractionResult:
        result = ExtractionResult(source_type=self.source_type)
        text = self.text()
        html = self.context.html
        
        # 1. Collecter les candidats titre
        title_candidates = [
            FieldCandidate("title", self._editorial_title(text), "editorial_header", score=30),
            FieldCandidate("title", self._label_value(text, "Intitulé du marché"), "legal_text_title", score=40),
            FieldCandidate("title", self._label_value(text, "Description succincte du marché"), "description_short", score=10),
        ]
        
        # Titre depuis JSON weboramaItemTag si présent
        weborama_title = self._weborama_title(html)
        if weborama_title:
            title_candidates.append(FieldCandidate("title", weborama_title, "weborama_json", score=45))
        
        # 2. Collecter les candidats acheteur (plusieurs sources pour éviter faux positifs)
        buyer_candidates = [
            FieldCandidate("buyer", self._editorial_buyer(text), "editorial_buyer_block", score=30),
            FieldCandidate("buyer", self._label_value(text, "Nom complet de l'acheteur"), "legal_nom_complet", score=40),
            FieldCandidate("buyer", self._label_value(text, "Nom officiel"), "legal_nom_officiel", score=35),
        ]
        
        # Ajouter candidats acheteur avec patterns spécifiques pour prioriser les vrais organismes
        # (hôpitaux, collectivités) sur les intermédiaires (communautés de communes pour autrui)
        buyer_patterns = [
            (r'Nom officiel\s*:\s*(Centre Hospitalier[^\n]+)', 'nom_officiel_chu', 50),
            (r'Nom officiel\s*:\s*(CHU[^\n]+)', 'nom_officiel_chu', 50),
            (r'Nom officiel\s*:\s*(Hôpital[^\n]+)', 'nom_officiel_hopital', 50),
            (r'Nom officiel\s*:\s*([^.]*?(?:Commune|Ville|Mairie|Département|Région)[^.]+)', 'nom_officiel_collectivite', 45),
        ]
        for pattern, rule, score in buyer_patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                val = normalize_text(m.group(1))
                if val and len(val) > 3:
                    buyer_candidates.append(FieldCandidate("buyer", val, rule, score=score))
        
        # Acheteur depuis JSON weboramaItemTag si présent
        weborama_buyer = self._weborama_buyer(html)
        if weborama_buyer:
            buyer_candidates.append(FieldCandidate("buyer", weborama_buyer, "weborama_json", score=45))
        
        # 3. Champs structurés
        result.reference = (
            self._label_value(text, "Identifiant interne")
            or self._guess_reference_from_filename()
        )
        result.deadline = self._deadline(text)
        result.location = self._label_value(text, "Lieu principal d'exécution du marché")
        
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

    def _editorial_title(self, text: str) -> str:
        """Extrait le titre depuis l'en-tête éditorial."""
        m = re.search(r"Intitul[ée] de l'appel d'offre public\s+(.+?)(?:\n\d|\n##|\nTexte|\Z)", text, re.I | re.S)
        if m:
            return normalize_text(m.group(1))
        return ""

    def _editorial_buyer(self, text: str) -> str:
        """Extrait l'acheteur depuis le bloc éditorial."""
        m = re.search(
            r"Nom et adresse officiels de l['']?organisme acheteur public\s+(.+?)(?:\n\d|\n##|\nTexte|\Z)",
            text,
            re.I | re.S,
        )
        if m:
            # Prendre la première ligne non vide
            first_line = normalize_text(m.group(1).splitlines()[0])
            return first_line
        return ""

    def _label_value(self, text: str, label: str) -> str:
        """Extrait la valeur après un label."""
        m = re.search(rf"{re.escape(label)}\s*[:\-\n]\s*(.+?)(?:\n|$)", text, re.I)
        if m:
            return normalize_text(m.group(1))
        return ""

    def _deadline(self, text: str) -> str:
        """Extrait la date limite.
        
        Supporte plusieurs formats:
        - "Date limite de réception des offres : 08/06/2026 12:00:00 (UTC+02:00)"
        - "Date et heure limites de réception des offres : 08/06/2026 à 12:00"
        - "Date de clôture : 08/06/2026"
        """
        # Pattern 1: Date limite de réception des offres avec heure (format France Marchés moderne)
        m = re.search(
            r"Date limite de r[ée]ception des offres\s*:\s*(\d{2}/\d{2}/\d{4})\s*(\d{2}:\d{2}:\d{2})",
            text,
            re.I,
        )
        if m:
            date = m.group(1)
            time = m.group(2)
            return f"{date} {time}"
        
        # Pattern 2: Date et heure limites (format ancien)
        m = re.search(
            r"Date et heure limites? de r[ée]ception des (?:plis|offres)\s*[:\-\n]\s*(\d{2}/\d{2}/\d{4})\s*[àa]?\s*(\d{2}h?\d{2})",
            text,
            re.I | re.S,
        )
        if m:
            date = m.group(1)
            time = m.group(2).replace("h", ":")
            return f"{date} {time}"
        
        # Pattern 3: Date limite sans heure explicite
        m = re.search(
            r"Date limite de r[ée]ception des offres\s*:\s*(\d{2}/\d{2}/\d{4})",
            text,
            re.I,
        )
        if m:
            return m.group(1)
        
        return ""

    def _weborama_title(self, html: str) -> str:
        """Extrait le titre depuis le JSON weboramaItemTag."""
        m = re.search(r'title_article\\u0022\s*:\\u0022([^\\u0022]+)', html, re.I)
        if m:
            return self._decode_unicode_escapes(m.group(1))
        return ""

    def _weborama_buyer(self, html: str) -> str:
        """Extrait l'acheteur depuis le JSON weboramaItemTag."""
        m = re.search(r'buyer_name\\u0022\s*:\\u0022([^\\u0022]+)', html, re.I)
        if m:
            return self._decode_unicode_escapes(m.group(1))
        return ""

    def _decode_unicode_escapes(self, text: str) -> str:
        """Décode les séquences Unicode échappées."""
        if not text:
            return ""
        
        replacements = {
            '\\u0020': ' ',
            '\\u0027': "'",
            '\\u0022': '"',
            '\\u002D': '-',
            '\\u00E9': 'é',
            '\\u00E8': 'è',
            '\\u00EA': 'ê',
            '\\u00E0': 'à',
            '\\u00E2': 'â',
            '\\u00E7': 'ç',
            '\\u00F4': 'ô',
            '\\u00FB': 'û',
            '\\u00F9': 'ù',
            '\\u00EB': 'ë',
            '\\u00EF': 'ï',
            '\\u00FC': 'ü',
            '\\u2019': "'",
        }
        
        result = text
        for seq, char in replacements.items():
            result = result.replace(seq, char)
        
        return result

    def _guess_reference_from_filename(self) -> str:
        """Extrait une référence depuis le nom de fichier."""
        name = self.filename()
        # Pattern: prefixe-nombre ou juste identifiant
        m = re.match(r"([a-z0-9]+(?:-[a-z0-9]+)*)", name, re.I)
        if m:
            return m.group(1)
        return ""
