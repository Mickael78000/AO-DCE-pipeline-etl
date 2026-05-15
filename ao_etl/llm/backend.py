"""Abstraction backend LLM.

Supporte trois backends configurables via la variable d'environnement
AO_LLM_BACKEND : openai | anthropic | ollama

Configuration par variables d'environnement :
  AO_LLM_BACKEND        = openai | anthropic | ollama  (défaut: openai)
  AO_LLM_MODEL          = nom du modèle
  AO_LLM_API_KEY        = clé API (ou OPENAI_API_KEY / ANTHROPIC_API_KEY)
  AO_LLM_BASE_URL       = URL de base pour Ollama (défaut: http://localhost:11434)
  AO_LLM_TIMEOUT        = timeout en secondes (défaut: 60)
  AO_LLM_MAX_TOKENS     = max tokens de sortie (défaut: 4096)
  AO_LLM_TEMPERATURE    = température (défaut: 0.0)
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Optional

log = logging.getLogger(__name__)

_DEFAULTS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-latest",
    "ollama": "llama3.1",
}


class LLMBackend(ABC):
    """Interface commune pour tous les backends LLM."""

    @abstractmethod
    def call(self, system_prompt: str, user_prompt: str) -> str:
        """Appelle le LLM et retourne la réponse brute (string)."""

    def call_json(self, system_prompt: str, user_prompt: str) -> dict:
        """Appelle le LLM et parse la réponse JSON. Lève ValueError si invalide."""
        raw = self.call(system_prompt, user_prompt)
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(
                l for l in lines
                if not l.strip().startswith("```")
            ).strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM n'a pas retourné un JSON valide: {e}\nRéponse: {raw[:200]}") from e


class OpenAIBackend(LLMBackend):
    def __init__(self, model: str, api_key: str, timeout: int,
                 max_tokens: int, temperature: float):
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError("pip install openai requis pour le backend OpenAI") from e
        self._client = OpenAI(api_key=api_key, timeout=timeout)
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature

    def call(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""


class AnthropicBackend(LLMBackend):
    def __init__(self, model: str, api_key: str, timeout: int,
                 max_tokens: int, temperature: float):
        try:
            import anthropic
        except ImportError as e:
            raise ImportError("pip install anthropic requis pour le backend Anthropic") from e
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature

    def call(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text if response.content else ""


class OllamaBackend(LLMBackend):
    def __init__(self, model: str, base_url: str, timeout: int,
                 max_tokens: int, temperature: float):
        try:
            import requests
        except ImportError as e:
            raise ImportError("pip install requests requis pour le backend Ollama") from e
        self._requests = requests
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_tokens = max_tokens
        self._temperature = temperature

    def call(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": self._temperature,
                "num_predict": self._max_tokens,
            },
            "format": "json",
        }
        resp = self._requests.post(
            f"{self._base_url}/api/chat",
            json=payload,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")


def build_backend(
    backend: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> LLMBackend:
    """Construit le backend LLM selon la configuration d'environnement.

    Args:
        backend: Force un backend (openai|anthropic|ollama). Par défaut: AO_LLM_BACKEND.
        model:   Force un modèle. Par défaut: AO_LLM_MODEL ou défaut du backend.
        api_key: Force une clé API. Par défaut: AO_LLM_API_KEY.
    """
    backend = (backend or os.environ.get("AO_LLM_BACKEND", "openai")).lower()
    model = model or os.environ.get("AO_LLM_MODEL", _DEFAULTS.get(backend, ""))
    timeout = int(os.environ.get("AO_LLM_TIMEOUT", "60"))
    max_tokens = int(os.environ.get("AO_LLM_MAX_TOKENS", "4096"))
    temperature = float(os.environ.get("AO_LLM_TEMPERATURE", "0.0"))

    if backend == "openai":
        key = api_key or os.environ.get("AO_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise EnvironmentError(
                "Clé API OpenAI manquante. Définissez OPENAI_API_KEY ou AO_LLM_API_KEY."
            )
        return OpenAIBackend(model, key, timeout, max_tokens, temperature)

    if backend == "anthropic":
        key = api_key or os.environ.get("AO_LLM_API_KEY") or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise EnvironmentError(
                "Clé API Anthropic manquante. Définissez ANTHROPIC_API_KEY ou AO_LLM_API_KEY."
            )
        return AnthropicBackend(model, key, timeout, max_tokens, temperature)

    if backend == "ollama":
        base_url = os.environ.get("AO_LLM_BASE_URL", "http://localhost:11434")
        return OllamaBackend(model, base_url, timeout, max_tokens, temperature)

    raise ValueError(
        f"Backend LLM inconnu: '{backend}'. Valeurs autorisées: openai, anthropic, ollama"
    )
