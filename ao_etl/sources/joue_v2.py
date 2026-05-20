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
        soup = self.context.soup

        # DOM-first: chercher span.class='data' sibling du label "Titre"
        for label_span in soup.find_all('span'):
            if not re.match(r'^Titre$', label_span.get_text(strip=True), re.I):
                continue
            parent = label_span.parent
            if parent is None:
                continue
            data_span = parent.find('span', class_='data')
            if data_span:
                val = normalize_text(data_span.get_text(strip=True))
                if val and len(val) >= 10:
                    title_candidates.append(FieldCandidate("title", val, "dom_titre_data", score=55))
                    break
            # Variante: parcourir les siblings après le label
            found_label = False
            for sibling in parent.children:
                if not hasattr(sibling, 'get_text'):
                    continue
                if sibling is label_span:
                    found_label = True
                    continue
                if not found_label:
                    continue
                sib_text = normalize_text(sibling.get_text(strip=True))
                if not sib_text or sib_text in (':', ': '):
                    continue
                if len(sib_text) >= 10:
                    title_candidates.append(FieldCandidate("title", sib_text, "dom_titre_sibling", score=50))
                break

        # Pattern: Objet / Description
        m = re.search(r"Objet\s*:\s*([^.\n]{10,300})", text, re.I)
        if m:
            title_candidates.append(FieldCandidate(
                "title", 
                normalize_text(m.group(1)), 
                "objet_pattern", 
                score=40
            ))
        
        # Pattern: Titre du marché — s'arrête sur fin de ligne (tolère les virgules)
        m = re.search(r"Titre\s*:\s*([^\n]{10,400})", text, re.I)
        if m:
            title_candidates.append(FieldCandidate(
                "title",
                normalize_text(m.group(1)),
                "titre_pattern",
                score=45
            ))
        
        # 3. Collecter les candidats acheteur (DOM-first + regex fallback)
        buyer_candidates = []

        # DOM-first extraction pour JOUE (section I.1 Nom officiel)
        dom_buyer = self._extract_buyer_dom()
        if dom_buyer:
            buyer_candidates.append(FieldCandidate("buyer", dom_buyer, "dom_nom_officiel", score=50))

        # Patterns regex fallback - patterns simplifiés pour matcher l'autorité
        buyer_patterns = [
            # Pattern prioritaire: Nom et adresse de l'autorité attribuant le marché
            # Utilise .*? pour capturer tout après le : jusqu'à la fin de ligne
            (r"Nom\s+et\s+adresse\s+de\s+l.*?autorit[ée].*?attribuant.*?march[ée].*?[:\-]\s*(.+?)(?:\n|</p>|$)", 'autorite_attribuant'),
            (r"Nom\s+officiel\s*[:\-]?\s*([^<\n]{3,200}?)(?:\s*<|\s*Adresse|\s*Code\s+postal|$)", 'nom_officiel'),
            (r"Nom\s+complet\s+de\s+l.*?acheteur\s*[:\-]?\s*([^<\n]{3,200}?)(?:\s*<|$)", 'nom_complet'),
            (r"Acheteur\s+public\s*[:\-]?\s*([^<\n]{3,200}?)(?:\s*<|$)", 'acheteur_public'),
        ]
        for pattern, rule in buyer_patterns:
            m = re.search(pattern, text, re.I)
            if m:
                val = normalize_text(m.group(1))
                # Rejeter les numéros de section (1.1, 2.3, etc.)
                if val and len(val) > 3 and not re.match(r'^\d+(\.\d+)*$', val):
                    buyer_candidates.append(FieldCandidate("buyer", val, rule, score=45 if 'autorite' in rule else 40))
        
        # 4. Champs structurés
        result.location = self._extract_location(text)
        result.deadline = self._extract_deadline(text)
        result.estimation = self._extract_estimation(text)
        result.duration = self._extract_duration(text)
        
        # 4.5 Type de procédure, nature du marché, fonction publique
        result.raw['procedure_type'] = self._procedure_type(text)
        result.raw['contract_nature'] = self._contract_nature(text)
        result.raw['fonction_publique'] = self._fonction_publique(text, result.buyer)
        
        # 5. URL source (JOUE/TED)
        result.raw['url_source'] = self._build_url(result.reference)
        
        # 5.5 CPV codes
        result.raw['cpv_codes'] = self._extract_cpv()
        
        # 5.6 Duration months
        result.raw['duration_months'] = self._extract_duration_months()
        
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
        # Pattern dans le texte: 13/joue/XXXXXXXX (préserve les zéros initiaux)
        m = re.search(r"13/joue/(\d{8,12})", text, re.I)
        if m:
            return f"13/joue/{m.group(1)}"

        # Fallback: depuis le nom de fichier (13joueXXXXXXXXYYYY → 13/joue/XXXXXXXXYYYY)
        # Format: 13joue002671162026 où 00267116 est le numéro et 2026 l'année
        name = self.filename()
        m = re.match(r"13joue(\d{8,12})", name, re.I)
        if m:
            return f"13/joue/{m.group(1)}"

        # Dernier fallback: extraire tout ce qui ressemble à 13joue
        m = re.search(r"13joue([a-z0-9]+)", name, re.I)
        if m:
            return f"13/joue/{m.group(1)}"

        return name.replace('.html', '')

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
            r"Lieu\s+d[']?ex[ée]cution\s*[:\-]?\s*([^\.\n,]{3,100}(?:,\s*[^\.\n]{3,50})?)",
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
        nuts_m = re.search(r"NUTS\s*[:\-]?\s*([^\.\n]{3,50})", text, re.I)
        if nuts_m:
            return normalize_text(nuts_m.group(1))
        
        return ""
    
    def _procedure_type(self, text: str) -> str:
        """Extrait le type de procédure depuis le texte ou les métadonnées JSON."""
        # 1. Chercher dans les métadonnées weborama (JSON embarqué avec échappement Unicode)
        # \u0022 = " (guillemet) dans le fichier HTML
        weborama_match = re.search(r'\\u0022type_procedure\\u0022\s*:\s*\\u0022(.*?)\\u0022', text)
        if weborama_match:
            val = weborama_match.group(1)
            # Décoder les caractères Unicode (\u00e9 -> é)
            try:
                val = val.encode().decode('unicode_escape')
            except:
                pass
            return normalize_text(val)
        
        # 2. Chercher dans le texte avec des patterns classiques
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
        """Extrait la nature du marché depuis le texte ou les métadonnées JSON."""
        # 1. Chercher dans les métadonnées weborama (JSON embarqué avec échappement Unicode)
        # \u0022 = " (guillemet) dans le fichier HTML
        weborama_match = re.search(r'\\u0022type_marche\\u0022\s*:\s*\\u0022(.*?)\\u0022', text)
        if weborama_match:
            nature = weborama_match.group(1)
            # Décoder les caractères Unicode (\u00e9 -> é)
            try:
                nature = nature.encode().decode('unicode_escape')
            except:
                pass
            nature = normalize_text(nature)
            if "service" in nature.lower():
                return "Services"
            elif "fourniture" in nature.lower():
                return "Fournitures"
            elif "travail" in nature.lower():
                return "Travaux"
            return nature
        
        # 2. Chercher dans le texte avec des patterns classiques
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
