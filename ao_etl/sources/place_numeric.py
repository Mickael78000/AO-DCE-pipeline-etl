"""Extracteur pour les fichiers PLACE numérique (orgAcronyme)."""

import re

from ao_etl.models.market import MarketData, SourceType, ExtractionStatus
from ao_etl.sources.base import BaseExtractor
from ao_etl.sources.validation import (
    is_valid_title, is_valid_buyer, clean_text, 
    pick_best_candidate, log_extraction_rule
)


class PlaceNumericExtractor(BaseExtractor):
    """Extracteur pour le format PLACE (marches-publics.gouv.fr).
    
    Caractéristiques:
    - Nom de fichier contient orgAcronyme
    - Structure: labels + spans avec classes spécifiques
    - Données dans h1/h2 et sections structurées
    """
    
    source_type = SourceType.PLACE_NUMERIC
    
    def can_extract(self) -> bool:
        """Vérifie si c'est un fichier PLACE."""
        return (
            'orgacronyme' in self.filepath.name.lower() or
            'consultation_depot' in self.content
        )
    
    def extract(self) -> MarketData:
        """Extrait les données d'un fichier PLACE."""
        self.data.source_type = self.source_type
        
        self._extract_title()
        self._extract_reference()
        self._extract_buyer()
        self._extract_location()
        self._extract_deadline()
        self._extract_cpv()
        
        # Log du résultat global
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
        """Extrait l'intitulé avec validation anti-faux positifs."""
        candidates = []
        
        # 1. Structure label: "Intitulé :" + valeur (PLUS FIABLE pour PLACE)
        # Chercher dans les blocs avec classe spécifique
        for label in self.soup.find_all(['label', 'span', 'div']):
            text = label.get_text(strip=True)
            if re.search(r'Intitul[eé]', text, re.I):
                # Chercher le span suivant ou parent
                parent = label.find_parent()
                if parent:
                    # Chercher le span avec la valeur
                    for sibling in parent.find_all(['span', 'div']):
                        sibling_text = sibling.get_text(strip=True)
                        if sibling_text and not re.search(r'Intitul[eé]', sibling_text, re.I):
                            candidates.append(sibling_text)
                            break
        
        # 2. Chercher dans les blocs avec classe contenant "intitule" ou "titre"
        for elem in self.soup.find_all(['span', 'div'], class_=lambda x: x and 
                                        any(word in x.lower() for word in ['intitule', 'titre', 'title'])):
            text = elem.get_text(strip=True)
            if len(text) > 15:  # Titres significatifs
                candidates.append(text)
        
        # 3. Chercher le titre après la référence dans la structure
        ref_elem = None
        for label in self.soup.find_all(['label', 'span']):
            if re.search(r'Référence', label.get_text(), re.I):
                ref_elem = label
                break
        
        if ref_elem:
            # Chercher dans le même bloc ou juste après
            parent = ref_elem.find_parent()
            if parent:
                # Chercher les spans/divs suivants qui pourraient contenir le titre
                for sibling in parent.find_next_siblings():
                    for span in sibling.find_all(['span', 'div', 'h1', 'h2', 'h3']):
                        text = span.get_text(strip=True)
                        if len(text) > 20 and len(text) < 500:
                            candidates.append(text)
        
        # 4. Fallback regex structuré
        match = re.search(
            r'<label[^>]*>Intitul[eé]\s*:\s*</label>.*?<span[^>]*class="[^"]*(?:intitule|titre|title)[^"]*"[^>]*>(.*?)</span>',
            self.content,
            re.DOTALL | re.IGNORECASE
        )
        if match:
            candidates.append(clean_text(match.group(1)))
        
        # Sélectionner le meilleur candidat valide
        best_title = pick_best_candidate(candidates, is_valid_title, prefer_longer=True)
        
        if best_title:
            self.data.title = best_title
            log_extraction_rule(self.data.extraction_notes, 'title', 
                              f'extracted_from_{len(candidates)}_candidates', best_title)
        else:
            # Log l'échec
            self.data.add_note(f"title: Aucun candidat valide parmi {len(candidates)} trouvés")
    
    def _extract_reference(self) -> None:
        """Extrait la référence depuis la structure ou le nom de fichier."""
        # 1. Structure label: "Référence :"
        label = self.soup.find('label', string=re.compile(r'R[eé]f[eé]rence', re.I))
        if label:
            parent = label.find_parent()
            if parent:
                value_span = parent.find('span')
                if value_span:
                    ref = self._clean_text(value_span.get_text())
                    if ref and ref != '-':
                        self.data.reference = ref
                        return
        
        # 2. Fallback regex
        match = re.search(
            r'<label[^>]*>R[eé]f[eé]rence\s*:</label>.*?<span[^>]*>(.*?)</span>',
            self.content,
            re.DOTALL | re.IGNORECASE
        )
        if match:
            ref = self._clean_text(match.group(1))
            if ref and ref != '-':
                self.data.reference = ref
                return
        
        # 3. Depuis le nom de fichier
        match = re.search(r'(\d+)\?orgAcronyme', self.filepath.name)
        if match:
            self.data.reference = match.group(1)
    
    def _extract_buyer(self) -> None:
        """Extrait l'acheteur avec priorité à l'Entité d'Achat sur Organisme."""
        candidates = []
        
        # 1. PRIORITÉ HAUTE: "Entité d'Achat" (valeur métier réelle)
        for label in self.soup.find_all(['label', 'span', 'div']):
            text = label.get_text(strip=True)
            if re.search(r'Entité\s+d\'Achat|Entite\s+d\'Achat', text, re.I):
                parent = label.find_parent()
                if parent:
                    for sibling in parent.find_all(['span', 'div']):
                        sibling_text = sibling.get_text(strip=True)
                        if sibling_text and len(sibling_text) > 3:
                            # Ignorer si c'est juste le label
                            if not re.search(r'Entité\s+d\'Achat', sibling_text, re.I):
                                candidates.append(('entite_achat', sibling_text))
                                break
        
        # 2. "Organisme" (souvent une catégorie générique comme "Autres organismes")
        for label in self.soup.find_all(['label', 'span', 'div']):
            text = label.get_text(strip=True)
            if re.search(r'^Organisme\s*:', text, re.I):
                parent = label.find_parent()
                if parent:
                    for sibling in parent.find_all(['span', 'div']):
                        sibling_text = sibling.get_text(strip=True)
                        if sibling_text and len(sibling_text) > 3:
                            if not re.search(r'Organisme', sibling_text, re.I):
                                candidates.append(('organisme', sibling_text))
                                break
        
        # 3. Chercher dans les blocs acheteur/entité
        for elem in self.soup.find_all(['span', 'div'], class_=lambda x: x and 
                                        any(word in x.lower() for word in ['acheteur', 'buyer', 'entite', 'entity'])):
            text = elem.get_text(strip=True)
            if len(text) > 5 and len(text) < 300:
                candidates.append(('class_search', text))
        
        # 4. Fallback regex
        # Entité d'Achat en priorité
        match = re.search(
            r'<label[^>]*>Entit[eé]\s+d\'Achat\s*:\s*</label>.*?<span[^>]*>(.*?)</span>',
            self.content,
            re.DOTALL | re.IGNORECASE
        )
        if match:
            candidates.append(('regex_entite', clean_text(match.group(1))))
        
        # Valider et sélectionner
        valid_candidates = []
        for source, candidate in candidates:
            cleaned = clean_text(candidate)
            if is_valid_buyer(cleaned):
                # Donner priorité à l'entité d'achat
                priority = 0 if source == 'entite_achat' else 1
                valid_candidates.append((priority, len(cleaned), cleaned, source))
        
        if valid_candidates:
            # Trier par priorité puis par longueur
            valid_candidates.sort(key=lambda x: (x[0], -x[1]))
            best_buyer = valid_candidates[0][2]
            source = valid_candidates[0][3]
            self.data.buyer = best_buyer
            log_extraction_rule(self.data.extraction_notes, 'buyer', 
                              f'{source}_selected_from_{len(candidates)}', best_buyer)
        elif candidates:
            # Aucun valide, logger pour diagnostic
            rejected = [c[1][:50] for c in candidates[:3]]
            self.data.add_note(f"buyer: {len(candidates)} candidats rejetés: {rejected}")
    
    def _extract_location(self) -> None:
        """Extrait la localisation/géographie."""
        candidates = []
        
        # Chercher "Lieu d'exécution" ou "Localisation"
        for label in self.soup.find_all(['label', 'span', 'div']):
            text = label.get_text(strip=True)
            if re.search(r'Lieu|Localisation|D[ée]partement', text, re.I):
                parent = label.find_parent()
                if parent:
                    for sibling in parent.find_all(['span', 'div']):
                        sibling_text = sibling.get_text(strip=True)
                        if sibling_text and len(sibling_text) > 2 and len(sibling_text) < 100:
                            if not re.search(r'Lieu|Localisation', sibling_text, re.I):
                                candidates.append(sibling_text)
                                break
        
        # Chercher dans les classes
        for elem in self.soup.find_all(['span', 'div'], class_=lambda x: x and 
                                        any(word in x.lower() for word in ['lieu', 'localisation', 'location', 'geo'])):
            text = elem.get_text(strip=True)
            if 5 < len(text) < 100:
                candidates.append(text)
        
        # Patterns de textes d'interface UI à rejeter pour la localisation
        _UI_REJECT_RE = re.compile(
            r'^(Aller au|D\u00e9tail de la|Consultation|March\u00e9|Prestation)',
            re.IGNORECASE
        )
        
        # Sélectionner le meilleur
        valid_candidates = [c for c in candidates if not _UI_REJECT_RE.match(c)]
        if valid_candidates:
            # Privilégier les localisations avec codes départementaux
            for c in valid_candidates:
                if re.search(r'\(\s*\d{2,3}\s*\)|-\s*\d{2,3}\s*\)|[0-9]{2}\s*\(', c):
                    self.data.location = clean_text(c)
                    log_extraction_rule(self.data.extraction_notes, 'location', 
                                      'with_dept_code', self.data.location)
                    return
            
            # Sinon prendre le plus long valide
            best = max((c for c in valid_candidates if 5 < len(c) < 100), key=len, default=None)
            if best:
                self.data.location = clean_text(best)
                log_extraction_rule(self.data.extraction_notes, 'location', 
                                  'longest_candidate', self.data.location)
    
    def _extract_deadline(self) -> None:
        """Extrait la date limite de réponse avec heure.

        Priorité d'extraction:
        1. Libellés explicites: "Date et heure limite de remise des plis"
        2. Libellés alternatifs: "Date limite de remise des plis", "Date limite de réception des offres"
        3. Pattern date/heure dans le bloc "Détail de la consultation"
        4. Fallback: première date valide avec heure

        Formats supportés:
        - 17/06/2026 14:00 (heure de Paris)
        - 12/06/2026 12:00
        - Date et heure limite de remise des plis : 17/06/2026 14:00
        """
        from datetime import datetime

        text = self.soup.get_text("\n", strip=True)

        # PRIORITÉ 1: Libellés explicites avec date et heure
        # Pattern: "Date et heure limite de remise des plis : 17/06/2026 14:00"
        explicit_patterns = [
            (r'Date et heure limite de remise des plis\s*[:\-\n]\s*(\d{2}/\d{2}/\d{4})\s+(\d{2}):(\d{2})', 'date_heure_limite_plis'),
            (r'Date limite de remise des plis\s*[:\-\n]\s*(\d{2}/\d{2}/\d{4})\s+(\d{2}):(\d{2})', 'date_limite_plis'),
            (r'Date limite de r[ée]ception des plis\s*[:\-\n]\s*(\d{2}/\d{2}/\d{4})\s+(\d{2}):(\d{2})', 'date_reception_plis'),
            (r'Date limite de r[ée]ception des offres\s*[:\-\n]\s*(\d{2}/\d{2}/\d{4})\s+(\d{2}):(\d{2})', 'date_reception_offres'),
        ]

        for pattern, rule_name in explicit_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = f"{match.group(1)} {match.group(2)}:{match.group(3)}:00"
                day, month, year = match.group(1).split('/')
                try:
                    dt = datetime.strptime(date_str, '%d/%m/%Y %H:%M:%S')
                    self.data.date_limite = dt
                    log_extraction_rule(self.data.extraction_notes, 'date_limite', rule_name, date_str)
                    return
                except ValueError:
                    continue

        # PRIORITÉ 2: Pattern générique date/heure dans le bloc de consultation
        # Recherche de format: DD/MM/YYYY HH:MM éventuellement suivi de "(heure de Paris)"
        generic_pattern = r'(\d{2}/\d{2}/\d{4})\s+(\d{2}):(\d{2})(?:\s*\(heure de Paris\))?'
        matches = list(re.finditer(generic_pattern, text))

        for match in matches:
            date_str = f"{match.group(1)} {match.group(2)}:{match.group(3)}:00"
            day, month, year = match.group(1).split('/')
            try:
                dt = datetime.strptime(date_str, '%d/%m/%Y %H:%M:%S')
                # Vérifier que c'est une date future plausible (2025-2030)
                if 2025 <= dt.year <= 2030:
                    self.data.date_limite = dt
                    log_extraction_rule(self.data.extraction_notes, 'date_limite', 'generic_date_time', date_str)
                    return
            except ValueError:
                continue

        # PRIORITÉ 3: Recherche via structure DOM (libellés HTML)
        deadline_labels = [
            r'Date et heure limite de remise des plis',
            r'Date limite de remise des plis',
            r'Date limite de r[ée]ception des plis',
            r'Date limite de r[ée]ception des offres',
            r'Date de cl[ôo]ture',
            r'Date limite de r[ée]ponse',
        ]

        for label_pattern in deadline_labels:
            for label in self.soup.find_all(['label', 'span', 'div']):
                text = label.get_text(strip=True)
                if re.search(label_pattern, text, re.I):
                    parent = label.find_parent()
                    if parent:
                        for sibling in parent.find_all(['span', 'div']):
                            sibling_text = sibling.get_text(strip=True)
                            # Chercher date avec heure: DD/MM/YYYY HH:MM
                            date_match = re.search(r'(\d{2}/\d{2}/\d{4})\s+(\d{2}):(\d{2})', sibling_text)
                            if date_match:
                                date_str = f"{date_match.group(1)} {date_match.group(2)}:{date_match.group(3)}:00"
                                day, month, year = date_match.group(1).split('/')
                                try:
                                    dt = datetime.strptime(date_str, '%d/%m/%Y %H:%M:%S')
                                    self.data.date_limite = dt
                                    log_extraction_rule(self.data.extraction_notes, 'date_limite', f'dom_{label_pattern[:20]}', date_str)
                                    return
                                except ValueError:
                                    continue
                            # Fallback: date sans heure
                            date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', sibling_text)
                            if date_match:
                                date_str = date_match.group(1)
                                for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y']:
                                    try:
                                        self.data.date_limite = datetime.strptime(date_str, fmt)
                                        log_extraction_rule(self.data.extraction_notes, 'date_limite', f'dom_date_only_{fmt}', date_str)
                                        return
                                    except ValueError:
                                        continue
    
    def _extract_cpv(self) -> None:
        """Extrait les codes CPV depuis data-code-cpv."""
        matches = re.findall(r'data-code-cpv="(\d+)"', self.content)
        self.data.cpv = list(set(matches))[:5]
        if matches:
            log_extraction_rule(self.data.extraction_notes, 'cpv', 
                              f'found_{len(matches)}_codes', ','.join(matches[:3]))
