"""Extracteur pour les fichiers France Marchés (weboramaItemTag JSON)."""

import re
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from ao_etl.models.market import MarketData, SourceType, ExtractionStatus
from ao_etl.sources.base import BaseExtractor
from ao_etl.sources.validation import (
    is_valid_title, is_valid_buyer, clean_text,
    pick_best_candidate, log_extraction_rule
)


class FranceMarchesExtractor(BaseExtractor):
    """Extracteur pour le format France Marchés.
    
    Caractéristiques:
    - Contient un JSON weboramaItemTag encodé avec séquences Unicode (\\u0022)
    - Format JOUE, BOAMP, et autres via France Marchés
    - Référence dans <title> ou <meta> sous format "Appel d'offre n°XXX"
    """
    
    source_type = SourceType.FRANCE_MARCHES
    
    def can_extract(self) -> bool:
        """Vérifie si c'est un fichier France Marchés."""
        return (
            'weboramaitemtag' in self.content.lower() and
            'title_article' in self.content
        )
    
    def extract(self) -> MarketData:
        """Extrait les données d'un fichier France Marchés."""
        self.data.source_type = self.source_type
        
        self._extract_title()
        self._extract_reference()
        self._extract_buyer()
        self._extract_cpv()
        
        completeness = self.data.completeness_score()
        if completeness >= 0.8:
            self.data.status = ExtractionStatus.SUCCESS
            self.data.add_note(f"Extraction réussie (completude: {completeness:.0%})")
        elif completeness >= 0.4:
            self.data.status = ExtractionStatus.PARTIAL
            self.data.add_note(f"Extraction partielle (completude: {completeness:.0%})")
        else:
            self.data.status = ExtractionStatus.FAILED
            self.data.add_note(f"Extraction échouée (completude: {completeness:.0%})")
        
        return self.data
    
    def _extract_title(self) -> None:
        """Extrait le titre depuis weboramaItemTag JSON ou DOM avec validation."""
        candidates = []
        
        # 1. weboramaItemTag JSON (meilleure source)
        match = re.search(
            'title_article\\\\u0022(?:\\\\u003A|:)\\\\u0022(.*?)\\\\u0022',
            self.content,
            re.IGNORECASE
        )
        if match:
            title = self._decode_unicode_escapes(match.group(1))
            candidates.append(clean_text(title))
        
        # 2. <title> après "Appel d'offre :"
        if self.soup.title:
            title_match = re.search(
                r"Appel d'offre\s*:\s*([^<\-,]+)(?:,|\s*-\s*|$)",
                str(self.soup.title),
                re.IGNORECASE
            )
            if title_match:
                candidates.append(clean_text(title_match.group(1)))
        
        # 3. <meta name="description">
        meta_desc = self.soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            desc_match = re.search(
                r"Appel d'offre\s+n°[^:]+:\s*([^\.]+)",
                meta_desc.get('content'),
                re.IGNORECASE
            )
            if desc_match:
                candidates.append(clean_text(desc_match.group(1)))
        
        # 4. Chercher "Intitulé de l'appel d'offre public"
        text = self.soup.get_text("\n", strip=True)
        match = re.search(
            r"Intitul[eé]\s+de\s+l['']?appel\s+d['']?offre\s+(?:public\s+)?\.\.\.\.\s*:\s*([^\n]+)",
            text,
            re.IGNORECASE
        )
        if match:
            candidates.append(clean_text(match.group(1)))
        
        # Valider et sélectionner
        best_title = pick_best_candidate(candidates, is_valid_title, prefer_longer=True)
        
        if best_title:
            self.data.title = best_title
            log_extraction_rule(self.data.extraction_notes, 'title',
                              f'weborama_from_{len(candidates)}', best_title)
        else:
            # Dernier fallback: h1
            h1 = self.soup.find('h1')
            if h1:
                title_text = clean_text(h1.get_text())
                if len(title_text) > 10:
                    self.data.title = title_text
                    log_extraction_rule(self.data.extraction_notes, 'title', 'h1_fallback', title_text)
            if not self.data.title:
                self.data.add_note(f"title: Aucun candidat valide parmi {len(candidates)} trouvés")
    
    def _extract_reference(self) -> None:
        """Extrait la référence depuis nom de fichier ou contenu."""
        name = self.filepath.name.lower()
        
        # Pattern 1: 3boamp2643374 → 3/boamp/2643374
        match = re.search(r'(\dboamp\d+)', name)
        if match:
            ref = match.group(1)
            self.data.reference = f"{ref[0]}/boamp/{ref[6:]}"
            return
        
        # Pattern 2: 37ao26181581260520263294
        match = re.search(r'(\d{2}ao\d+)', name, re.IGNORECASE)
        if match:
            self.data.reference = match.group(1).upper()
            return
        
        # Pattern 3: 36parisien1157695
        match = re.search(r'parisien(\d+)', name, re.IGNORECASE)
        if match:
            self.data.reference = match.group(1)
            return
        
        # Pattern 4: 13joue003085442026
        match = re.search(r'(\d{2}joue\d+)', name, re.IGNORECASE)
        if match:
            ref = match.group(1)
            self.data.reference = f"{ref[:2]}/joue/{ref[6:]}"
            return
        
        # Fallback: <title> ou <meta> "Appel d'offre n°XXX"
        if not self.data.reference:
            patterns = [
                r"Appel d&#039;offre\s+n°([^\s\-]+)",  # Format HTML échappé
                r"Appel d'offre\s+n°([^\s\-]+)",       # Format standard
                r"Appel d&#039;offre\s*:\s*[^<\-]+\s*-\s*([^<\-]+)\s*-\s*2026",
                r"Appel d'offre\s*:\s*[^<\-]+\s*-\s*([^<\-]+)\s*-\s*2026",
            ]
            for pattern in patterns:
                ref_match = re.search(pattern, self.content, re.IGNORECASE)
                if ref_match:
                    self.data.reference = ref_match.group(1).strip()
                    break
        
        # Dernier fallback: "Avis n°"
        if not self.data.reference:
            match = re.search(
                r'Avis\s+n[°o]\s*(\d+[-/\d]*)',
                self.content,
                re.IGNORECASE
            )
            if match:
                self.data.reference = match.group(1)
    
    def _extract_buyer(self) -> None:
        """Extrait l'acheteur depuis le contenu textuel."""
        text = self.soup.get_text("\n", strip=True)
        
        patterns = [
            r'Acheteur\s*:\s*([^<\n]{5,100})',
            r'Organisme\s*:\s*([^<\n]{5,100})',
            r'Nom\s+officiel\s*:\s*([^<\n]{5,100})',
            r'Nom complet de l.acheteur\s*:\s*([^<\n]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                val = self._clean_text(match.group(1))
                if val and is_valid_buyer(val):
                    self.data.buyer = val
                    return
        
        # Fallback DOM: chercher label "Acheteur"
        if not self.data.buyer:
            buyer_label = self.soup.find(
                string=re.compile(r'Acheteur|Organisme', re.I)
            )
            if buyer_label:
                parent = buyer_label.find_parent()
                if parent:
                    next_elem = parent.find_next_sibling()
                    if next_elem:
                        val = self._clean_text(next_elem.get_text())
                        if val and is_valid_buyer(val):
                            self.data.buyer = val
    
    def _extract_location(self) -> None:
        """Extrait la localisation."""
        candidates = []
        text = self.soup.get_text("\n", strip=True)
        
        # Chercher Ville ou Lieu d'exécution
        for pattern in [
            r'Ville\s*:\s*([^\n<,]+)',
            r"Lieu d['']?ex[eé]cution\s*:\s*([^\n<]+)",
        ]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                candidates.append(clean_text(match.group(1)))
        
        if candidates:
            # Sélectionner le plus spécifique (avec code postal si présent)
            for c in candidates:
                if re.search(r'\(\s*\d{2,3}\s*\)', c):
                    self.data.location = c
                    log_extraction_rule(self.data.extraction_notes, 'location', 'with_cp', c)
                    return
            # Sinon prendre le premier
            self.data.location = candidates[0]
            log_extraction_rule(self.data.extraction_notes, 'location', 'first_match', candidates[0])
    
    def _extract_deadline(self) -> None:
        """Extrait la date limite."""
        text = self.soup.get_text("\n", strip=True)
        
        # Chercher date dans différents formats
        match = re.search(
            r'Date limite[^\n]*?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            text,
            re.IGNORECASE
        )
        if match:
            date_str = match.group(1)
            for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y']:
                try:
                    self.data.date_limite = datetime.strptime(date_str, fmt)
                    log_extraction_rule(self.data.extraction_notes, 'date_limite', fmt, date_str)
                    return
                except ValueError:
                    continue
    
    def _extract_cpv(self) -> None:
        """Extrait les codes CPV."""
        matches = re.findall(r'data-code-cpv="(\d+)"', self.content)
        self.data.cpv = list(set(matches))[:5]
        if matches:
            log_extraction_rule(self.data.extraction_notes, 'cpv', 
                              f'found_{len(matches)}', ','.join(matches[:3]))
