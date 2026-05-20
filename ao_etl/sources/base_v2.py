"""Classe de base pour les extracteurs de source - Version 2 avec architecture candidate/trace."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


@dataclass(slots=True)
class FieldCandidate:
    """Un candidat pour un champ donné avec sa règle d'extraction et score."""
    field_name: str
    value: str
    rule: str
    score: int = 0
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExtractionTrace:
    """Trace d'une décision d'extraction pour la traçabilité."""
    field_name: str
    rule: str
    value: str
    score: int | None = None
    accepted: bool = True
    reason: str | None = None

    def to_note(self) -> str:
        status = "accepted" if self.accepted else "rejected"
        score_part = f" score={self.score}" if self.score is not None else ""
        reason_part = f" reason={self.reason}" if self.reason else ""
        return f"{self.field_name}: {self.rule} -> {status}{score_part} value={self.value!r}{reason_part}"


@dataclass(slots=True)
class ExtractionResult:
    """Résultat normalisé d'une extraction HTML."""
    source_type: str
    reference: str = ""
    title: str = ""
    buyer: str = ""
    location: str = ""
    deadline: str = ""
    duration: str = ""
    estimation: str = ""
    extraction_notes: list[str] = field(default_factory=list)
    review_needed: bool = False
    confidence: int = 0
    raw: dict[str, Any] = field(default_factory=dict)

    def add_trace(self, trace: ExtractionTrace) -> None:
        self.extraction_notes.append(trace.to_note())

    def add_note(self, note: str) -> None:
        self.extraction_notes.append(note)

    def to_pipeline_dict(self) -> dict[str, str]:
        return {
            "Référence": self.reference,
            "Intitulé synthétique": self.title,
            "Acheteur_auto": self.buyer,
            "Localisation_auto": self.location,
            "Date_limite_auto": self.deadline,
            "Durée initiale du marché": self.duration,
            "Estimation_auto": self.estimation,
            "review_needed": "yes" if self.review_needed else "",
            "extraction_notes": " | ".join(self.extraction_notes),
            "source_type": self.source_type,
        }


@dataclass(slots=True)
class ExtractionContext:
    """Contexte d'extraction pour un fichier HTML."""
    file_path: Path
    html: str
    soup: BeautifulSoup


class BaseExtractor(ABC):
    """Classe abstraite pour tous les extracteurs de source.
    
    Architecture candidate/trace:
    - Les extracteurs proposent des candidats avec règles et scores
    - validation.py arbitre la sélection finale
    - Toutes les décisions sont tracées dans extraction_notes
    """
    source_type: str = "UNKNOWN"

    def __init__(self, context: ExtractionContext) -> None:
        self.context = context

    @abstractmethod
    def extract(self) -> ExtractionResult:
        """Extrait les données du fichier HTML.
        
        Returns:
            ExtractionResult avec tous les champs extraits et traces
        """
        raise NotImplementedError

    def text(self) -> str:
        """Retourne le texte brut du HTML nettoyé."""
        return self.context.soup.get_text("\n", strip=True)

    def filename(self) -> str:
        """Retourne le nom du fichier."""
        return self.context.file_path.name

    @staticmethod
    def _clean_text(value: str) -> str:
        """Normalise les apostrophes typographiques et guillemets.

        Remplace ' (U+2019) par ' (U+0027) et les guillemets courbes
        par des guillemets droits, cohérent avec le comportement legacy.
        """
        return (
            value
            .replace("\u2019", "'")   # ' → '
            .replace("\u2018", "'")   # ' → '
            .replace("\u201c", '"')   # " → "
            .replace("\u201d", '"')   # " → "
        )

    def _extract_cpv(self) -> list[str]:
        """Extrait les codes CPV du HTML de manière déterministe.

        Stratégies (dans l'ordre de priorité):
        1. Attributs data-code-cpv="XXXXXXXX" (PLACE_NUMERIC, France Marchés)
        2. Codes 8 chiffres dans le texte (fallback)

        Returns:
            Liste de codes CPV uniques (max 10), formatés comme strings 8 chiffres.
        """
        html = self.context.html
        text = self.text()
        codes: set[str] = set()

        # Pattern 1: Attributs data-code-cpv (utilisé par PLACE_NUMERIC, France Marchés)
        matches = re.findall(r'data-code-cpv="(\d+)"', html)
        for m in matches:
            if len(m) == 8 and m.isdigit():
                codes.add(m)

        # Pattern 2: Codes CPV dans des balises spécifiques (BOAMP/JOUE)
        # Chercher des spans ou divs contenant des codes 8 chiffres
        matches = re.findall(r'<(?:span|div|td|p)[^>]*>(\d{8})</(?:span|div|td|p)>', html)
        for m in matches:
            codes.add(m)

        # Pattern 3: Fallback - chercher tous les codes 8 chiffres dans le texte
        # mais seulement ceux qui ressemblent à des CPV (commençant par des chiffres communs)
        if not codes:
            matches = re.findall(r'\b(\d{8})\b', text)
            for m in matches:
                # Filtrer: les CPV commencent généralement par des codes de catégories connues
                # 72xxxxxx = Informatique, 48xxxxxx = Télécoms, etc.
                if m.startswith(('72', '48', '71', '79', '38', '30', '32', '33', '50', '63', '66', '92')):
                    codes.add(m)

        # Retourner liste dédupliquée, max 10 codes
        return list(codes)[:10]

    def _extract_duration_months(self) -> int | None:
        """Extrait la durée du marché en mois à partir du texte.

        Patterns supportés:
        - "Durée du marché : 24 mois"
        - "pour une durée de 36 mois"
        - "Durée en mois : 12"
        - "24 mois" (contexte durée)
        - Conversion années: "2 ans" → 24 mois

        Returns:
            Nombre de mois (1-120) ou None si non déterminable
        """
        text = self.text()

        # Pattern 1: "Durée du marché : X mois"
        m = re.search(r'Dur[ée]e(?:\s+du\s+march[ée])?\s*[:\-]?\s*(\d+)\s*mois', text, re.I)
        if m:
            months = int(m.group(1))
            if 1 <= months <= 120:
                return months

        # Pattern 2: "Durée en mois : X"
        m = re.search(r'Dur[ée]e\s+en\s+mois\s*[:\-]?\s*(\d+)', text, re.I)
        if m:
            months = int(m.group(1))
            if 1 <= months <= 120:
                return months

        # Pattern 3: "pour une durée de X mois"
        m = re.search(r'pour\s+une\s+dur[ée]e\s+de\s*(\d+)\s*mois', text, re.I)
        if m:
            months = int(m.group(1))
            if 1 <= months <= 120:
                return months

        # Pattern 4: Conversion années en mois
        m = re.search(r'Dur[ée]e.*?((\d+)\s*ans?)', text, re.I)
        if m:
            years = int(m.group(2))
            months = years * 12
            if 1 <= months <= 120:
                return months

        # Pattern 5: Recherche générale "X mois" proche de mots-clés durée
        m = re.search(r'dur[ée]e.*?\b(\d{1,3})\s*mois\b', text, re.I)
        if m:
            months = int(m.group(1))
            if 1 <= months <= 120:
                return months

        return None
