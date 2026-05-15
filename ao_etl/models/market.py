"""Modèles de données pour les marchés publics."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Optional


class SourceType(Enum):
    """Type de source du marché."""
    FRANCE_MARCHES = "FRANCE_MARCHES"
    MARCHES_ONLINE = "MARCHES_ONLINE"
    PLACE_NUMERIC = "PLACE_NUMERIC"
    BOAMP_XML = "BOAMP_XML"
    STANDARD = "STANDARD"
    UNKNOWN = "UNKNOWN"


class ExtractionStatus(Enum):
    """Statut de l'extraction."""
    SUCCESS = auto()
    PARTIAL = auto()
    FAILED = auto()
    ALIAS = auto()


@dataclass
class MarketData:
    """Données extraites d'un marché public.
    
    Cette classe représente toutes les données métier extraites d'un fichier HTML
    d'appel d'offres, avec traçabilité de la source et qualité de l'extraction.
    """
    # Identification
    filename: str
    source_type: SourceType = SourceType.UNKNOWN
    
    # Données métier (champs obligatoires)
    title: str = ""
    reference: str = ""
    buyer: str = ""
    
    # Données métier (champs optionnels)
    cpv: list[str] = field(default_factory=list)
    url_source: str = ""
    location: str = ""
    
    # Classification acheteur
    fonction_publique: str = ""  # etat, collectivite, hospitaliere, etc.
    
    # Caractéristiques du marché
    procedure_type: str = ""  # Ouverte, Restreinte, Négociée, etc.
    contract_nature: str = ""  # Services, Fournitures, Travaux
    
    # Dates et durée
    date_publication: Optional[datetime] = None
    date_limite: Optional[datetime] = None
    duree_mois: Optional[int] = None
    
    # Estimation
    estimation_eur: Optional[float] = None
    
    # Métadonnées d'extraction
    status: ExtractionStatus = ExtractionStatus.PARTIAL
    extraction_notes: list[str] = field(default_factory=list)
    
    # Gestion des alias
    is_alias: bool = False
    alias_of: Optional[str] = None
    
    def is_complete(self) -> bool:
        """Vérifie si les champs critiques sont extraits."""
        return all([
            self.title.strip(),
            self.reference.strip(),
            self.buyer.strip(),
        ])
    
    def completeness_score(self) -> float:
        """Calcule le taux de complétude (0.0 à 1.0)."""
        fields = [self.title, self.reference, self.buyer]
        filled = sum(1 for f in fields if f.strip())
        return filled / len(fields)
    
    def add_note(self, note: str) -> None:
        """Ajoute une note d'extraction avec timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.extraction_notes.append(f"[{timestamp}] {note}")
