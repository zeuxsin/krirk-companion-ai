"""
backend/providers/openai_compat.py
Provider genérico para APIs compatíveis com OpenAI (NVIDIA NIM, Cerebras, Google).
"""
import os
from typing import AsyncGenerator
from .base import BaseProvider


def _to_openai_messages(messages: list[dict]) -> list[dict]:
    """
    Converte mensagens com chave 'images' (lista de base64) para o formato
    multimodal do protocolo OpenAI (content como lista de blocos text/image_url).
    Mensagens sem imagens passam intactas.
    """
    out = []
    for m in messages:
        imgs = m.get("images")
        if imgs:
            content: list[dict] = [{"type": "text", "text": m.get("content", "")}]
            for b64 in imgs:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                })
            out.append({"role": m["role"], "content": content})
        else:
            out.append({"role": m["role"], "content": m.get("content", "")})
    return out


class OpenAICompatProvider(BaseProvider):
    """
    Funciona com qualquer API que implemente o protocolo OpenAI Chat Completions.
    NVIDIA NIM:  https://integrate.api.nvidia.com/v1
    Cerebras:    https://api.cerebras.ai/v1
    Google:      https://generativelanguage.googleapis.com/v1beta/openai/
    """

    def __init__(self, name: str, base_url: str, api_key: str):
        self.name = name
        self._base_url = base_url
        self._api_key = api_key

    def is_available(self) -> bool:
        return bool(self._api_key and self._api_key.strip())

    def _client(self, timeout: float = 10.0):
        import ssl
        import httpx
        from openai import AsyncOpenAI

        # Usa o certificate store nativo do SO (Windows/Linux/macOS)
        try:
            import truststore
            ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        except ImportError:
            ctx = ssl.create_default_context()

        # timeout precisa estar em AMBOS: httpx (conexão) e AsyncOpenAI (SDK)
        httpx_timeout = httpx.Timeout(timeout, connect=5.0)
        return AsyncOpenAI(
            base_url=self._base_url,
            api_key=self._api_key,
            timeout=timeout,          # timeout do SDK openai (cobre retry logic)
            max_retries=0,            # sem retry — queremos cair para próximo provider
            http_client=httpx.AsyncClient(
                timeout=httpx_timeout,
                verify=ctx,
            ),
        )

    async def stream_chat(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        top_p: float | None = None,
    ) -> AsyncGenerator[str, None]:
        # Upload de imagens base64 é pesado — timeout maior para visão
        has_images = any(m.get("images") for m in messages)
        client = self._client(timeout=45.0 if has_images else 10.0)
        extra = {"top_p": top_p} if top_p is not None else {}
        stream = await client.chat.completions.create(
            model=model,
            messages=_to_openai_messages(messages),
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **extra,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta

    async def chat(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 512,
        top_p: float | None = None,
    ) -> str:
        has_images = any(m.get("images") for m in messages)
        client = self._client(timeout=45.0 if has_images else 10.0)
        extra = {"top_p": top_p} if top_p is not None else {}
        resp = await client.chat.completions.create(
            model=model,
            messages=_to_openai_messages(messages),
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
            **extra,
        )
        return resp.choices[0].message.content or ""

    async def embed(self, text: str, model: str) -> list[float]:
        client = self._client()
        resp = await client.embeddings.create(input=[text], model=model)
        return resp.data[0].embedding


def make_nvidia() -> OpenAICompatProvider:
    return OpenAICompatProvider(
        name="nvidia",
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=os.getenv("NVIDIA_API_KEY", ""),
    )


def make_cerebras() -> OpenAICompatProvider:
    return OpenAICompatProvider(
        name="cerebras",
        base_url="https://api.cerebras.ai/v1",
        api_key=os.getenv("CEREBRAS_API_KEY", ""),
    )


def make_google() -> OpenAICompatProvider:
    return OpenAICompatProvider(
        name="google",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=os.getenv("GOOGLE_API_KEY", ""),
    )
