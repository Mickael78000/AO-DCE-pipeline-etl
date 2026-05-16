"""Module de validation des données avec Pydantic."""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, validator
import re


class MarketDataValidated(BaseModel):
    """Modèle de validation pour les données de marché."""
    
    reference: str = Field(..., min_length=1, max_length=100)
    titre: str = Field(..., min_length=5, max_length=500)
    acheteur: str = Field(..., min_length=2, max_length=200)
    localisation: str = Field(..., min_length=2, max_length=100)
    date_limite: Optional[str] = None
    estimation: Optional[float] = Field(None, ge=0)
    url_source: Optional[str] = Field(None, regex=r'^https?://')
    
    # Champs enrichis
    cpv_principal: Optional[str] = Field(None, regex=r'^\d{8}$')
    cpv_supplementaires: List[str] = Field(default_factory=list)
    nombre_lots: int = Field(0, ge=0)
    
    @validator('cpv_principal')
    def validate_cpv(cls, v):
        if v and not re.match(r'^\d{8}$', v):
            raise ValueError('CPV doit être un code à 8 chiffres')
        return v
    
    @validator('date_limite')
    def validate_date(cls, v):
        if v and not re.match(r'\d{2}/\d{2}/\d{4}', v):
            raise ValueError('Date doit être au format JJ/MM/AAAA')
        return v


class PipelineConfig(BaseModel):
    """Configuration validée du pipeline."""
    
    html_dir: str = Field(..., min_length=1)
    input_csv: str = Field(..., min_length=1)
    output_csv: str = Field(..., min_length=1)
    verbose: bool = True
    enable_enrich_descriptif: bool = False
    enable_consolidation: bool = False
    
    @validator('html_dir', 'input_csv', 'output_csv')
    def validate_paths(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Le chemin ne peut pas être vide')
        return v


def validate_csv_row(row: dict) -> tuple[bool, Optional[str]]:
    """Valide une ligne CSV et retourne (is_valid, error_message)."""
    try:
        # Vérification des champs obligatoires
        required = ['Référence', 'Intitulé synthétique', 'Acheteur_clean']
        for field in required:
            if not row.get(field) or str(row[field]).strip() == '':
                return False, f"Champ obligatoire manquant: {field}"
        
        # Validation de la référence
        ref = str(row.get('Référence', ''))
        if len(ref) < 3:
            return False, "Référence trop courte (< 3 caractères)"
        
        return True, None
        
    except Exception as e:
        return False, f"Erreur de validation: {e}"
