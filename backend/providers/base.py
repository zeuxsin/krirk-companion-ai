"""
backend/providers/base.py
Interface comum para todos os providers de LLM.
"""
from abc import ABC, abstractmethod
from typing import AsyncGenerator


class BaseProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """Streama tokens de resposta de chat."""
        ...

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 512,
    ) -> str:
        """Retorna resposta completa (sem streaming). Usado para tool routing."""
        ...

    async def embed(self, text: str, model: str) -> list[float]:
        """Retorna vetor de embedding. Implementar apenas se suportado."""
        raise NotImplementedError(f"{self.name} não suporta embeddings")

    def is_available(self) -> bool:
        """True se o provider está configurado e pronto para uso."""
        return True
