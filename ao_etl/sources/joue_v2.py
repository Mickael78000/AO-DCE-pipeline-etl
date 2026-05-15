"""Extracteur pour les fichiers JOUE (Journal Officiel de l'Union Européenne) - Version 2."""

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


class JoueExtractor(BaseExtractor):
    """Extracteur pour le format JOUE (13/joue/XXXXXXXX).
    
    Caractéristiques:
    - Nom de fichier: 13joueXXXXXXXX-YYYY-*.html
    - Structure avec référence 13/joue/XXXXXXXX
    - "Nom et adresse de l'autorité attribuant le marché"
    - "Valeur totale du marché" ou "Prix à payer"
    """
    source_type = "JOUE"

    def extract(self) -> ExtractionResult:
        result = ExtractionResult(source_type=self.source_type)
        text = self.text()
        
        # 1. Référence depuis contenu ou nom de fichier
        result.reference = self._extract_reference(text)
        
        # 2. Collecter les candidats titre
        title_candidates = []
        
        # Pattern: Objet / Description
        m = re.search(r"Objet\s*:\s*([^.\n]{10,300})", text, re.I)
        if m:
            title_candidates.append(FieldCandidate(
                "title", 
                normalize_text(m.group(1)), 
                "objet_pattern", 
                score=40
            ))
        
        # Pattern: Titre du marché
        m = re.search(r"Titre\s*:\s*([^.\n]{10,300})", text, re.I)
        if m:
            title_candidates.append(FieldCandidate(
                "title",
                normalize_text(m.group(1)),
                "titre_pattern",
                score=45
            ))
        
        # 3. Collecter les candidats acheteur
        buyer_candidates = []
        
        # Nom et adresse de l'autorité
        m = re.search(
            r"Nom\s+et\s+adresse\s+de\s+l['']?autorit[ée]\s+attribuant\s+le\s+march[ée]\s*:\s*([^.\n]{3,150})",
            text,
            re.I
        )
        if m:
            buyer_candidates.append(FieldCandidate(
                "buyer",
                normalize_text(m.group(1)),
                "autorite_attribuant",
                score=45
            ))
        
        # Acheteur public
        m = re.search(r"Acheteur\s+public\s*:\s*([^.\n]{3,150})", text, re.I)
        if m:
            buyer_candidates.append(FieldCandidate(
                "buyer",
                normalize_text(m.group(1)),
                "acheteur_public",
                score=40
            ))
        
        # 4. Champs structurés
        result.location = self._extract_location(text)
        result.deadline = self._extract_deadline(text)
        result.estimation = self._extract_estimation(text)
        result.duration = self._extract_duration(text)
        
        # 5. URL source (JOUE/TED)
        result.raw['url_source'] = self._build_url(result.reference)
        
        # 6. Sélectionner le meilleur titre
        result.title, traces = pick_best_candidate(title_candidates, is_valid_title, score_title)
        for trace in traces:
            result.add_trace(trace)
        
        # 7. Sélectionner le meilleur acheteur
        result.buyer, traces = pick_best_candidate(buyer_candidates, is_valid_buyer, score_buyer)
        for trace in traces:
            result.add_trace(trace)
        
        # 8. Marquer pour révision si champs critiques manquants
        if not result.title or not result.buyer:
            result.review_needed = True
        
        return result
    
    def _extract_reference(self, text: str) -> str:
        """Extrait la référence JOUE (13/joue/XXXXXXXX)."""
        # Pattern dans le texte
        m = re.search(r"13/joue/(\d{8,12})", text, re.I)
        if m:
            return f"13/joue/{m.group(1)}"
        
        # Fallback: depuis le nom de fichier
        name = self.filename()
        m = re.match(r"13joue(\d{8,12})", name, re.I)
        if m:
            return f"13/joue/{m.group(1)}"
        
        return name.replace('.html', '')
    
    def _extract_location(self, text: str) -> str:
        """Extrait la localisation."""
        # Lieu d'exécution
        m = re.search(
            r"Lieu\s+d['']?ex[ée]cution\s*:\s*([^.\n,]{3,100}(?:,\s*[^.\n]{3,50})?)",
            text,
            re.I
        )
        if m:
            return normalize_text(m.group(1))
        
        # Ville + CP
        ville_m = re.search(r"Ville\s*:\s*([^.\n]{3,50})", text, re.I)
        cp_m = re.search(r"Code\s+postal\s*:\s*(\d{5})", text, re.I)
        if ville_m:
            ville = normalize_text(ville_m.group(1))
            if cp_m:
                return f"{ville} ({cp_m.group(1)})"
            return ville
        
        return ""
    
    def _extract_deadline(self, text: str) -> str:
        """Extrait la date limite de réception des offres."""
        # Pattern: Date limite de réception des offres ou des candidatures
        patterns = [
            r"Date\s+limite\s+de\s+r[ée]ception\s+des\s+(?:offres|candidatures)\s*:\s*(\d{2}/\d{2}/\d{4})",
            r"Date\s+limite\s*:\s*(\d{2}/\d{2}/\d{4})",
            r"Date\s+de\s+cl[ôo]ture\s*:\s*(\d{2}/\d{2}/\d{4})",
        ]
        
        for pattern in patterns:
            m = re.search(pattern, text, re.I)
            if m:
                return m.group(1)
        
        return ""
    
    def _extract_estimation(self, text: str) -> str:
        """Extrait l'estimation du marché."""
        # Pattern 1: Valeur totale du marché
        m = re.search(
            r"Valeur\s+totale\s+du\s+march[ée]\s*:\s*(\d[\d\s,.]*)\s*(?:EUR|€)",
            text,
            re.I,
        )
        if m:
            return f"{m.group(1).replace(' ', '').replace(',', '').replace('.', '')} EUR"
        
        # Pattern 2: Prix à payer
        m = re.search(
            r"Prix\s+[àa]\s+payer\s*:\s*(\d[\d\s,.]*)\s*(?:EUR|€)",
            text,
            re.I,
        )
        if m:
            return f"{m.group(1).replace(' ', '').replace(',', '').replace('.', '')} EUR"
        
        # Pattern 3: Budget maximum
        m = re.search(
            r"Budget\s+maximum\s*:\s*(\d[\d\s,.]*)\s*(?:EUR|€)",
            text,
            re.I,
        )
        if m:
            return f"{m.group(1).replace(' ', '').replace(',', '').replace('.', '')} EUR"
        
        return ""
    
    def _extract_duration(self, text: str) -> str:
        """Extrait la durée du marché."""
        # Durée en mois ou ans
        m = re.search(
            r"Dur[ée]e\s+du\s+march[ée]\s*:\s*(\d+)\s+(mois|ans?)",
            text,
            re.I,
        )
        if m:
            return f"{m.group(1)} {m.group(2)}"
        
        return ""
    
    def _build_url(self, reference: str) -> str:
        """Construit l'URL JOUE/TED depuis la référence."""
        if reference and reference.startswith("13/joue/"):
            # URL TED: https://ted.europa.eu/udl?uri=TED:NOTICE:[numero]-[annee]:TEXT:FR
            # Extraction du numéro depuis 13/joue/XXXXXXXX
            parts = reference.split('/')
            if len(parts) >= 3:
                numero = parts[-1]
                # L'année est dans les 2 derniers chiffres du numéro JOUE
                if len(numero) >= 10:
                    annee = numero[4:6]  # Position 4-5 pour l'année (ex: 26 pour 2026)
                    return f"https://ted.europa.eu/udl?uri=TED:NOTICE:{numero}-20{annee}:TEXT:FR"
        
        return ""
