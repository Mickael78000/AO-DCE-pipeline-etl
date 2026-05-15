"""Extracteur pour les fichiers Marchés Online - Version 2."""

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


class MarchesOnlineExtractor(BaseExtractor):
    """Extracteur pour le format Marchés Online.
    
    Caractéristiques:
    - Nom de fichier: ao-XXXXX-X.html
    - h1.title-avis contient le titre
    - print_area_company contient l'acheteur
    - Structure avec "Nom officiel :" dans les sections ORG
    """
    source_type = "MARCHES_ONLINE"

    def extract(self) -> ExtractionResult:
        result = ExtractionResult(source_type=self.source_type)
        soup = self.context.soup
        text = self.text()
        
        # 1. Référence depuis nom de fichier
        result.reference = self._extract_reference_from_filename()
        
        # 2. Collecter les candidats titre
        title_candidates = []
        
        # h1 avec classe title-avis
        h1_title = soup.find('h1', class_=lambda x: x and 'title-avis' in x)
        if h1_title:
            title_candidates.append(FieldCandidate(
                "title", 
                normalize_text(h1_title.get_text()), 
                "h1_title_avis", 
                score=40
            ))
        
        # Balise title
        if soup.title:
            m = re.search(r"Appel d'offres?\s*:\s*([^<\-,]+)(?:,|\s*-\s*|$)", str(soup.title), re.I)
            if m:
                title_candidates.append(FieldCandidate(
                    "title",
                    normalize_text(m.group(1)),
                    "title_tag",
                    score=30
                ))
        
        # Meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            m = re.search(r"appel d'offre\s*:\s*([^\.]+)", meta_desc.get('content'), re.I)
            if m:
                title_candidates.append(FieldCandidate(
                    "title",
                    normalize_text(m.group(1)),
                    "meta_description",
                    score=25
                ))
        
        # 3. Collecter les candidats acheteur
        buyer_candidates = []
        
        # Lien dans print_area_company
        company_div = soup.find('div', id='print_area_company')
        if company_div:
            link = company_div.find('a')
            if link:
                buyer_candidates.append(FieldCandidate(
                    "buyer",
                    normalize_text(link.get_text()),
                    "company_link",
                    score=45
                ))
        
        # Nom officiel dans le texte
        m = re.search(r'Nom officiel\s*:\s*([^\n<]+)', text, re.I)
        if m:
            buyer_candidates.append(FieldCandidate(
                "buyer",
                normalize_text(m.group(1)),
                "nom_officiel_pattern",
                score=40
            ))
        
        # dataLayer (si présent mais moins fiable)
        m = re.search(r"'organisme'\s*:\s*'([^']{3,200})'", self.context.html)
        if m:
            buyer_candidates.append(FieldCandidate(
                "buyer",
                normalize_text(m.group(1)),
                "datalayer_organisme",
                score=10  # Score faible car souvent catégorie
            ))
        
        # 4. Localisation et date
        result.location = self._extract_location(soup, text)
        result.deadline = self._extract_deadline(soup, text)
        
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

    def _extract_reference_from_filename(self) -> str:
        """Extrait la référence depuis le nom de fichier."""
        name = self.filename()
        # Pattern: ao-XXXXX-X.html -> MO-XXXXX
        m = re.match(r"ao-(\d+)-\d+", name, re.I)
        if m:
            return f"MO-{m.group(1)}"
        return name.replace('.html', '')

    def _extract_location(self, soup, text: str) -> str:
        """Extrait la localisation."""
        # Chercher dans print_area_info
        info_div = soup.find('div', id='print_area_info')
        if info_div:
            info_text = info_div.get_text("\n", strip=True)
            # Pattern: XX - REGION ou département
            m = re.search(r'(\d{2,3}\s*-\s*[^\n,]{3,100})', info_text)
            if m:
                return normalize_text(m.group(1))
        
        # Chercher Ville + Code postal
        ville_m = re.search(r'Ville\s*:\s*([^\n<,]+)', text, re.I)
        cp_m = re.search(r'Code\s+postal\s*:\s*(\d{5})', text, re.I)
        if ville_m:
            ville = normalize_text(ville_m.group(1))
            if cp_m:
                return f"{ville} ({cp_m.group(1)})"
            return ville
        
        return ""

    def _extract_deadline(self, soup, text: str) -> str:
        """Extrait la date limite."""
        # Pattern visible: "Limite de réponse : DD/MM/YYYY"
        m = re.search(
            r'Limite\s+de\s+r[ée]ponse\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            text,
            re.I
        )
        if m:
            return normalize_text(m.group(1))
        
        # Chercher dans span font-bold
        m = re.search(
            r'Limite\s+de\s+r[ée]ponse\s*[:\-]?\s*<[^>]*font-bold[^>]*>(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            self.context.html,
            re.I
        )
        if m:
            return normalize_text(m.group(1))
        
        return ""
