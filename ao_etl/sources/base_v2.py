"""Classe de base pour les extracteurs de source - Version 2 avec architecture candidate/trace."""

from __future__ import annotations

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
