import sqlite3
import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class MemoryManager:
    def __init__(
        self,
        db_path: str = "data/memory.db",
        chroma_path: str = "data/chroma",
        ollama_base_url: str = "http://localhost:11434",
        ollama_model: str = "nomic-embed-text",
    ):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._init_db()

        # Perfil estruturado do usuário
        from backend.memory.profile_manager import ProfileManager
        self.profile = ProfileManager(db_path)

        # Grafo de conhecimento — entidades e relações permanentes
        from backend.memory.knowledge_graph import KnowledgeGraphManager
        self.kg = KnowledgeGraphManager(db_path)

        # Busca semântica via ChromaDB — degradação graciosa se não disponível
        try:
            from backend.memory.vector_store import VectorStore
            self._vectors: Optional[object] = VectorStore(
                persist_path=chroma_path,
                ollama_base_url=ollama_base_url,
                ollama_model=ollama_model,
            )
        except Exception as e:
            print(f"[KRIRK] ChromaDB indisponível, usando só SQLite: {e}")
            self._vectors = None

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    emotion TEXT DEFAULT 'neutro',
                    session TEXT DEFAULT 'chat',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    fact TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    confidence REAL DEFAULT 1.0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_profile (
                    user_id TEXT PRIMARY KEY,
                    display_name TEXT,
                    preferences TEXT DEFAULT '{}',
                    intimacy_level REAL DEFAULT 0.0,
                    total_messages INTEGER DEFAULT 0,
                    first_seen TEXT,
                    last_seen TEXT
                );

                CREATE TABLE IF NOT EXISTS conversation_summaries (
                    user_id          TEXT PRIMARY KEY,
                    summary          TEXT NOT NULL,
                    messages_covered INTEGER DEFAULT 0,
                    updated_at       TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id);
                CREATE INDEX IF NOT EXISTS idx_facts_user ON facts(user_id);
            """)
            # Migrations: adicionam colunas se não existirem (banco legado)
            cols = [r[1] for r in conn.execute("PRAGMA table_info(messages)").fetchall()]
            if "is_proactive" not in cols:
                conn.execute("ALTER TABLE messages ADD COLUMN is_proactive INTEGER DEFAULT 0")
            if "session" not in cols:
                # Mensagens antigas eram todas do chat
                conn.execute("ALTER TABLE messages ADD COLUMN session TEXT DEFAULT 'chat'")

    def save_message(
        self,
        user_id: str,
        role: str,
        content: str,
        emotion: str = "neutro",
        is_proactive: bool = False,
        session: str = "chat",
    ):
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO messages (user_id, role, content, emotion, is_proactive, session, created_at) VALUES (?,?,?,?,?,?,?)",
                (user_id, role, content, emotion, int(is_proactive), session, now)
            )
            conn.execute(
                """INSERT INTO user_profile (user_id, total_messages, first_seen, last_seen)
                   VALUES (?,1,?,?)
                   ON CONFLICT(user_id) DO UPDATE SET
                     total_messages = total_messages + 1,
                     last_seen = excluded.last_seen""",
                (user_id, now, now)
            )

        # Indexa no ChromaDB para busca semântica (código não vira memória semântica)
        if self._vectors and session == "chat":
            doc_id = f"msg-{user_id}-{uuid.uuid4().hex[:12]}"
            self._vectors.add(doc_id, content, {
                "user_id": user_id,
                "type": "message",
                "role": role,
                "emotion": emotion,
                "session": session,
            })

    def get_recent_messages(self, user_id: str, limit: int = 20, session: str = "chat") -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT role, content, is_proactive FROM messages
                   WHERE user_id = ? AND session = ?
                   ORDER BY id DESC LIMIT ?""",
                (user_id, session, limit)
            ).fetchall()
        return [
            {"role": r["role"], "content": r["content"], "is_proactive": bool(r["is_proactive"])}
            for r in reversed(rows)
        ]

    def save_fact(self, user_id: str, fact: str, category: str = "general"):
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO facts (user_id, fact, category, created_at, updated_at)
                   VALUES (?,?,?,?,?)""",
                (user_id, fact, category, now, now)
            )

        # Indexa no ChromaDB
        if self._vectors:
            doc_id = f"fact-{user_id}-{uuid.uuid4().hex[:12]}"
            self._vectors.add(doc_id, fact, {
                "user_id": user_id,
                "type": "fact",
                "category": category,
            })

    def delete_fact(self, user_id: str, fact: str) -> None:
        """Remove um fato específico pelo texto."""
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM facts WHERE user_id=? AND fact=?",
                (user_id, fact),
            )

    def clear_facts(self, user_id: str) -> None:
        """Remove todos os fatos do usuário."""
        with self._conn() as conn:
            conn.execute("DELETE FROM facts WHERE user_id=?", (user_id,))

    def clear_all(self, user_id: str) -> None:
        """Apaga fatos, Knowledge Graph e perfil. Mantém histórico de mensagens."""
        from backend.memory.profile_manager import DEFAULT_PROFILE
        from copy import deepcopy
        self.clear_facts(user_id)
        self.kg.clear_all(user_id)
        self.update_profile(user_id, deepcopy(DEFAULT_PROFILE))

    def get_facts(self, user_id: str, limit: int = 10) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT fact FROM facts WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
                (user_id, limit)
            ).fetchall()
        return [r["fact"] for r in rows]

    def search_semantic(self, user_id: str, query: str, n: int = 5) -> list[dict]:
        """Busca semântica nas memórias do usuário. Retorna [] se ChromaDB indisponível."""
        if not self._vectors:
            return []
        return self._vectors.search(query, user_id, n=n)

    def get_profile(self, user_id: str) -> dict:
        """Retorna o perfil estruturado do usuário (campos tipados como nome, profissao, etc.)."""
        return self.profile.load(user_id)

    def update_profile(self, user_id: str, profile: dict) -> None:
        """Salva o perfil estruturado completo."""
        self.profile.save(user_id, profile)

    def _get_raw_profile(self, user_id: str) -> Optional[dict]:
        """Acesso à row completa de user_profile (uso interno / get_stats)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM user_profile WHERE user_id = ?", (user_id,)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["preferences"] = json.loads(d["preferences"] or "{}")
        return d

    def update_intimacy(self, user_id: str, delta: float):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO user_profile (user_id, intimacy_level, first_seen, last_seen)
                   VALUES (?,?,datetime('now'),datetime('now'))
                   ON CONFLICT(user_id) DO UPDATE SET
                     intimacy_level = MIN(100.0, MAX(0.0, intimacy_level + ?))""",
                (user_id, delta, delta)
            )

    def save_summary(self, user_id: str, summary: str, messages_covered: int) -> None:
        """Persiste o resumo da conversa (sobrescreve o anterior)."""
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO conversation_summaries
                       (user_id, summary, messages_covered, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                       summary = excluded.summary,
                       messages_covered = excluded.messages_covered,
                       updated_at = excluded.updated_at""",
                (user_id, summary, messages_covered, now),
            )

    def get_summary(self, user_id: str) -> str | None:
        """Retorna o último resumo de conversa salvo, ou None se não existir."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT summary FROM conversation_summaries WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return row["summary"] if row else None

    def get_stats(self, user_id: str) -> dict:
        raw = self._get_raw_profile(user_id)
        facts_count = len(self.get_facts(user_id, limit=1000))
        vector_count = self._vectors.count() if self._vectors else 0
        return {
            "total_messages": raw["total_messages"] if raw else 0,
            "facts_stored": facts_count,
            "intimacy_level": raw["intimacy_level"] if raw else 0.0,
            "first_seen": raw["first_seen"] if raw else None,
            "semantic_memories": vector_count,
        }
