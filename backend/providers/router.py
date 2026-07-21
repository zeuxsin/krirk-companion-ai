"""
backend/providers/router.py
Roteia tarefas para o provider correto com fallback automático.

Hierarquia padrão: nvidia -> google -> cerebras -> ollama
Cada tarefa tem modelos configurados por provider.
"""
import asyncio
import os
import time
from typing import AsyncGenerator

from .base import BaseProvider
from .openai_compat import make_openai_providers
from .ollama_prov import OllamaProvider


# ── Mapeamento tarefa -> provider -> model ─────────────────────────────────────

TASK_MODELS: dict[str, dict[str, str]] = {
    "nvidia": {
        # llama-3.3-70b e outros meta/llama estão com timeout crônico no free tier;
        # mistral-small-4-119b (MoE) responde em ~3s e é o único NVIDIA confiável (2026-07)
        "chat":   "mistralai/mistral-small-4-119b-2603",
        "tools":  "mistralai/mistral-small-4-119b-2603",
        "route":  "mistralai/mistral-small-4-119b-2603",  # fallback do roteamento
        "code":   "nvidia/llama-3.3-nemotron-super-49b-v1",
        "ocr":    "meta/llama-3.2-11b-vision-instruct",   # phi-4-multimodal foi removido (410)
        "vision": "meta/llama-3.2-11b-vision-instruct",
        "embed":  "nvidia/nv-embedqa-e5-v5",
        "safety": "meta/llama-guard-4-12b",
    },
    "google": {
        # Aliases "latest": os IDs fixos 2.5 deram 404 p/ contas novas (2026-07);
        # os aliases seguem o modelo free-tier atual da conta automaticamente
        "chat":   "gemini-flash-latest",
        "tools":  "gemini-flash-lite-latest",
        "route":  "gemini-flash-lite-latest",
        "code":   "gemini-flash-latest",
        "ocr":    "gemini-flash-latest",
        "vision": "gemini-flash-latest",
    },
    "cerebras": {
        # Catálogo 2026-07: gpt-oss-120b, gemma-4-31b, zai-glm-4.7 (llama3.1 removidos)
        "chat":   "gpt-oss-120b",
        "tools":  "gpt-oss-120b",
        # roteamento de ferramentas: gemma-4-31b é rápido (não-reasoning) e mais
        # confiável que o mistral p/ decidir a tool. Limite 5 req/min é suficiente
        # porque SÓ a decisão de rota usa "route" (1x/msg) — extração fica em "tools"
        "route":  "gemma-4-31b",
        "code":   "zai-glm-4.7",
    },
    "groq": {
        # Inferência rápida — ótimo p/ route/chat. IDs conferir em console.groq.com/docs/models
        "chat":   "llama-3.3-70b-versatile",
        "tools":  "llama-3.3-70b-versatile",
        "route":  "llama-3.3-70b-versatile",
        "code":   "openai/gpt-oss-120b",
    },
    "cohere": {
        # Trial 20 req/min. Endpoint compat: model = ID nativo da Cohere
        "chat":   "command-a-03-2025",
        "tools":  "command-r7b-12-2024",
        "route":  "command-r7b-12-2024",
        "code":   "command-a-03-2025",
    },
    "mistral": {
        # Plano free "Experiment" (~1 RPS). Codestral p/ código.
        "chat":   "mistral-medium-latest",
        "tools":  "mistral-small-latest",
        "route":  "mistral-small-latest",
        "code":   "codestral-latest",
        "vision": "pixtral-large-latest",
        "ocr":    "pixtral-large-latest",
    },
    "openrouter": {
        # Catálogo :free validado 2026-07 (gemma-4-31b:free vive em 429 upstream;
        # llama/deepseek :free sairam). Conferir em openrouter.ai/models se falhar.
        "chat":   "nvidia/nemotron-3-super-120b-a12b:free",
        "tools":  "nvidia/nemotron-3-super-120b-a12b:free",
        "route":  "nvidia/nemotron-3-super-120b-a12b:free",
        "code":   "poolside/laguna-m.1:free",
    },
    "ollama": {
        "chat":   "gemma3:4b",
        "tools":  "qwen2.5-coder:7b",
        "route":  "qwen2.5-coder:7b",
        "code":   "qwen2.5-coder:7b",
        "embed":  "nomic-embed-text",
        "vision": "gemma3:4b",   # gemma3 é multimodal — fallback local de visão
        "ocr":    "gemma3:4b",
    },
}

