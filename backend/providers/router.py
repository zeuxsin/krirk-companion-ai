"""
backend/providers/router.py
Roteia tarefas para o provider correto com fallback automático.

Hierarquia padrão: nvidia -> google -> cerebras -> ollama
Cada tarefa tem modelos configurados por provider.
"""
import asyncio
import os
from typing import AsyncGenerator

from .base import BaseProvider
from .openai_compat import make_nvidia, make_cerebras, make_google
from .ollama_prov import OllamaProvider


# ── Mapeamento tarefa -> provider -> model ─────────────────────────────────────

TASK_MODELS: dict[str, dict[str, str]] = {
    "nvidia": {
        "chat":   "meta/llama-3.3-70b-instruct",
        "tools":  "mistralai/mistral-small-4-119b-2603",
        "code":   "nvidia/llama-3.3-nemotron-super-49b-v1",
        "ocr":    "microsoft/phi-4-multimodal-instruct",
        "vision": "meta/llama-3.2-11b-vision-instruct",
        "embed":  "nvidia/nv-embedqa-e5-v5",
        "safety": "meta/llama-guard-4-12b",
    },
    "google": {
        "chat":   "gemma-4-31b-it",
        "tools":  "gemma-4-31b-it",
        "code":   "gemma-4-31b-it",
    },
    "cerebras": {
        "chat":   "llama3.1-70b",
        "tools":  "llama3.1-8b",
        "code":   "llama3.1-70b",
    },
    "ollama": {
        "chat":   "gemma3:4b",
        "tools":  "qwen2.5-coder:7b",
        "code":   "qwen2.5-coder:7b",
        "embed":  "nomic-embed-text",
        "vision": "gemma3:4b",   # gemma3 é multimodal — fallback local de visão
        "ocr":    "gemma3:4b",
    },
}

# Ordem de fallback por tarefa
TASK_FALLBACK: dict[str, list[str]] = {
    "chat":   ["nvidia", "google", "cerebras", "ollama"],
    "tools":  ["nvidia", "ollama"],
    "code":   ["nvidia", "cerebras", "ollama"],
    "embed":  ["nvidia", "ollama"],
    "ocr":    ["nvidia", "ollama"],
    "vision": ["nvidia", "ollama"],
    "safety": ["nvidia"],
}

# Erros que ativam fallback para o próximo provider
_RETRIABLE_CODES = (400, 404, 422, 429, 500, 502, 503, 504)


def _is_retriable(exc: Exception) -> bool:
    # Timeouts (httpx ou asyncio) -> sempre cai para próximo provider
    exc_type = type(exc).__name__
    if exc_type in ("TimeoutException", "ReadTimeout", "ConnectTimeout",
                    "TimeoutError", "APITimeoutError", "APIConnectionError"):
        return True
    # Erros do SDK openai com status code
    if exc_type in ("NotFoundError", "RateLimitError", "InternalServerError",
                    "APIStatusError", "UnprocessableEntityError", "BadRequestError"):
        if exc_type in ("NotFoundError", "RateLimitError"):
            return True
        status = getattr(exc, "status_code", None)
        if status in _RETRIABLE_CODES:
            return True
    # Fallback: inspeciona a mensagem de texto
    msg = str(exc).lower()
    return (
        any(str(c) in msg for c in _RETRIABLE_CODES)
        or "rate" in msg
        or "limit" in msg
        or "timeout" in msg
        or "timed out" in msg
        or "not found" in msg
        or "notfounderror" in msg
        or "does not exist" in msg
        or "invalid model" in msg
        or "no such model" in msg
    )


