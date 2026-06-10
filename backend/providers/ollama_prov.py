"""
backend/providers/ollama_prov.py
Provider Ollama (local) — sempre disponível como último fallback.
"""
from typing import AsyncGenerator
from .base import BaseProvider


class OllamaProvider(BaseProvider):
    name = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434"):
        self._base_url = base_url

    def is_available(self) -> bool:
        return True  # sempre disponível se o Ollama está rodando

    def _client(self):
        import ollama
        return ollama.AsyncClient(host=self._base_url)

    async def stream_chat(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        client = self._client()
        async for chunk in await client.chat(
            model=model,
            messages=messages,
            stream=True,
            options={"temperature": temperature, "num_predict": max_tokens},
        ):
            content = chunk.get("message", {}).get("content", "")
            if content:
                yield content

    async def chat(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 512,
    ) -> str:
        client = self._client()
        resp = await client.chat(
            model=model,
            messages=messages,
            stream=False,
            options={"temperature": temperature, "num_predict": max_tokens},
        )
        return resp.get("message", {}).get("content", "")

    async def embed(self, text: str, model: str) -> list[float]:
        client = self._client()
        resp = await client.embeddings(model=model, prompt=text)
        return resp.get("embedding", [])
