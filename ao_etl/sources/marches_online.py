"""Extracteur pour les fichiers Marchés Online (ao-*.html)."""

import re
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

from ao_etl.models.market import MarketData, SourceType, ExtractionStatus
from ao_etl.sources.base import BaseExtractor
from ao_etl.sources.validation import (
    is_valid_title, is_valid_buyer, clean_text,
    pick_best_candidate, log_extraction_rule
)


class MarchesOnlineExtractor(BaseExtractor):
    """Extracteur pour le format Marchés Online.
    
    Caractéristiques:
    - Nom de fichier: ao-XXXXXXX-N.html
    - Structure: dataLayer JavaScript avec refContrat (mais refContrat est
      identique pour tous les marchés du même compte - à ne PAS utiliser)
    - Référence fiable: ID fichier ao-XXXXXXX → MO-XXXXXXX
    """
    
    source_type = SourceType.MARCHES_ONLINE
    
    def can_extract(self) -> bool:
        """Vérifie si c'est un fichier Marchés Online."""
        return (
            'marchesonline.com' in self.content or
            self.filepath.name.startswith('ao-')
        )
    
    def extract(self) -> MarketData:
        """Extrait les données d'un fichier Marchés Online."""
        self.data.source_type = self.source_type

        # Extraction titre
        self._extract_title()

        # Extraction référence (DEPUIS NOM DE FICHIER, pas refContrat)
        self._extract_reference()

        # Extraction acheteur avec forme juridique et activité
        self._extract_buyer()

        # Extraction localisation
        self._extract_location()

        # Extraction date limite
        self._extract_deadline()

        # Extraction CPV
        self._extract_cpv()

        # Extraction type de procédure et nature du marché
        self._extract_procedure_and_nature()

        # Extraction durée et montants (lots)
        self._extract_duration_and_amounts()

        # Mise à jour statut avec score de complétude
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
        """Extrait le titre avec validation anti-faux positifs."""
        candidates = []
        
        # 1. <h1 class="...title-avis..."> - PLUS FIABLE pour Marchés Online
        h1_title = self.soup.find('h1', class_=lambda x: x and 'title-avis' in x)
        if h1_title:
            title_text = clean_text(h1_title.get_text())
            if len(title_text) > 20:  # Titres longs = plus spécifiques
                candidates.append(('h1_title_long', title_text))
            else:
                candidates.append(('h1_title', title_text))
        
        # 2. <title> tag: "Appel d'offres : TITRE, ..."
        if self.soup.title:
            title_match = re.search(
                r"Appel d'offres?\s*:\s*(.*?)(?:,|\s*-\s*REGION|</title>|$)",
                str(self.soup.title),
                re.IGNORECASE
            )
            if title_match:
                title_text = clean_text(title_match.group(1))
                if len(title_text) >= 10:
                    candidates.append(('title_tag', title_text))
        
        # 3. <meta name="description">: "Appel d'offre : TITRE."
        meta_desc = self.soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            desc_match = re.search(
                r"appel d'offre\s*:\s*(.*?)\. ?\s*(?:,|\s*-\s*REGION|$)",
                meta_desc.get('content'),
                re.IGNORECASE
            )
            if desc_match:
                title_text = clean_text(desc_match.group(1))
                if len(title_text) >= 10:
                    candidates.append(('meta_description', title_text))
        
        # 4. Texte visible dans la div principale (près de l'acheteur)
        main_content = self.soup.find('div', class_=lambda x: x and 'print_area_title' in str(x))
        if main_content:
            for div in main_content.find_all(['div', 'span'], class_=lambda x: x and 
                                              any(w in str(x).lower() for w in ['text', 'font-bold', 'secondary'])):
                text = clean_text(div.get_text())
                if len(text) > 30 and len(text) < 500:  # Titres significatifs
                    candidates.append(('main_content', text))
        
        # 5. Fallback regex structuré: "Titre :"
        match = re.search(
            r'Titre\s*:\s*([^<\n]{20,500})',
            self.content,
            re.IGNORECASE
        )
        if match:
            candidates.append(('regex_titre_section', clean_text(match.group(1))))
        
        # 6. Dernier fallback: "Intitulé du marché :"
        match = re.search(
            r'Intitul[eé] du march[eé]\s*:\s*([^<\n]{20,500})',
            self.content,
            re.IGNORECASE
        )
        if match:
            candidates.append(('regex_intitule', clean_text(match.group(1))))
        
        # Valider et sélectionner - privilégier les sources spécifiques et les textes longs
        valid_candidates = []
        for source, candidate in candidates:
            if is_valid_title(candidate):
                # Score: source priority (h1=0, title=1, meta=2, etc.) + length bonus
                priority = {'h1_title_long': 0, 'h1_title': 1, 'title_tag': 2, 
                           'meta_description': 3, 'main_content': 4, 
                           'regex_titre_section': 5, 'regex_intitule': 6}.get(source, 10)
                valid_candidates.append((priority, len(candidate), candidate, source))
        
        if valid_candidates:
            # Trier par priorité puis par longueur décroissante
            valid_candidates.sort(key=lambda x: (x[0], -x[1]))
            best_title = valid_candidates[0][2]
            source = valid_candidates[0][3]
            self.data.title = best_title
            log_extraction_rule(self.data.extraction_notes, 'title',
                              f'{source}_from_{len(candidates)}_candidates', best_title)
        elif candidates:
            # Aucun valide, logger les rejets
            rejected = [f"{src}:{txt[:30]}" for src, txt in candidates[:3]]
            self.data.add_note(f"title: {len(candidates)} candidats rejetés: {rejected}")
    
    def _extract_reference(self) -> None:
        """Extrait la référence depuis le nom de fichier (PAS depuis refContrat).
        
        CRITIQUE: refContrat dans dataLayer est identique pour tous les marchés
        du même compte client. Il faut utiliser l'ID unique dans le nom de fichier.
        """
        # Format: ao-9594452-1.html → MO-9594452
        match = re.search(r'ao-(\d+)-', self.filepath.name)
        if match:
            self.data.reference = f"MO-{match.group(1)}"
        
        # Note: L'ancien code utilisait refContrat (toujours 1838554)
        # Ce bug a été corrigé le 2026-05-11
    
    def _extract_buyer(self) -> None:
        """Extrait l'acheteur avec priorité au nom réel vs catégorie administrative.
        
        Extrait également la forme juridique et l'activité pour déterminer
        la fonction publique (ex: Santé → hospitalier).
        """
        candidates = []

        # 1. PRIORITÉ HAUTE: Lien acheteur dans print_area_company (visible en haut)
        company_div = self.soup.find('div', id='print_area_company')
        if company_div:
            link = company_div.find('a')
            if link:
                buyer_text = clean_text(link.get_text())
                if len(buyer_text) > 3:
                    candidates.append(('company_link', buyer_text))

        # 2. Section détaillée: "Nom officiel :" (dans ORG-0001 ou ORG-0002)
        text = self.soup.get_text("\n", strip=True)
        match = re.search(r'Nom officiel\s*:\s*([^\n]+)', text, re.IGNORECASE)
        if match:
            buyer_text = clean_text(match.group(1))
            if len(buyer_text) > 3:
                candidates.append(('nom_officiel', buyer_text))

        # 3. Balise meta ou structurée acheteur
        for pattern in [
            r'Acheteur\s*:\s*([^\n]+)',
            r'Pouvoir adjudicateur\s*:\s*([^\n]+)',
        ]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                buyer_text = clean_text(match.group(1))
                if len(buyer_text) > 3:
                    candidates.append(('pattern_search', buyer_text))

        # 4. EVITER: dataLayer 'organisme' (souvent une catégorie générique)
        # Mais le garder comme fallback très basse priorité
        match = re.search(r"'organisme'\s*:\s*'([^']{3,200})'", self.content)
        if match:
            buyer_text = clean_text(match.group(1))
            candidates.append(('datalayer_organisme', buyer_text))

        # Valider et sélectionner
        valid_candidates = []
        for source, candidate in candidates:
            if is_valid_buyer(candidate):
                # Priorité: company_link et nom_officiel sont les meilleurs
                priority = {'company_link': 0, 'nom_officiel': 1, 'pattern_search': 2,
                           'datalayer_organisme': 10}.get(source, 5)
                valid_candidates.append((priority, len(candidate), candidate, source))

        if valid_candidates:
            valid_candidates.sort(key=lambda x: (x[0], -x[1]))
            best_buyer = valid_candidates[0][2]
            source = valid_candidates[0][3]
            self.data.buyer = best_buyer
            log_extraction_rule(self.data.extraction_notes, 'buyer',
                              f'{source}_from_{len(candidates)}_candidates', best_buyer)

            # Détection fonction publique basée sur la forme juridique et activité
            self._detect_fonction_publique(text, best_buyer)
        elif candidates:
            rejected = [f"{src}:{txt[:30]}..." for src, txt in candidates[:3]]
            self.data.add_note(f"buyer: {len(candidates)} candidats rejetés: {rejected}")

    def _detect_fonction_publique(self, text: str, buyer: str) -> None:
        """Détecte la fonction publique basée sur forme juridique et activité."""
        # Chercher forme juridique
        forme_match = re.search(r'Forme juridique.*?acheteur\s*:\s*([^\n]+)', text, re.IGNORECASE)
        activite_match = re.search(r'Activit[eé].*?pouvoir adjudicateur\s*:\s*([^\n]+)', text, re.IGNORECASE)

        forme = forme_match.group(1).strip() if forme_match else ""
        activite = activite_match.group(1).strip() if activite_match else ""

        # Logique de classification
        if 'santé' in activite.lower() or 'hospital' in buyer.lower() or 'chu ' in buyer.lower() or 'chru' in buyer.lower():
            self.data.fonction_publique = 'hospitaliere'
            log_extraction_rule(self.data.extraction_notes, 'fonction_publique',
                              'activite_sante', 'hospitaliere')
        elif 'organisme de droit public' in forme.lower():
            self.data.fonction_publique = 'etat'
            log_extraction_rule(self.data.extraction_notes, 'fonction_publique',
                              'forme_droit_public', 'etat')
        elif 'collectivité' in forme.lower() or 'territoriale' in forme.lower():
            self.data.fonction_publique = 'collectivite'
            log_extraction_rule(self.data.extraction_notes, 'fonction_publique',
                              'forme_collectivite', 'collectivite')
        elif 'établissement public' in forme.lower():
            self.data.fonction_publique = 'etat'
            log_extraction_rule(self.data.extraction_notes, 'fonction_publique',
                              'forme_etablissement_public', 'etat')
    
    def _extract_location(self) -> None:
        """Extrait la localisation depuis le bloc info visible ou Section 5."""
        candidates = []

        # 1. Chercher dans le bloc print_area_info (visible près du titre)
        info_div = self.soup.find('div', id='print_area_info')
        if info_div:
            # Chercher des patterns comme "67 - REGION GRAND EST" ou codes postaux
            text = info_div.get_text("\n", strip=True)
            # Pattern: 2-3 chiffres suivi de texte ou "- REGION"
            match = re.search(r'(\d{2,3}\s*-\s*[^\n,]{3,100})', text)
            if match:
                candidates.append(('info_block', clean_text(match.group(1))))

        # 2. Chercher dans le contenu complet (Section 5 - Lieu d'exécution)
        text = self.soup.get_text("\n", strip=True)

        # Section 5.1.2 Lieu d'exécution avec ville + code postal + NUTS
        lieu_match = re.search(
            r'Lieu.*?ex[ée]cution.*?Ville\s*:\s*([^\n]+).*?Code\s+postal\s*:\s*(\d{5})',
            text, re.DOTALL | re.IGNORECASE
        )
        if lieu_match:
            ville = clean_text(lieu_match.group(1))
            cp = lieu_match.group(2)
            # Chercher aussi le NUTS
            nuts_match = re.search(r'Subdivision pays.*?NUTS\)\s*:\s*([^\n]+)', text, re.IGNORECASE)
            if nuts_match:
                nuts = clean_text(nuts_match.group(1))
                candidates.append(('section_5_lieu', f"{ville} ({cp}) - {nuts}"))
            else:
                candidates.append(('section_5_ville_cp', f"{ville} ({cp})"))
        else:
            # Fallback: juste ville
            match = re.search(r'Ville\s*:\s*([^\n,]{2,50})', text, re.IGNORECASE)
            if match:
                city = clean_text(match.group(1))
                # Chercher aussi le code postal
                cp_match = re.search(r'Code\s+postal\s*:\s*(\d{5})', text, re.IGNORECASE)
                if cp_match:
                    candidates.append(('adresse_complete', f"{city} ({cp_match.group(1)})"))
                else:
                    candidates.append(('ville', city))

        # 3. Chercher NUTS/Subdivision pays
        match = re.search(r'NUTS\)\s*:\s*([^\n,()]+\([^)]+\))', text, re.IGNORECASE)
        if match:
            candidates.append(('nuts', clean_text(match.group(1))))

        # 4. Chercher Code postal / Département générique
        cp_match = re.search(r'Code\s+postal\s*:\s*(\d{5})', text, re.IGNORECASE)
        if cp_match:
            cp = cp_match.group(1)
            dept = cp[:2] if cp.startswith('0') else cp[:2]
            candidates.append(('code_postal', f"({dept})"))

        # Sélectionner le meilleur
        if candidates:
            # Priorité: section_5_lieu (le plus complet), puis info_block, etc.
            priority = {
                'section_5_lieu': 0, 'section_5_ville_cp': 1,
                'info_block': 2, 'adresse_complete': 3,
                'nuts': 4, 'ville': 5, 'code_postal': 6
            }
            candidates.sort(key=lambda x: (priority.get(x[0], 10), -len(x[1])))
            best = candidates[0]
            self.data.location = best[1]
            log_extraction_rule(self.data.extraction_notes, 'location', best[0], best[1])
    
    def _extract_deadline(self) -> None:
        """Extrait la date limite de réponse."""
        candidates = []
        
        # 1. Pattern visible: "Limite de réponse : DD/MM/YYYY"
        text = self.soup.get_text("\n", strip=True)
        match = re.search(
            r'Limite\s+de\s+r[ée]ponse\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            text,
            re.IGNORECASE
        )
        if match:
            candidates.append(('limite_visible', match.group(1)))
        
        # 2. Pattern avec span font-bold (comme vu dans l'HTML)
        match = re.search(
            r'Limite\s+de\s+r[ée]ponse\s*[:\-]?\s*<[^>]*font-bold[^>]*>(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            self.content,
            re.IGNORECASE
        )
        if match:
            candidates.append(('limite_bold_span', match.group(1)))
        
        # 3. Pattern générique "Date limite"
        match = re.search(
            r'Date\s+limite[^\n]*?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            text,
            re.IGNORECASE
        )
        if match:
            candidates.append(('date_limite', match.group(1)))
        
        # Parser la première date trouvée
        for source, date_str in candidates:
            from datetime import datetime
            for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y']:
                try:
                    self.data.date_limite = datetime.strptime(date_str, fmt)
                    log_extraction_rule(self.data.extraction_notes, 'date_limite', 
                                      f'{source}_{fmt}', date_str)
                    return
                except ValueError:
                    continue
    
    def _extract_cpv(self) -> None:
        """Extrait les codes CPV."""
        matches = re.findall(r"'codeCpv'\s*:\s*'(\d+)'", self.content)
        if not matches:
            matches = re.findall(r'(\d{8})', self.soup.get_text())

        self.data.cpv = list(set(matches))[:5]  # Max 5 codes
        if matches:
            log_extraction_rule(self.data.extraction_notes, 'cpv',
                              f'found_{len(matches)}_codes', ','.join(matches[:3]))

    def _extract_procedure_and_nature(self) -> None:
        """Extrait le type de procédure et la nature du marché.

        Depuis Section 2:
        - Type de procédure : Ouverte, Restreinte, Procédure négociée, etc.
        - Nature du marché : Services, Fournitures, Travaux
        """
        text = self.soup.get_text("\n", strip=True)

        # Type de procédure
        proc_match = re.search(r'Type de proc[ée]dure\s*:\s*([^\n]+)', text, re.IGNORECASE)
        if proc_match:
            procedure = clean_text(proc_match.group(1))
            self.data.procedure_type = procedure
            log_extraction_rule(self.data.extraction_notes, 'procedure_type',
                              'section_2', procedure)

        # Nature du marché (peut apparaître dans Section 2.1.1 et Section 5.1.1)
        nature_matches = re.findall(r'Nature du march[ée]\s*:\s*([^\n]+)', text, re.IGNORECASE)
        if nature_matches:
            # Prendre la première occurrence (généralement la plus fiable)
            nature = clean_text(nature_matches[0])
            self.data.contract_nature = nature
            log_extraction_rule(self.data.extraction_notes, 'contract_nature',
                              'section_2_or_5', nature)

    def _extract_duration_and_amounts(self) -> None:
        """Extrait la durée estimée et les montants avec hiérarchie stricte.

        HIÉRARCHIE DES SOURCES:
        1. Blocs structurés (Section 5.1.3, 5.1.5) - PRIORITÉ MAXIMALE
        2. Section 2.1.3 pour valeur globale
        3. Prose libre (Description des options) - FALLBACK UNIQUEMENT

        RÈGLES MÉTIERS:
        - Durée: utiliser 5.1.3 Durée estimée en priorité
        - Montant: privilégier "Valeur estimée hors TVA" sur "Valeur maximale"
        - Si plusieurs valeurs dans la prose, ne pas choisir automatiquement
        - En cas de conflit: bloc structuré gagne sur prose libre

        Normalisation:
        - "4 An" → "4 ans"
        - "660,000 Euro" → "660000 EUR"
        """
        text = self.soup.get_text("\n", strip=True)

        # Variables pour suivre la source des données
        duree_source = None
        duree_value = None
        montant_estime_source = None
        montant_max_source = None
        notes_structured = []

        # ============================================================
        # 1. EXTRACTION DES BLOCS STRUCTURÉS (Section 5 - Lots) - PRIORITÉ MAX
        # ============================================================
        # Les valeurs spécifiques des lots (Valeur estimée hors TVA) priment
        # sur les valeurs globales car elles sont plus précises
        
        # Pattern 1: Lots avec identifiant LOT-XXXX (format standard)
        lot_pattern = r'5\.1\s+Identifiant technique du lot\s*:\s*(LOT-\d+)'
        lot_matches = list(re.finditer(lot_pattern, text))
        
        # Pattern 2: Fallback pour les pages sans LOT-XXXX explicite mais avec Section 5
        has_section_5 = bool(re.search(r'Section\s+5', text, re.IGNORECASE))
        if not lot_matches and has_section_5:
            # Chercher des alternatives comme "Lot X" ou "LOT-XXXX" sans le préfixe 5.1
            alt_lot_pattern = r'(Lot\s+\d+|LOT-\d+)'
            alt_matches = list(re.finditer(alt_lot_pattern, text, re.IGNORECASE))
            if alt_matches:
                # Créer des pseudo-lots à partir de ces mentions
                lot_matches = alt_matches

        lots_data = []
        for i, lot_match in enumerate(lot_matches):
            lot_id = lot_match.group(1)
            lot_start = lot_match.end()

            # Déterminer la fin de ce lot
            if i + 1 < len(lot_matches):
                lot_end = lot_matches[i + 1].start()
            else:
                next_section = re.search(r'Section\s+6', text[lot_start:])
                if next_section:
                    lot_end = lot_start + next_section.start()
                else:
                    lot_end = lot_start + 2000

            lot_text = text[lot_start:lot_end]

            # --- PRIORITÉ 1: Durée structurée (5.1.3) ---
            # Pattern strict: "Durée : 4 An" ou "Durée : 6 mois" ou "48 Mois"
            # Doit avoir un nombre suivi d'une unité de temps valide
            duration_match = re.search(
                r'Durée\s*:\s*(\d+)\s*(?:mois?|an(?:s|née)?)\b',
                lot_text,
                re.IGNORECASE | re.DOTALL
            )
            duration = None
            if duration_match:
                nombre = duration_match.group(1)
                # Déterminer l'unité à partir du texte matché
                match_text = duration_match.group(0).lower()
                if 'mois' in match_text:
                    duration = f"{nombre} mois"
                elif 'an' in match_text or 'année' in match_text:
                    duration = f"{nombre} ans"
                duree_source = f'{lot_id}_5.1.3'

            # --- PRIORITÉ 1: Montants structurés (5.1.5) ---
            # Chercher "Valeur estimée hors TVA" en PRIORITÉ
            valeur_estimee_match = re.search(
                r'Valeur estimée hors TVA\s*:\s*([\d,\.]+)\s*Euro',
                lot_text, re.IGNORECASE
            )
            valeur_max_match = re.search(
                r'Valeur maximale.*?([\d,\.]+)\s*Euro',
                lot_text, re.IGNORECASE
            )

            valeur_estimee = None
            valeur_max = None

            if valeur_estimee_match:
                amount_str = valeur_estimee_match.group(1).replace(',', '').replace(' ', '')
                try:
                    valeur_estimee = int(amount_str)
                    montant_estime_source = f'{lot_id}_5.1.5_estimee'
                except ValueError:
                    pass

            if valeur_max_match:
                amount_str = valeur_max_match.group(1).replace(',', '').replace(' ', '')
                try:
                    valeur_max = int(amount_str)
                    montant_max_source = f'{lot_id}_5.1.5_max'
                except ValueError:
                    pass

            # Stocker pour la note
            lot_info = {'lot_id': lot_id}
            if duration:
                lot_info['duration'] = duration
            if valeur_estimee:
                lot_info['valeur_estimee'] = valeur_estimee
            if valeur_max:
                lot_info['valeur_max'] = valeur_max
            if lot_info:
                lots_data.append(lot_info)

        # ============================================================
        # 2. AFFECTATION DES VALEURS EXTRAITES
        # ============================================================

        # --- DURÉE: priorité au bloc structuré ---
        if lots_data and lots_data[0].get('duration'):
            duree_value = lots_data[0]['duration']
            mois = self._parse_duration_to_months(duree_value)
            if mois:
                self.data.duree_mois = mois
                log_extraction_rule(self.data.extraction_notes, 'duree_mois',
                                  'section_5_1_3_structured', f"{duree_value} = {mois} mois")

        # --- MONTANT: stratégie selon les données disponibles ---
        if lots_data:
            first_lot = lots_data[0]
            
            # Cas 1: Le lot a une Valeur estimée → l'utiliser (priorité max)
            if first_lot.get('valeur_estimee'):
                self.data.estimation_eur = float(first_lot['valeur_estimee'])
                log_extraction_rule(self.data.extraction_notes, 'estimation_eur',
                                  'section_5_1_5_valeur_estimee', f"{first_lot['valeur_estimee']} EUR")
                notes_structured.append(f"Valeur estimée: {first_lot['valeur_estimee']} EUR")
            
            # Cas 2: Le lot n'a que Valeur maximale → chercher valeur globale d'abord
            elif first_lot.get('valeur_max'):
                # Chercher valeur globale Section 2.1.3 qui est plus fiable
                section2_match = re.search(r'Section\s+2.*?(?=Section\s+3|\Z)', text, re.DOTALL | re.IGNORECASE)
                if section2_match:
                    section2_text = section2_match.group(0)
                    global_value_match = re.search(
                        r'2\.1\.3.*?Valeur.*?([\d,\.]+)\s*Euro',
                        section2_text, re.DOTALL | re.IGNORECASE
                    )
                    if global_value_match:
                        amount_str = global_value_match.group(1).replace(',', '').replace(' ', '')
                        try:
                            amount = int(amount_str)
                            self.data.estimation_eur = float(amount)
                            log_extraction_rule(self.data.extraction_notes, 'estimation_eur',
                                              'section_2_1_3_global', f"{amount} EUR")
                            notes_structured.append(f"Valeur globale accord-cadre: {amount} EUR")
                        except ValueError:
                            pass
                
                # Si toujours pas de valeur, utiliser la valeur maximale du lot
                if not self.data.estimation_eur:
                    self.data.estimation_eur = float(first_lot['valeur_max'])
                    log_extraction_rule(self.data.extraction_notes, 'estimation_eur',
                                      'section_5_1_5_valeur_max_fallback', f"{first_lot['valeur_max']} EUR (maximale)")
                    notes_structured.append(f"Valeur maximale utilisée comme fallback: {first_lot['valeur_max']} EUR")

        # ============================================================
        # 3. FALLBACK: SECTION 5 DIRECTE (sans lots explicites)
        # ============================================================
        # Pour les pages avec Section 5 mais sans structure LOT-XXXX
        if not self.data.duree_mois and has_section_5:
            section5_match = re.search(r'Section\s+5.*?(?=Section\s+6|\Z)', text, re.DOTALL | re.IGNORECASE)
            if section5_match:
                section5_text = section5_match.group(0)
                
                # Chercher 5.1.3 Durée directement avec pattern strict
                duree_513_match = re.search(
                    r'5\.1\.3.*?Durée\s*:\s*(\d+)\s*(?:mois?|an(?:s|née)?)\b',
                    section5_text, re.IGNORECASE | re.DOTALL
                )
                if duree_513_match:
                    nombre = duree_513_match.group(1)
                    match_text = duree_513_match.group(0).lower()
                    if 'mois' in match_text:
                        duree_str = f"{nombre} mois"
                    elif 'an' in match_text:
                        duree_str = f"{nombre} ans"
                    else:
                        duree_str = f"{nombre} ans"
                    mois = self._parse_duration_to_months(duree_str)
                    if mois:
                        self.data.duree_mois = mois
                        log_extraction_rule(self.data.extraction_notes, 'duree_mois',
                                          'section_5_1_3_direct', f"{duree_str} = {mois} mois")

        # ============================================================
        # 4. FALLBACK: VALEUR GLOBALE (Section 2.1.3) si pas de valeur lot
        # ============================================================
        if not self.data.estimation_eur:
            section2_match = re.search(r'Section\s+2.*?(?=Section\s+3|\Z)', text, re.DOTALL | re.IGNORECASE)
            if section2_match:
                section2_text = section2_match.group(0)
                # Chercher 2.1.3 Valeur
                global_value_match = re.search(
                    r'2\.1\.3.*?Valeur.*?([\d,\.]+)\s*Euro',
                    section2_text, re.DOTALL | re.IGNORECASE
                )
                if global_value_match:
                    amount_str = global_value_match.group(1).replace(',', '').replace(' ', '')
                    try:
                        amount = int(amount_str)
                        self.data.estimation_eur = float(amount)
                        log_extraction_rule(self.data.extraction_notes, 'estimation_eur',
                                          'section_2_1_3_global_fallback', f"{amount} EUR")
                        notes_structured.append(f"Valeur globale (Section 2.1.3): {amount} EUR")
                    except ValueError:
                        pass

        # Noter les différences entre valeurs globales et valeurs de lots
        if lots_data and self.data.estimation_eur:
            first_lot = lots_data[0]
            if first_lot.get('valeur_estimee'):
                lot_est = first_lot['valeur_estimee']
                global_val = int(self.data.estimation_eur)
                if lot_est != global_val:
                    notes_structured.append(f"Note: Valeur estimée du lot ({lot_est}) ≠ Valeur extraite ({global_val})")

        # ============================================================
        # 4. FALLBACK: PROSE LIBRE (uniquement si pas de structuré)
        # ============================================================
        if not self.data.duree_mois:
            # Chercher dans la prose libre (Description des options)
            prose_duree_patterns = [
                r'Offre de base.*?(\d+)\s*an',
                r'durée ferme de (\d+)\s*mois',
            ]
            for pattern in prose_duree_patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if match:
                    nombre = match.group(1)
                    if 'mois' in pattern:
                        try:
                            self.data.duree_mois = int(nombre)
                            log_extraction_rule(self.data.extraction_notes, 'duree_mois',
                                              'prose_libre_fallback', f"{nombre} mois (prose)")
                            notes_structured.append(f"Durée extraite de la prose: {nombre} mois")
                        except ValueError:
                            pass
                    else:
                        duree_str = f"{nombre} ans"
                        mois = self._parse_duration_to_months(duree_str)
                        if mois:
                            self.data.duree_mois = mois
                            log_extraction_rule(self.data.extraction_notes, 'duree_mois',
                                              'prose_libre_fallback', f"{duree_str} = {mois} mois (prose)")
                            notes_structured.append(f"Durée extraite de la prose: {duree_str}")
                    break  # Prendre la première trouvée

        # ============================================================
        # 5. NOTES STRUCTURÉES
        # ============================================================
        if lots_data:
            lots_note = "Lots: " + "; ".join([
                lot['lot_id'] +
                (f" ({lot.get('duration', '')})" if lot.get('duration') else "") +
                (f" est={lot.get('valeur_estimee')}EUR" if lot.get('valeur_estimee') else "") +
                (f" max={lot.get('valeur_max')}EUR" if lot.get('valeur_max') else "")
                for lot in lots_data
            ])
            self.data.add_note(lots_note)

        if notes_structured:
            for note in notes_structured:
                self.data.add_note(note)

    def _parse_duration_to_months(self, duration_str: str) -> Optional[int]:
        """Convertit une durée textuelle en nombre de mois.
        
        Ex: "4 ans" → 48, "6 mois" → 6, "1 an" → 12
        """
        if not duration_str:
            return None
        
        # Chercher nombre + unité
        match = re.search(r'(\d+)\s*(an|ans|mois|month|months)', duration_str, re.IGNORECASE)
        if match:
            nombre = int(match.group(1))
            unite = match.group(2).lower()
            
            if unite in ('an', 'ans', 'year', 'years'):
                return nombre * 12
            elif unite in ('mois', 'month', 'months'):
                return nombre
        
        return None


# Import nécessaire
from ao_etl.models.market import ExtractionStatus
