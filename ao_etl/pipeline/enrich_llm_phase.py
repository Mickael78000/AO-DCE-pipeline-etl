"""
Phase d'enrichissement complémentaire via LLM — DÉSACTIVÉE.

POLITIQUE PROJET : Le LLM est interdit sur l'ensemble du pipeline.
run_enrich_llm_phase() retourne immédiatement sans aucun appel modèle.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from ao_etl.llm.backend import LLMDisabledError

log = logging.getLogger(__name__)


@dataclass
class EnrichLLMResult:
    """Résultat de la phase d'enrichissement LLM."""
    total_rows: int
    llm_enriched_rows: int
    errors: List[str] = field(default_factory=list)
    cpv_completed: int = 0
    montants_completed: int = 0
    duree_completed: int = 0
    lots_completed: int = 0


@dataclass
class EnrichLLMConfig:
    """Configuration pour la phase d'enrichissement LLM."""
    enabled: bool = True
    output_csv: Optional[Path] = None
    backend: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    max_rows: Optional[int] = None  # Pour les tests, limiter le nombre de lignes



def run_enrich_llm_phase(
    input_csv: Path,
    html_dir: Path,
    output_csv: Path,
    config: EnrichLLMConfig,
) -> Dict[str, Any]:
    """
    DÉSACTIVÉE — Le LLM est interdit sur l'ensemble du pipeline.

    Retourne immédiatement sans aucun appel modèle.
    Les champs non extraits par le parsing déterministe restent à "-".
    """
    raise LLMDisabledError(
        "APPEL LLM INTERDIT — run_enrich_llm_phase() est désactivée. "
        "Enrichissement uniquement par parsing déterministe HTML/TXT. "
        "Pour réactiver : voir ao_etl/llm/backend.py (LLMDisabledError)."
    )


def print_enrich_llm_summary(stats: Dict[str, Any]) -> None:
    """Affiche le résumé de la phase d'enrichissement LLM."""
    print()
    print("=" * 70)
    print("ENRICHISSEMENT COMPLÉMENTAIRE LLM - Résumé")
    print("=" * 70)
    print(f"Lignes traitées:      {stats.get('total_rows', 0)}")
    print(f"Lignes complétées:    {stats.get('llm_enriched_rows', 0)}")
    print(f"CPV complétés:        {stats.get('cpv_completed', 0)}")
    print(f"Montants complétés:   {stats.get('montants_completed', 0)}")
    print(f"Durées complétées:    {stats.get('duree_completed', 0)}")
    print(f"Lots complétés:       {stats.get('lots_completed', 0)}")
    if stats.get('errors'):
        print(f"Erreurs:              {len(stats['errors'])}")
    print(f"Fichier sortie:       {stats.get('output_csv', 'N/A')}")
    print("=" * 70)
