"""
backend/memory/vector_store.py
Armazenamento vetorial com ChromaDB para busca semântica de memórias (Fase 5).

Usa Ollama como embedding function — sem downloads externos, sem SSL.
O mesmo servidor Ollama já em execução gera os embeddings via /api/embeddings.
"""
from __future__ import annotations
import chromadb
from chromadb import EmbeddingFunction, Embeddings


class OllamaEmbeddingFunction(EmbeddingFunction):
    """Embedding function que usa a API local do Ollama — sem internet necessária."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "nomic-embed-text"):
        self._url = f"{base_url.rstrip('/')}/api/embeddings"
        self._model = model
        self._dim: int | None = None

    def __call__(self, input: list[str]) -> Embeddings:
        import requests
        results: Embeddings = []
        for text in input:
            try:
                resp = requests.post(
                    self._url,
                    json={"model": self._model, "prompt": text},
                    timeout=30,
                )
                embedding: list[float] = resp.json().get("embedding", [])
                if embedding:
                    self._dim = len(embedding)
                results.append(embedding)
            except Exception:
                # Fallback: vetor zero (não prejudica busca, apenas ignora este doc)
                results.append([0.0] * (self._dim or 3072))
        return results


class VectorStore:
    def __init__(
        self,
        persist_path: str = "data/chroma",
        ollama_base_url: str = "http://localhost:11434",
        ollama_model: str = "nomic-embed-text",
    ):
        self._client = chromadb.PersistentClient(path=persist_path)
        ef = OllamaEmbeddingFunction(base_url=ollama_base_url, model=ollama_model)

        # Coleção única para mensagens e fatos, separados por metadata
        self._col = self._client.get_or_create_collection(
            name="krirk_memories",
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, doc_id: str, text: str, metadata: dict) -> None:
        """Adiciona ou atualiza um documento no índice vetorial."""
        if not text or not text.strip():
            return
        try:
            self._col.upsert(
                ids=[doc_id],
                documents=[text],
                metadatas=[metadata],
            )
        except Exception:
            pass  # nunca bloqueia o fluxo principal

    def search(self, query: str, user_id: str, n: int = 5) -> list[dict]:
        """
        Retorna os n documentos mais semanticamente próximos da query.
        Filtra por user_id via metadata.
        """
        if not query or not query.strip():
            return []
        try:
            total = self._col.count()
            if total == 0:
                return []
            n_results = min(n, total)

            results = self._col.query(
                query_texts=[query],
                n_results=n_results,
                where={"user_id": user_id},
            )
            docs      = results.get("documents", [[]])[0]
            metas     = results.get("metadatas",  [[]])[0]
            distances = results.get("distances",  [[]])[0]

            out = []
            for doc, meta, dist in zip(docs, metas, distances):
                out.append({
                    "text":    doc,
                    "type":    meta.get("type", "message"),
                    "role":    meta.get("role", ""),
                    "emotion": meta.get("emotion", ""),
                    "score":   round(1.0 - dist, 3),
                })
            return out
        except Exception:
            return []

    def count(self) -> int:
        try:
            return self._col.count()
        except Exception:
            return 0
