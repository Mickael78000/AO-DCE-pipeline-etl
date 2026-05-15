"""Extracteur pour les fichiers BOAMP XML."""

import re
from datetime import datetime

from ao_etl.models.market import MarketData, SourceType, ExtractionStatus
from ao_etl.sources.base import BaseExtractor
from ao_etl.sources.validation import (
    is_valid_title, is_valid_buyer, clean_text,
    pick_best_candidate, log_extraction_rule
)


class BoampXmlExtractor(BaseExtractor):
    """Extracteur pour le format BOAMP (Bulletin Officiel des Annonces
    des Marchés Publics) au format XML-like dans HTML.
    
    Caractéristiques:
    - Structure avec spans et classes spécifiques
    - Labels structurés (Titre, Référence, Acheteur, CPV)
    - Nom de fichier commence souvent par "26-" ou contient "boamp"
    """
    
    source_type = SourceType.BOAMP_XML
    
    def can_extract(self) -> bool:
        """Vérifie si c'est un fichier BOAMP."""
        name = self.filepath.name.lower()
        return name.startswith('26-') or 'boamp' in name
    
    def extract(self) -> MarketData:
        """Extrait les données d'un fichier BOAMP."""
        self.data.source_type = self.source_type
        
        self._extract_title()
        self._extract_reference()
        self._extract_buyer()
        self._extract_cpv()
        
        if self.data.is_complete():
            self.data.status = ExtractionStatus.SUCCESS
        elif any([self.data.title, self.data.reference]):
            self.data.status = ExtractionStatus.PARTIAL
        
        return self.data
    
    def _extract_title(self) -> None:
        """Extrait le titre depuis la structure BOAMP avec validation."""
        candidates = []
        
        # 1. Structure label/valeur: "Titre :" + valeur
        text_content = self.soup.get_text("\n", strip=True)
        match = re.search(r'Titre\s*:\s*([^\n]+)', text_content, re.IGNORECASE)
        if match:
            candidates.append(clean_text(match.group(1)))
        
        # 2. span avec classe titrePrincipal
        title_span = self.soup.find('span', class_=lambda x: x and 'titrePrincipal' in x)
        if title_span:
            candidates.append(clean_text(title_span.get_text()))
        
        # 3. Structure label span "Titre" + span valeur
        label = self.soup.find('span', string=re.compile(r'^Titre$', re.I))
        if label:
            parent = label.find_parent()
            if parent:
                next_span = parent.find_next('span')
                if next_span:
                    candidates.append(clean_text(next_span.get_text()))
        
        # 4. "Intitulé du marché"
        match = re.search(r'Intitul[eé] du march[ée]\s*:\s*([^\n]+)', text_content, re.IGNORECASE)
        if match:
            candidates.append(clean_text(match.group(1)))
        
        # Valider et sélectionner
        best_title = pick_best_candidate(candidates, is_valid_title, prefer_longer=True)
        
        if best_title:
            self.data.title = best_title
            log_extraction_rule(self.data.extraction_notes, 'title',
                              f'from_{len(candidates)}_candidates', best_title)
        else:
            # Dernier fallback: h1 ou title (sans validation stricte mais avec nettoyage)
            h1 = self.soup.find('h1')
            if h1:
                title_text = clean_text(h1.get_text())
                if len(title_text) > 10:  # Minimum pour éviter génériques
                    self.data.title = title_text
                    log_extraction_rule(self.data.extraction_notes, 'title', 'h1_fallback', title_text)
            if not self.data.title:
                self.data.add_note(f"title: Aucun candidat valide parmi {len(candidates)} trouvés")
    
    def _extract_reference(self) -> None:
        """Extrait la référence BOAMP depuis 'Identifiant interne'."""
        text = self.soup.get_text("\n", strip=True)
        
        # 1. "Identifiant interne" - PRIORITÉ MAX
        match = re.search(r'Identifiant interne\s*:\s*([^\n<]+)', text, re.IGNORECASE)
        if match:
            ref = clean_text(match.group(1))
            if ref and len(ref) < 60 and ref != '-':
                self.data.reference = ref
                log_extraction_rule(self.data.extraction_notes, 'reference', 'identifiant_interne', ref)
                return
        
        # 2. Pattern fichier BOAMP dans le nom
        filename_match = re.search(r'(?:26-)?(\d+)', self.filepath.name)
        if filename_match:
            ref = f"26-{filename_match.group(1)}"
            self.data.reference = ref
            log_extraction_rule(self.data.extraction_notes, 'reference', 'from_filename', ref)
            return
        
        self.data.add_note("reference: Non extraite")
    
    def _extract_buyer(self) -> None:
        """Extrait l'acheteur depuis 'Nom officiel' avec validation."""
        text = self.soup.get_text("\n", strip=True)
        candidates = []
        
        # 1. "Nom officiel" - PRIORITÉ HAUTE
        match = re.search(r'Nom officiel\s*:\s*([^\n<]+)', text, re.IGNORECASE)
        if match:
            candidates.append(('nom_officiel', clean_text(match.group(1))))
        
        # 2. "Nom complet de l'acheteur"
        match = re.search(r"Nom complet de l['']?acheteur\s*:\s*([^\n<]+)", text, re.IGNORECASE)
        if match:
            candidates.append(('nom_complet', clean_text(match.group(1))))
        
        # 3. "Acheteur public"
        match = re.search(r'Acheteur public\s*:\s*([^\n<]+)', text, re.IGNORECASE)
        if match:
            candidates.append(('acheteur_public', clean_text(match.group(1))))
        
        # Valider et sélectionner
        best_buyer = None
        for source, candidate in candidates:
            if is_valid_buyer(candidate):
                best_buyer = candidate
                log_extraction_rule(self.data.extraction_notes, 'buyer', source, best_buyer)
                break
        
        if best_buyer:
            self.data.buyer = best_buyer
        else:
            self.data.add_note(f"buyer: {len(candidates)} candidats rejetés comme faux positifs")
    
    def _extract_location(self) -> None:
        """Extrait la localisation depuis Ville ou NUTS."""
        text = self.soup.get_text("\n", strip=True)
        candidates = []
        
        # 1. "Ville" + "Code postal"
        ville_match = re.search(r'Ville\s*:\s*([^\n<,]+)', text, re.IGNORECASE)
        cp_match = re.search(r'Code postal\s*:\s*(\d{5})', text, re.IGNORECASE)
        if ville_match:
            ville = clean_text(ville_match.group(1))
            if cp_match:
                candidates.append(('ville_cp', f"{ville} ({cp_match.group(1)})"))
            else:
                candidates.append(('ville', ville))
        
        # 2. Subdivision pays (NUTS)
        nuts_match = re.search(r'NUTS\)\s*:\s*([^\n<]+)', text, re.IGNORECASE)
        if nuts_match:
            candidates.append(('nuts', clean_text(nuts_match.group(1))))
        
        # 3. "Lieu d'exécution"
        lieu_match = re.search(r"Lieu d['']?ex[eé]cution\s*:\s*([^\n<]+)", text, re.IGNORECASE)
        if lieu_match:
            candidates.append(('lieu_execution', clean_text(lieu_match.group(1))))
        
        if candidates:
            # Priorité: ville_cp > lieu > nuts
            priority = {'ville_cp': 0, 'lieu_execution': 1, 'ville': 2, 'nuts': 3}
            candidates.sort(key=lambda x: priority.get(x[0], 10))
            self.data.location = candidates[0][1]
            log_extraction_rule(self.data.extraction_notes, 'location', candidates[0][0], self.data.location)
    
    def _extract_deadline(self) -> None:
        """Extrait la date limite 'Date limite de réception des offres'."""
        text = self.soup.get_text("\n", strip=True)
        
        # "Date limite de réception des offres" avec heure optionnelle
        # Supporte formats: "04/06/2026 à 17:00", "04/06/2026 @ 17:00", "04/06/2026 17:00"
        match = re.search(
            r'Date limite de r[ée]ception des offres\s*:\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*(?:à|@|a)?\s*(\d{1,2}:\d{2})?',
            text,
            re.IGNORECASE
        )
        if match:
            date_str = match.group(1)
            time_str = match.group(2) if match.group(2) else "00:00"
            
            for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y']:
                try:
                    dt = datetime.strptime(f"{date_str} {time_str}", f"{fmt} %H:%M")
                    self.data.date_limite = dt
                    log_extraction_rule(self.data.extraction_notes, 'date_limite', 
                                      f'date_reception_{fmt}', f"{date_str} {time_str}")
                    return
                except ValueError:
                    continue
    
    def _extract_duree(self) -> None:
        """Extrait la durée du marché."""
        text = self.soup.get_text("\n", strip=True)
        
        # "Durée" ou "Durée du marché"
        match = re.search(
            r'Dur[ée]e(?:\s+du\s+march[ée])?\s*:\s*([^\n<]+)',
            text,
            re.IGNORECASE
        )
        if match:
            duree_text = clean_text(match.group(1))
            # Extraire les mois
            mois_match = re.search(r'(\d+)\s*mois', duree_text, re.IGNORECASE)
            if mois_match:
                self.data.duree_mois = int(mois_match.group(1))
                log_extraction_rule(self.data.extraction_notes, 'duree', 'mois', str(self.data.duree_mois))
            elif 'an' in duree_text.lower():
                an_match = re.search(r'(\d+)\s*an', duree_text, re.IGNORECASE)
                if an_match:
                    self.data.duree_mois = int(an_match.group(1)) * 12
                    log_extraction_rule(self.data.extraction_notes, 'duree', 'annees', duree_text)
    
    def _extract_estimation(self) -> None:
        """Extrait l'estimation 'Valeur estimée hors TVA'."""
        text = self.soup.get_text("\n", strip=True)
        
        # "Valeur estimée hors TVA" ou "Valeur totale"
        match = re.search(
            r'Valeur\s+(?:estim[ée]e\s+)?(?:hors\s+TVA|totale)\s*:\s*([^\n<]+)',
            text,
            re.IGNORECASE
        )
        if match:
            val_text = clean_text(match.group(1))
            # Extraire le nombre
            num_match = re.search(r'([\d\s.,]+)\s*(?:€|EUR|Euro)', val_text, re.IGNORECASE)
            if num_match:
                num_str = num_match.group(1).replace(' ', '').replace(',', '.')
                try:
                    self.data.estimation_eur = float(num_str)
                    log_extraction_rule(self.data.extraction_notes, 'estimation', 'valeur_hors_tva', val_text)
                except ValueError:
                    pass
    
    def _extract_cpv(self) -> None:
        """Extrait les codes CPV."""
        matches = re.findall(r'data-code-cpv="(\d+)"', self.content)
        if not matches:
            text = self.soup.get_text()
            matches = re.findall(r'(\d{8})', text)
        
        self.data.cpv = list(set(matches))[:3]
        if matches:
            log_extraction_rule(self.data.extraction_notes, 'cpv', 
                              f'found_{len(matches)}', ','.join(matches[:3]))
    
    def extract(self) -> MarketData:
        """Extrait les données d'un fichier BOAMP."""
        self.data.source_type = self.source_type
        
        self._extract_title()
        self._extract_reference()
        self._extract_buyer()
        self._extract_location()
        self._extract_deadline()
        self._extract_duree()
        self._extract_estimation()
        self._extract_cpv()
        
        # Statut avec score
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
