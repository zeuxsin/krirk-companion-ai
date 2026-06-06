"""
backend/memory/knowledge_graph.py
Grafo de conhecimento persistido em SQLite.

Armazena entidades e relações permanentes sobre o usuário e seu contexto.
Exemplos: "Erik → usa → Python", "KRIRK → usa_tecnologia → Ollama"

Totalmente local — não adiciona dependências novas ao projeto.
"""
import sqlite3
from collections import defaultdict
from datetime import datetime
from typing import Optional


class KnowledgeGraphManager:
    """Gerencia entidades e relações permanentes em SQLite."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._init_tables()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS kg_entities (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     TEXT    NOT NULL,
                    name        TEXT    NOT NULL,
                    type        TEXT    NOT NULL,
                    created_at  TEXT    NOT NULL,
                    UNIQUE(user_id, name)
                );

                CREATE TABLE IF NOT EXISTS kg_relations (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     TEXT    NOT NULL,
                    entity_from TEXT    NOT NULL,
                    relation    TEXT    NOT NULL,
                    entity_to   TEXT    NOT NULL,
                    confidence  REAL    DEFAULT 1.0,
                    created_at  TEXT    NOT NULL,
                    UNIQUE(user_id, entity_from, relation, entity_to)
                );

                CREATE INDEX IF NOT EXISTS idx_kg_entities_user
                    ON kg_entities(user_id);
                CREATE INDEX IF NOT EXISTS idx_kg_relations_user
                    ON kg_relations(user_id);
                CREATE INDEX IF NOT EXISTS idx_kg_relations_from
                    ON kg_relations(entity_from);
            """)

    # ── Escrita ───────────────────────────────────────────────────────────────

    def upsert_entity(self, user_id: str, name: str, entity_type: str) -> None:
        """Insere entidade se ainda não existir. Ignora duplicatas silenciosamente."""
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO kg_entities (user_id, name, type, created_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(user_id, name) DO NOTHING""",
                (user_id, name.strip(), entity_type.strip(), now),
            )

    def upsert_relation(
        self,
        user_id: str,
        entity_from: str,
        relation: str,
        entity_to: str,
        confidence: float = 1.0,
    ) -> None:
        """Insere relação se ainda não existir. Ignora duplicatas silenciosamente."""
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO kg_relations
                       (user_id, entity_from, relation, entity_to, confidence, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, entity_from, relation, entity_to) DO NOTHING""",
                (
                    user_id,
                    entity_from.strip(),
                    relation.strip(),
                    entity_to.strip(),
                    confidence,
                    now,
                ),
            )

    # ── Leitura ───────────────────────────────────────────────────────────────

    def get_relations(self, user_id: str, limit: int = 50) -> list[dict]:
        """Retorna relações ordenadas por confiança e data."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT entity_from, relation, entity_to, confidence
                   FROM kg_relations WHERE user_id = ?
                   ORDER BY confidence DESC, created_at DESC
                   LIMIT ?""",
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def to_prompt_text(self, user_id: str, max_relations: int = 25) -> Optional[str]:
        """Formata o grafo como bloco compacto para o system prompt.

        Agrupa destinos com a mesma origem+relação:
            Erik → usa → Python, FastAPI, VS Code
            Erik → trabalha_em → KRIRK
            KRIRK → usa_tecnologia → Ollama, Tauri
        """
        relations = self.get_relations(user_id, limit=max_relations)
        if not relations:
            return None

        # Agrupa destinos por (origem, relação)
        grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
        for r in relations:
            key = (r["entity_from"], r["relation"])
            if r["entity_to"] not in grouped[key]:
                grouped[key].append(r["entity_to"])

        lines = [
            f"{efrom} → {rel} → {', '.join(targets)}"
            for (efrom, rel), targets in grouped.items()
        ]
        return "\n".join(lines) if lines else None

    # ── Estatísticas ─────────────────────────────────────────────────────────

    def get_stats(self, user_id: str) -> dict:
        with self._conn() as conn:
            n_entities = conn.execute(
                "SELECT COUNT(*) AS n FROM kg_entities WHERE user_id = ?", (user_id,)
            ).fetchone()["n"]
            n_relations = conn.execute(
                "SELECT COUNT(*) AS n FROM kg_relations WHERE user_id = ?", (user_id,)
            ).fetchone()["n"]
        return {"entities": n_entities, "relations": n_relations}
