"""Extracteur standard (fallback) pour formats non reconnus."""

import re

from ao_etl.models.market import MarketData, SourceType
from ao_etl.sources.base import BaseExtractor


class StandardExtractor(BaseExtractor):
    """Extracteur fallback pour les fichiers au format générique.
    
    Utilisé quand aucune source spécifique n'est détectée.
    Applique des heuristiques génériques sur le contenu.
    """
    
    source_type = SourceType.STANDARD
    
    def can_extract(self) -> bool:
        """Toujours vrai - c'est le fallback."""
        return True
    
    def extract(self) -> MarketData:
        """Extrait les données avec des heuristiques génériques."""
        self.data.source_type = self.source_type
        
        self._extract_title_generic()
        self._extract_reference_generic()
        self._extract_buyer_generic()
        self._extract_cpv_generic()
        
        if self.data.is_complete():
            self.data.status = ExtractionStatus.SUCCESS
        elif any([self.data.title, self.data.reference]):
            self.data.status = ExtractionStatus.PARTIAL
        
        return self.data
    
    def _extract_title_generic(self) -> None:
        """Extraction titre générique."""
        # 1. <h1>
        h1 = self.soup.find('h1')
        if h1:
            text = self._clean_text(h1.get_text())
            if text and len(text) > 5:
                self.data.title = text
                return
        
        # 2. <title>
        if self.soup.title:
            title_text = self.soup.title.string or ""
            # Nettoyer les préfixes courants
            title_text = re.sub(r'^Appel d.offres?\s*:\s*', '', title_text, flags=re.I)
            title_text = re.sub(r'\s*-\s*[^-]+\s*-\s*\d{4}$', '', title_text)
            text = self._clean_text(title_text)
            if text and len(text) > 5:
                self.data.title = text
                return
        
        # 3. <meta name="description">
        meta = self.soup.find('meta', attrs={'name': 'description'})
        if meta:
            content = meta.get('content', '')
            # Prendre première phrase significative
            match = re.search(r'^([^\.]{20,200})', content)
            if match:
                self.data.title = self._clean_text(match.group(1))
    
    def _extract_reference_generic(self) -> None:
        """Extraction référence générique."""
        text = self.soup.get_text("\n", strip=True)
        
        patterns = [
            r'R[eé]f[eé]rence\s*:\s*([^\n]+)',
            r'Identifiant\s*:\s*([^\n]+)',
            r'Num[eé]ro\s*:\s*([^\n]+)',
            r'Avis\s+n[°o]\s*:\s*([^\n]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                ref = self._clean_text(match.group(1))
                if ref and len(ref) < 50:
                    self.data.reference = ref
                    return
        
        # Fallback: depuis le nom de fichier
        stem = self.filepath.stem
        # Prendre première partie significative
        match = re.search(r'^([a-z]+\d+)', stem, re.I)
        if match:
            self.data.reference = match.group(1)
    
    def _extract_buyer_generic(self) -> None:
        """Extraction acheteur générique."""
        text = self.soup.get_text("\n", strip=True)
        
        patterns = [
            r'Organisme\s*:\s*([^\n]{3,100})',
            r'Acheteur\s*:\s*([^\n]{3,100})',
            r'Pouvoir adjudicateur\s*:\s*([^\n]{3,100})',
            r'Client\s*:\s*([^\n]{3,100})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                val = self._clean_text(match.group(1))
                if val and len(val) >= 3:
                    self.data.buyer = val
                    return
    
    def _extract_cpv_generic(self) -> None:
        """Extraction CPV générique (codes 8 chiffres)."""
        text = self.soup.get_text()
        matches = re.findall(r'(\d{8})', text)
        # Filtrer les codes CPV plausibles (commençant par des codes connus)
        cpv_codes = [m for m in matches if m.startswith(('03', '30', '45', '72', '80'))]
        self.data.cpv = list(set(cpv_codes or matches))[:3]


from ao_etl.models.market import ExtractionStatus