class ProviderRouter:
    def __init__(
        self,
        providers: dict[str, BaseProvider],
        task_models: dict[str, dict[str, str]] | None = None,
        task_fallback: dict[str, list[str]] | None = None,
        ollama_base_url: str = "http://localhost:11434",
    ):
        self._providers = providers
        self._task_models = task_models or TASK_MODELS
        self._task_fallback = task_fallback or TASK_FALLBACK

    def _get_model(self, provider_name: str, task: str) -> str | None:
        return self._task_models.get(provider_name, {}).get(task)

    def _ordered_providers(self, task: str) -> list[tuple[str, BaseProvider]]:
        """Retorna lista de (name, provider) disponíveis na ordem de fallback."""
        order = self._task_fallback.get(task, ["ollama"])
        result = []
        for name in order:
            p = self._providers.get(name)
            if p and p.is_available() and self._get_model(name, task):
                result.append((name, p))
        return result

    async def stream(
        self,
        task: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """Streama tokens tentando providers em ordem de fallback."""
        ordered = self._ordered_providers(task)
        if not ordered:
            yield "[Erro: nenhum provider disponível para a tarefa]"
            return

        last_err = None
        for name, provider in ordered:
            model = self._get_model(name, task)
            try:
                print(f"[KRIRK][router] {task} -> {name}/{model}")
                async for token in provider.stream_chat(
                    messages, model=model,
                    temperature=temperature, max_tokens=max_tokens,
                ):
                    yield token
                return  # sucesso
            except Exception as e:
                last_err = e
                if _is_retriable(e):
                    print(f"[KRIRK][router] {name} falhou ({e}), tentando próximo...")
                    continue
                raise  # erro não-retriable -> propaga

        yield f"[Todos os providers falharam: {last_err}]"

    async def complete(
        self,
        task: str,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 512,
    ) -> str:
        """Retorna resposta completa (para tool routing — não streama)."""
        ordered = self._ordered_providers(task)
        if not ordered:
            return ""

        last_err = None
        for name, provider in ordered:
            model = self._get_model(name, task)
            try:
                print(f"[KRIRK][router] complete/{task} -> {name}/{model}")
                return await provider.chat(
                    messages, model=model,
                    temperature=temperature, max_tokens=max_tokens,
                )
            except Exception as e:
                last_err = e
                if _is_retriable(e):
                    print(f"[KRIRK][router] {name} falhou ({e}), tentando próximo...")
                    continue
                raise

        return ""

    async def embed(self, text: str) -> list[float]:
        """Gera embedding com fallback."""
        ordered = self._ordered_providers("embed")
        for name, provider in ordered:
            model = self._get_model(name, "embed")
            try:
                return await provider.embed(text, model=model)
            except Exception as e:
                print(f"[KRIRK][router] embed/{name} falhou: {e}")
                continue
        return []


def build_router(config: dict) -> ProviderRouter:
    """Instancia o router a partir do config + variáveis de ambiente."""
    ollama_url = config.get("ollama", {}).get("base_url", "http://localhost:11434")

    providers: dict[str, BaseProvider] = {
        "nvidia":   make_nvidia(),
        "google":   make_google(),
        "cerebras": make_cerebras(),
        "ollama":   OllamaProvider(base_url=ollama_url),
    }

    # Log quais providers estão disponíveis
    avail = [n for n, p in providers.items() if p.is_available()]
    print(f"[KRIRK][router] Providers disponíveis: {avail}")

    # Sobrescreve modelos com valores do config se definidos
    providers_cfg = config.get("providers", {})
    task_models = dict(TASK_MODELS)  # cópia
    for pname, pcfg in providers_cfg.items():
        if "models" in pcfg and pname in task_models:
            task_models[pname].update(pcfg["models"])

    # Sobrescreve modelos Ollama com os do config principal (retrocompatibilidade)
    ollama_cfg = config.get("ollama", {})
    if "model" in ollama_cfg:
        task_models["ollama"]["chat"] = ollama_cfg["model"]
    tool_cfg = config.get("tools", {})
    if "tool_model" in tool_cfg:
        task_models["ollama"]["tools"] = tool_cfg["tool_model"]
        task_models["ollama"]["code"] = tool_cfg["tool_model"]

    return ProviderRouter(
        providers=providers,
        task_models=task_models,
        ollama_base_url=ollama_url,
    )