# Ordem de fallback por tarefa. Cada "<name>2" (2ª chave) vem logo após o
# primário — quando a 1ª chave estoura (429 → circuit breaker pausa 65s), a 2ª
# assume, dobrando o limite antes de passar pro próximo provedor. Provedores
# sem chave configurada são pulados automaticamente (is_available).
TASK_FALLBACK: dict[str, list[str]] = {
    "chat":   ["nvidia", "groq", "groq2", "mistral", "mistral2", "cohere", "cohere2",
               "google", "google2", "cerebras", "cerebras2", "openrouter", "openrouter2", "ollama"],
    "tools":  ["nvidia", "groq", "groq2", "cerebras", "cerebras2", "google", "google2",
               "mistral", "mistral2", "cohere", "cohere2", "openrouter", "openrouter2", "ollama"],
    # decisão de rota: Cerebras (gemma-4-31b) primeiro — validado como o mais
    # confiável; Groq (rápido) e Gemini logo atrás; resto como rede de segurança
    "route":  ["cerebras", "cerebras2", "groq", "groq2", "google", "google2", "nvidia",
               "mistral", "mistral2", "cohere", "cohere2", "openrouter", "openrouter2", "ollama"],
    # código: Groq (gpt-oss rápido) e Codestral da Mistral primeiro
    "code":   ["groq", "groq2", "mistral", "mistral2", "cerebras", "cerebras2", "nvidia",
               "openrouter", "openrouter2", "cohere", "cohere2", "ollama"],
    "embed":  ["nvidia", "ollama"],
    "ocr":    ["nvidia", "google", "google2", "mistral", "mistral2", "ollama"],
    "vision": ["nvidia", "google", "google2", "mistral", "mistral2", "ollama"],
    "safety": ["nvidia"],
}

# Erros que ativam fallback para o próximo provider
# 403 (sem acesso ao modelo) e 410 (modelo removido) também caem para o próximo.
# 402 (payment required): conta sem free tier ativo (visto no cerebras2) —
# sem ele na lista a exceção PROPAGARIA e derrubaria a requisição inteira.
_RETRIABLE_CODES = (400, 402, 403, 404, 410, 422, 429, 500, 502, 503, 504)


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
        or "gone" in msg
        or "unavailable" in msg
    )


class ProviderRouter:
    # Circuit breaker: após N falhas consecutivas, o provider é pulado por um tempo.
    # Evita desperdiçar ~10s de timeout por chamada quando um provider está fora.
    BREAKER_THRESHOLD = 2
    BREAKER_COOLDOWN = 180.0       # segundos (falha "dura": modelo fora/timeout)
    RATE_LIMIT_COOLDOWN = 65.0     # rate limit (429) recupera na virada do minuto

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
        self._failures: dict[str, int] = {}
        self._skip_until: dict[str, float] = {}

    # ── Circuit breaker ───────────────────────────────────────────────────────

    def _record_failure(self, name: str, exc: Exception | None = None) -> None:
        self._failures[name] = self._failures.get(name, 0) + 1
        if self._failures[name] >= self.BREAKER_THRESHOLD:
            # Rate limit (429) não é o provider quebrado — recupera rápido; cooldown curto
            rate = exc is not None and (
                getattr(exc, "status_code", None) == 429
                or "429" in str(exc) or "rate" in str(exc).lower()
                or "too many requests" in str(exc).lower()
            )
            cooldown = self.RATE_LIMIT_COOLDOWN if rate else self.BREAKER_COOLDOWN
            self._skip_until[name] = time.monotonic() + cooldown
            print(f"[KRIRK][router] Circuit breaker: {name} pausado por {cooldown:.0f}s"
                  + (" (rate limit)" if rate else ""))

    def _record_success(self, name: str) -> None:
        self._failures.pop(name, None)
        self._skip_until.pop(name, None)

    def _is_skipped(self, name: str) -> bool:
        until = self._skip_until.get(name)
        if until is None:
            return False
        if time.monotonic() >= until:
            # Cooldown expirou — dá nova chance
            self._skip_until.pop(name, None)
            self._failures.pop(name, None)
            return False
        return True

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
        # Circuit breaker filtra os pausados — mas nunca deixa a lista vazia
        active = [(n, p) for n, p in result if not self._is_skipped(n)]
        return active if active else result

    async def stream(
        self,
        task: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        top_p: float | None = None,
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
                    temperature=temperature, max_tokens=max_tokens, top_p=top_p,
                ):
                    yield token
                self._record_success(name)
                return  # sucesso
            except Exception as e:
                last_err = e
                if _is_retriable(e):
                    self._record_failure(name, e)
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
                result = await provider.chat(
                    messages, model=model,
                    temperature=temperature, max_tokens=max_tokens,
                )
                self._record_success(name)
                return result
            except Exception as e:
                last_err = e
                if _is_retriable(e):
                    self._record_failure(name, e)
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

    # Provedores OpenAI-compatíveis (nvidia/google/cerebras/groq/cohere/mistral/
    # openrouter + as 2ªs chaves "<name>2" quando presentes) + Ollama local
    providers: dict[str, BaseProvider] = make_openai_providers()
    providers["ollama"] = OllamaProvider(base_url=ollama_url)

    # Log quais providers estão disponíveis (com chave)
    avail = [n for n, p in providers.items() if p.is_available()]
    print(f"[KRIRK][router] Providers disponíveis: {avail}")

    # deepcopy: não mutar o TASK_MODELS global (senão o config/2ª-chave vaza entre testes)
    import copy
    task_models = copy.deepcopy(TASK_MODELS)

    # Sobrescreve/define modelos com valores do config (aceita provedores novos)
    providers_cfg = config.get("providers", {})
    for pname, pcfg in providers_cfg.items():
        if isinstance(pcfg, dict) and "models" in pcfg:
            task_models.setdefault(pname, {}).update(pcfg["models"])

    # Provedores "2" (2ª chave) herdam os modelos do primário
    for pname in providers:
        if pname.endswith("2") and pname[:-1] in task_models:
            task_models[pname] = dict(task_models[pname[:-1]])

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
