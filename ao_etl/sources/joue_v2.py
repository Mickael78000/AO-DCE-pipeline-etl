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
        """Extrait l'estimation du marché (JOUE/TED)."""
        html = self.context.html
        
        # === Patterns dans le texte ===
        text_patterns = [
            (r"Valeur\s+totale\s+du\s+march[ée]\s*[:\-]?\s*(\d[\d\s,.]*)\s*(?:EUR|€)", 40),
            (r"Prix\s+[àa]\s+payer\s*[:\-]?\s*(\d[\d\s,.]*)\s*(?:EUR|€)", 35),
            (r"Budget\s*(?:maximum|maxi)?\s*[:\-]?\s*(\d[\d\s,.]*)\s*(?:EUR|€)", 35),
            (r"Estimation\s+(?:totale|globale)?\s*[:\-]?\s*(\d[\d\s,.]*)\s*(?:EUR|€)", 35),
            (r"Montant\s*(?:total|global)?\s*[:\-]?\s*(\d[\d\s,.]*)\s*(?:EUR|€)", 35),
            (r"Prix\s*(?:plafond|maximum)?\s*[:\-]?\s*(\d[\d\s,.]*)\s*(?:EUR|€)", 30),
            (r"Valeur\s*du\s*march[ée]\s*[:\-]?\s*(\d[\d\s,.]*)\s*(?:EUR|€)", 40),
        ]
        
        for pattern, score in text_patterns:
            m = re.search(pattern, text, re.I)
            if m:
                val = m.group(1).replace(' ', '').replace(',', '').replace('.', '')
                return f"{val} EUR"
        
        # === Patterns HTML spécifiques TED ===
        html_patterns = [
            (r'VALUE\s*[:=]\s*["\']?(\d[\d\s,.]*)\s*(?:EUR|€)?["\']?', 40),
            (r'class=["\'][^"\']*valorisation[^"\']*["\'][^>]*>(\d[\d\s,.]*)', 35),
            (r'<span[^>]*class=[^>]*value[^>]*>(\d[\d\s,.]*)', 30),
        ]
        
        for pattern, score in html_patterns:
            m = re.search(pattern, html, re.I)
            if m:
                val = m.group(1).replace(' ', '').replace(',', '').replace('.', '')
                return f"{val} EUR"
        
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
        """Construit ou extrait l'URL JOUE/TED."""
        html = self.context.html
        
        # 1. Chercher URL TED directement dans le HTML
        m = re.search(r'(https?://ted\.europa\.eu/[^"\'\s<>]+)', html, re.I)
        if m:
            return m.group(1)
        
        # 2. Chercher référence TED format
        m = re.search(r'NOTICE[:\-]?(\d{8,12})[-:]?(\d{4})', html, re.I)
        if m:
            numero = m.group(1)
            annee = m.group(2)
            return f"https://ted.europa.eu/udl?uri=TED:NOTICE:{numero}-{annee}:TEXT:FR"
        
        # 3. Construire depuis la référence 13/joue/XXXXXXXX
        if reference and reference.startswith("13/joue/"):
            parts = reference.split('/')
            if len(parts) >= 3:
                numero = parts[-1]
                if len(numero) >= 10:
                    # Format: 2026/S 123-456789 -> 26-123456
                    annee = numero[:2] if numero.startswith('20') else numero[2:4]
                    return f"https://ted.europa.eu/udl?uri=TED:NOTICE:{numero}-20{annee}:TEXT:FR"
        
        # 4. Fallback: URL générique TED
        return "https://ted.europa.eu/"
    
    def _extract_location(self, text: str) -> str:
        """Extrait la localisation (amélioré)."""
        # Lieu d'exécution principal
        m = re.search(
            r"Lieu\s+d['']?ex[ée]cution\s*[:\-]?\s*([^.\n,]{3,100}(?:,\s*[^.\n]{3,50})?)",
            text,
            re.I
        )
        if m:
            return normalize_text(m.group(1))
        
        # Lieu de performance
        m = re.search(
            r"Lieu\s+de\s+performance\s*[:\-]?\s*([^.\n,]{3,100})",
            text,
            re.I
        )
        if m:
            return normalize_text(m.group(1))
        
        # Adresse de l'autorité
        m = re.search(
            r"Adresse\s*[:\-]?\s*([^.\n,]{3,100}(?:,\s*[^.\n]{3,50})?)",
            text,
            re.I
        )
        if m:
            return normalize_text(m.group(1))
        
        # Ville + CP
        ville_m = re.search(r"Ville\s*[:\-]?\s*([^.\n]{3,50})", text, re.I)
        cp_m = re.search(r"Code\s+postal\s*[:\-]?\s*(\d{5})", text, re.I)
        pays_m = re.search(r"Pays\s*[:\-]?\s*([^.\n]{3,30})", text, re.I)
        
        parts = []
        if ville_m:
            parts.append(normalize_text(ville_m.group(1)))
        if cp_m:
            parts.append(cp_m.group(1))
        if pays_m:
            parts.append(normalize_text(pays_m.group(1)))
        
        if parts:
            return " / ".join(parts)
        
        # NUTS/Regions
        nuts_m = re.search(r"NUTS\s*[:\-]?\s*([^.\n]{3,50})", text, re.I)
        if nuts_m:
            return normalize_text(nuts_m.group(1))
        
        return ""
