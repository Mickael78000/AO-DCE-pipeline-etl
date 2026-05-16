"""Abstraction backend LLM — DÉSACTIVÉ (mode pipeline déterministe).

POLITIQUE PROJET : Le LLM est totalement désactivé sur l'ensemble du pipeline.
Toute tentative d'appel LLM lève LLMDisabledError avec un message explicite.

Pour réactiver : supprimer le bloc de garde-fou dans build_backend() et dans
les méthodes call() de chaque classe, après stabilisation complète du pipeline
déterministe et validation documentée des cas d'usage.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

log = logging.getLogger(__name__)


# =============================================================================
# GARDE-FOU GLOBAL — NE PAS SUPPRIMER SANS DÉCISION EXPLICITE
# =============================================================================

class LLMDisabledError(RuntimeError):
    """Levée dès qu'une tentative d'appel LLM est détectée.

    Le LLM est désactivé sur l'ensemble du pipeline (mode déterministe).
    Toute extraction, transformation et colonisation du CSV final doit
    être réalisée par parsing déterministe et règles Python explicites.

    Pour réactiver le LLM, modifier la politique dans ao_etl/llm/backend.py
    après validation documentée.
    """


_DISABLED_MSG = (
    "APPEL LLM INTERDIT — pipeline en mode déterministe. "
    "Aucun modèle ne doit être appelé pour aucune colonne du CSV final. "
    "Extraction = parsing HTML/TXT. Valeur incertaine = \"-\". "
    "Pour réactiver : voir ao_etl/llm/backend.py (LLMDisabledError)."
)


# =============================================================================
# Interface conservée pour ne pas casser les imports existants
# =============================================================================

class LLMBackend(ABC):
    """Interface commune — neutralisée, lève LLMDisabledError à chaque appel."""

    @abstractmethod
    def call(self, system_prompt: str, user_prompt: str) -> str:
        """Désactivé — lève LLMDisabledError."""

    def call_json(self, system_prompt: str, user_prompt: str) -> dict:
        """Désactivé — lève LLMDisabledError."""
        raise LLMDisabledError(_DISABLED_MSG)


class OpenAIBackend(LLMBackend):
    def __init__(self, *args, **kwargs):
        raise LLMDisabledError(_DISABLED_MSG)

    def call(self, system_prompt: str, user_prompt: str) -> str:
        raise LLMDisabledError(_DISABLED_MSG)


class AnthropicBackend(LLMBackend):
    def __init__(self, *args, **kwargs):
        raise LLMDisabledError(_DISABLED_MSG)

    def call(self, system_prompt: str, user_prompt: str) -> str:
        raise LLMDisabledError(_DISABLED_MSG)


class OllamaBackend(LLMBackend):
    def __init__(self, *args, **kwargs):
        raise LLMDisabledError(_DISABLED_MSG)

    def call(self, system_prompt: str, user_prompt: str) -> str:
        raise LLMDisabledError(_DISABLED_MSG)


def build_backend(
    backend: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> LLMBackend:
    """DÉSACTIVÉ — lève LLMDisabledError immédiatement.

    Le LLM est interdit sur l'ensemble du pipeline (mode déterministe).
    """
    raise LLMDisabledError(_DISABLED_MSG)
