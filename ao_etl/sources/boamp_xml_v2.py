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
        
        # 2. Collecter les candidats acheteur (DOM-first, puis regex fallback)
        buyer_candidates = []

        # DOM-first extraction (section I.1)
        dom_buyer = self._extract_buyer_dom()
        if dom_buyer:
            buyer_candidates.append(FieldCandidate("buyer", dom_buyer, "dom_nom_officiel", score=50))

        # Regex fallback patterns
        buyer_patterns = [
            (r'Nom\s+officiel\s*[:\-]?\s*([^<\n]{3,200}?)(?:\s*<|\s*Adresse|\s*Code\s+postal|$)', 'regex_nom_officiel'),
            (r'Nom\s+complet\s+de\s+l\'?acheteur\s*[:\-]?\s*([^<\n]{3,200}?)(?:\s*<|\s*Adresse|$)', 'regex_nom_complet'),
            (r'Acheteur\s+public\s*[:\-]?\s*([^<\n]{3,200}?)(?:\s*<|$)', 'regex_acheteur_public'),
        ]
        for pattern, rule in buyer_patterns:
            m = re.search(pattern, text, re.I)
            if m:
                val = normalize_text(m.group(1))
                if val and len(val) > 3 and not re.match(r'^\d+(\.\d+)*$', val):
                    buyer_candidates.append(FieldCandidate("buyer", val, rule, score=40))

        # Rejeter explicitement les faux candidats (organisation d'info complémentaire)
        org_info = self._value_after_label(
            text,
            "Organisation qui fournit des informations complémentaires sur la procédure de passation de marché"
        )
        if org_info:
            buyer_candidates.append(FieldCandidate("buyer", org_info, "org_info_complementaires", score=-100))
        
        # 3. Champs structurés directs
        result.reference = self._extract_reference(text)
        result.estimation = self._money_after_label(text, "Valeur estimée hors TVA")
        result.duration = self._duration(text)
        result.deadline = self._deadline(text)
        result.location = self._location(text)
        
        # 3.5 Type de procédure, nature du marché, fonction publique
        result.raw['procedure_type'] = self._procedure_type(text)
        result.raw['contract_nature'] = self._contract_nature(text)
        result.raw['fonction_publique'] = self._fonction_publique(text, result.buyer)
        
        # 4. URL source (BOAMP)
        result.raw['url_source'] = self._build_url(text)
        
        # 4.5 CPV codes
        result.raw['cpv_codes'] = self._extract_cpv()
        
        # 4.6 Duration months
        result.raw['duration_months'] = self._extract_duration_months()
        
        # 5. Sélectionner le meilleur titre
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
        """Extrait la valeur après un label avec plusieurs patterns."""
        patterns = [
            # Pattern 1: Label suivi de : ou - puis valeur
            rf"{re.escape(label)}\s*[:\-]?\s*(.+?)(?:\n|</|\Z)",
            # Pattern 2: Label sur sa ligne puis valeur sur ligne suivante
            rf"{re.escape(label)}\s*\n+(.+?)(?:\n|</|\Z)",
            # Pattern 3: Label dans balise, valeur dans balise suivante
            rf">{re.escape(label)}<[^>]*>\s*(.+?)(?:\n|</|\Z)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.I)
            if m:
                val = normalize_text(m.group(1))
                # Rejeter les valeurs qui sont juste des numéros de section (1.1, 2.3, etc.)
                if val and not re.match(r'^\d+(\.\d+)*$', val):
                    return val
        return ""

    _BUYER_LABEL_BLACKLIST = frozenset([
        "opérateur", "opérateur économique", "nom officiel",
        "adresse", "1.1", "i.1", "pouvoir adjudicateur",
        "autorité contractante", "entité adjudicatrice",
    ])

    def _extract_buyer_dom(self) -> str:
        """Extrait l'acheteur via DOM-first approach (section I.1 Nom officiel).

        Structure JOUE/BOAMP attendue dans le DOM :
          <div>
            <span class="label">Nom officiel</span>
            <span>: </span>
            <span class="data">VALEUR</span>
          </div>
        ou variante sans classes:
          <div>
            <span class="fr-text--bold">Nom officiel</span>
            <span>:</span>
            <span>VALEUR</span>
          </div>
        """
        soup = self.context.soup

        for label_span in soup.find_all('span'):
            if not re.match(r'^Nom\s+officiel$', label_span.get_text(strip=True), re.I):
                continue
            parent = label_span.parent
            if parent is None:
                continue
            # Chercher le span suivant contenant la vraie valeur
            # (sauter le span du séparateur ":")
            found_label = False
            for sibling in parent.children:
                if not hasattr(sibling, 'get_text'):
                    continue
                if sibling is label_span:
                    found_label = True
                    continue
                if not found_label:
                    continue
                sib_text = normalize_text(sibling.get_text())
                if not sib_text or sib_text in (':', ': '):
                    continue
                if len(sib_text) > 3 and not re.match(r'^\d+(\.\d+)*$', sib_text):
                    if sib_text.casefold() not in self._BUYER_LABEL_BLACKLIST:
                        return sib_text
            # Fallback: span.class='data' inside parent
            data_span = parent.find('span', class_='data')
            if data_span:
                val = normalize_text(data_span.get_text())
                if val and len(val) > 3 and val.casefold() not in self._BUYER_LABEL_BLACKLIST:
                    return val

        return ""

    def _extract_reference(self, text: str) -> str:
        """Extrait la référence BOAMP depuis 'Identifiant interne' ou nom de fichier."""
        # 1. "Identifiant interne" - PRIORITÉ MAX
        ref = self._value_after_label(text, "Identifiant interne")
        if ref and len(ref) < 60 and ref != '-':
            return ref

        # 2. Pattern fichier BOAMP dans le nom (26-XXXXX.html ou 3boampXXXX.html)
        name = self.filename().lower()

        # 26-41049.html → 26-41049
        m = re.search(r'(26-\d+)', name)
        if m:
            return m.group(1)

        # 3boamp2640079.html → 3/boamp/2640079
        m = re.search(r'(\dboamp\d+)', name)
        if m:
            ref = m.group(1)
            return f"{ref[0]}/boamp/{ref[6:]}"

        return ""

    def _money_after_label(self, text: str, label: str) -> str:
        """Extrait une valeur monétaire après un label (plusieurs patterns)."""
        # Pattern 1: Label sur sa ligne puis valeur puis devise
        pattern = re.compile(rf"{re.escape(label)}\s*\n+([\d.,\s]+)\s*\n+(Euro|EUR)", re.I)
        m = pattern.search(text)
        if m:
            value = normalize_text(m.group(1))
            currency = normalize_text(m.group(2))
            return f"{value} {currency}"
        
        # Pattern 2: Label: valeur EUR (sur même ligne)
        pattern2 = re.compile(rf"{re.escape(label)}\s*[:\-]?\s*([\d.,\s]+)\s*(?:EUR|€|Euros?)", re.I)
        m = pattern2.search(text)
        if m:
            value = normalize_text(m.group(1))
            return f"{value} EUR"
        
        # Pattern 3: Juste chercher la valeur + EUR après le label (flexible)
        pattern3 = re.compile(rf"{re.escape(label)}.*?([\d]{{1,3}}(?:\s*[\d]{{3}}){{1,4}}(?:[,.]\d+)?)\s*(?:EUR|€)", re.I | re.S)
        m = pattern3.search(text)
        if m:
            value = m.group(1).replace(' ', '').replace(',', '.')
            return f"{value} EUR"
        
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
    
    def _build_url(self, text: str) -> str:
        """Construit l'URL BOAMP depuis l'identifiant."""
        identifiant = self._value_after_label(text, "Identifiant interne")
        if identifiant:
            # URL BOAMP: https://www.boamp.fr/avis/detail/[identifiant]
            return f"https://www.boamp.fr/avis/detail/{identifiant}"
        return ""
    
    def _procedure_type(self, text: str) -> str:
        """Extrait le type de procédure."""
        patterns = [
            r"Type de proc[ée]dure\s*[:\-\n]\s*([^\n]+)",
            r"Proc[ée]dure\s*[:\-\n]\s*([^\n]+)",
            r"(Appel d'offres ouvert|Proc[ée]dure n[ée]goci[ée]e|March[ée] n[ée]goci[ée]|Dialogue comp[ée]titif)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return normalize_text(m.group(1))
        return ""
    
    def _contract_nature(self, text: str) -> str:
        """Extrait la nature du marché."""
        patterns = [
            r"Nature du march[ée]\s*[:\-\n]\s*([^\n]+)",
            r"Type de march[ée]\s*[:\-\n]\s*([^\n]+)",
            r"(Services|Fournitures|Travaux|Prestations intellectuelles)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                nature = normalize_text(m.group(1))
                if "service" in nature.lower() or "intellectuel" in nature.lower():
                    return "Services"
                elif "fourniture" in nature.lower():
                    return "Fournitures"
                elif "travail" in nature.lower() or "travaux" in nature.lower():
                    return "Travaux"
                return nature
        return ""
    
    def _fonction_publique(self, text: str, buyer: str) -> str:
        """Détecte la fonction publique."""
        forme_match = re.search(r"Forme juridique.*?acheteur\s*[:\-\n]\s*([^\n]+)", text, re.IGNORECASE)
        activite_match = re.search(r"Activit[ée].*?principale\s*[:\-\n]\s*([^\n]+)", text, re.IGNORECASE)
        
        forme = forme_match.group(1).strip() if forme_match else ""
        activite = activite_match.group(1).strip() if activite_match else ""
        buyer_str = buyer or ""
        
        if any(x in activite.lower() for x in ["santé", "hospital", "soin"]) or \
           any(x in buyer_str.lower() for x in ["chu ", "chru", "hôpital", "hopital"]):
            return "hospitaliere"
        elif any(x in forme.lower() for x in ["organisme de droit public", "établissement public", "ministère", "état"]):
            return "etat"
        elif any(x in forme.lower() for x in ["collectivité", "territoriale"]):
            return "territoriale"
        elif any(x in buyer_str.lower() for x in ["ministère", "dgfip"]):
            return "etat"

        # Fallback sur texte
        if "santé" in text.lower() or "hospitalier" in text.lower():
            return "hospitaliere"
        elif "collectivité" in text.lower():
            return "territoriale"
        elif "ministère" in text.lower() or "état" in text.lower():
            return "etat"

        return "-"
