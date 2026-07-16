import re
import sqlite3
import unicodedata
import uuid
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ── Memória de longo prazo (Fase 5) ──────────────────────────────────────────
DECAY_HALF_LIFE_DAYS = 30.0   # confiança efetiva cai pela metade a cada 30 dias
DECAY_HIDE_BELOW     = 0.25   # fatos abaixo disto somem do prompt (mas ficam no banco)
PURGE_BELOW          = 0.15   # fatos abaixo disto E com +90 dias são apagados
PURGE_MIN_AGE_DAYS   = 90


def _normalize_fact(text: str) -> str:
    """Normaliza um fato para comparação de duplicatas: casefold, sem acentos/pontuação."""
    t = unicodedata.normalize("NFD", text.casefold())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^\w\s]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _effective_confidence(confidence: float, updated_at: str, pinned: bool, now: datetime) -> float:
    """Confiança com decay exponencial por idade. Fatos fixados nunca decaem."""
    if pinned:
        return 2.0  # sempre acima de qualquer fato não-fixado
    try:
        age_days = max(0.0, (now - datetime.fromisoformat(updated_at)).total_seconds() / 86400)
    except (ValueError, TypeError):
        age_days = 0.0
    return confidence * (0.5 ** (age_days / DECAY_HALF_LIFE_DAYS))


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

                -- ── Interioridade escafoldada ──────────────────────────────
                CREATE TABLE IF NOT EXISTS lexicon (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    term TEXT NOT NULL,
                    meaning TEXT NOT NULL,
                    origin TEXT,
                    usage_count INTEGER DEFAULT 0,
                    pinned INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    last_used TEXT
                );

                CREATE TABLE IF NOT EXISTS reflections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    category TEXT DEFAULT 'insight',
                    content TEXT NOT NULL,
                    salience REAL DEFAULT 1.0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS diary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    mood TEXT DEFAULT 'neutro',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS learning_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT,
                    shared INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS kernel_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    note TEXT,
                    active INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS pending_proposals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    rationale TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id);
                CREATE INDEX IF NOT EXISTS idx_facts_user ON facts(user_id);
                CREATE INDEX IF NOT EXISTS idx_lexicon_user ON lexicon(user_id);
                CREATE INDEX IF NOT EXISTS idx_reflections_user ON reflections(user_id);
                CREATE INDEX IF NOT EXISTS idx_diary_user ON diary(user_id);
            """)
            # Migrations: adicionam colunas se não existirem (banco legado)
            cols = [r[1] for r in conn.execute("PRAGMA table_info(messages)").fetchall()]
            if "is_proactive" not in cols:
                conn.execute("ALTER TABLE messages ADD COLUMN is_proactive INTEGER DEFAULT 0")
            if "session" not in cols:
                # Mensagens antigas eram todas do chat
                conn.execute("ALTER TABLE messages ADD COLUMN session TEXT DEFAULT 'chat'")
            fcols = [r[1] for r in conn.execute("PRAGMA table_info(facts)").fetchall()]
            if "pinned" not in fcols:
                # Fatos fixados ("lembra disso") nunca sofrem decay nem purge
                conn.execute("ALTER TABLE facts ADD COLUMN pinned INTEGER DEFAULT 0")

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

    def save_fact(self, user_id: str, fact: str, category: str = "general",
                  pinned: bool = False) -> bool:
        """
        Salva um fato com deduplicação: se um fato equivalente (normalizado) já
        existe, reforça-o (confiança +0.25, atualiza timestamp) em vez de duplicar.
        Retorna True se um fato NOVO foi inserido, False se reforçou existente.
        """
        fact = fact.strip()
        if not fact:
            return False
        now = datetime.now().isoformat()
        norm = _normalize_fact(fact)

        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, fact, confidence, pinned FROM facts WHERE user_id = ?",
                (user_id,)
            ).fetchall()
            for r in rows:
                if _normalize_fact(r["fact"]) == norm:
                    # Duplicata → reforça em vez de inserir
                    conn.execute(
                        """UPDATE facts SET confidence = MIN(1.0, confidence + 0.25),
                           updated_at = ?, pinned = MAX(pinned, ?) WHERE id = ?""",
                        (now, int(pinned), r["id"])
                    )
                    return False

            conn.execute(
                """INSERT INTO facts (user_id, fact, category, pinned, created_at, updated_at)
                   VALUES (?,?,?,?,?,?)""",
                (user_id, fact, category, int(pinned), now, now)
            )

        # Indexa no ChromaDB (apenas fatos novos)
        if self._vectors:
            doc_id = f"fact-{user_id}-{uuid.uuid4().hex[:12]}"
            self._vectors.add(doc_id, fact, {
                "user_id": user_id,
                "type": "fact",
                "category": category,
            })
        return True

    def pin_fact(self, user_id: str, fact: str) -> None:
        """Salva (ou reforça) um fato como fixado — nunca decai nem é purgado."""
        self.save_fact(user_id, fact, category="importante", pinned=True)

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
        """
        Fatos ordenados por confiança efetiva (com decay por idade).
        Fixados sempre primeiro; fatos decaídos abaixo do limiar são omitidos
        (esquecimento gradual) mas permanecem no banco até o purge.
        """
        now = datetime.now()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT fact, confidence, pinned, updated_at FROM facts WHERE user_id = ?",
                (user_id,)
            ).fetchall()

        scored = []
        for r in rows:
            eff = _effective_confidence(
                r["confidence"], r["updated_at"], bool(r["pinned"]), now
            )
            if eff >= DECAY_HIDE_BELOW:
                scored.append((eff, r["fact"]))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [fact for _, fact in scored[:limit]]

    def get_facts_full(self, user_id: str) -> list[dict]:
        """Todos os fatos com metadados (para consolidação e painel de memória)."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT fact, category, confidence, pinned, updated_at
                   FROM facts WHERE user_id = ? ORDER BY pinned DESC, updated_at DESC""",
                (user_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def purge_stale_facts(self, user_id: str = "default") -> int:
        """
        Esquecimento definitivo: apaga fatos não-fixados cuja confiança efetiva
        caiu abaixo de PURGE_BELOW e que têm mais de PURGE_MIN_AGE_DAYS.
        Retorna quantos fatos foram removidos. Chamado no startup do backend.
        """
        now = datetime.now()
        to_delete = []
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, confidence, pinned, updated_at FROM facts WHERE user_id = ?",
                (user_id,)
            ).fetchall()
            for r in rows:
                if r["pinned"]:
                    continue
                eff = _effective_confidence(r["confidence"], r["updated_at"], False, now)
                try:
                    age = (now - datetime.fromisoformat(r["updated_at"])).days
                except (ValueError, TypeError):
                    age = 0
                if eff < PURGE_BELOW and age > PURGE_MIN_AGE_DAYS:
                    to_delete.append(r["id"])
            if to_delete:
                conn.executemany("DELETE FROM facts WHERE id = ?", [(i,) for i in to_delete])
        if to_delete:
            print(f"[KRIRK][memory] Esquecidos {len(to_delete)} fatos obsoletos (decay)")
        return len(to_delete)

    def replace_facts(self, user_id: str, facts: list[str]) -> None:
        """
        Substitui todos os fatos NÃO-fixados pela lista consolidada.
        Usado pela consolidação via LLM. Fatos fixados ficam intocados.
        """
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute("DELETE FROM facts WHERE user_id = ? AND pinned = 0", (user_id,))
            conn.executemany(
                """INSERT INTO facts (user_id, fact, category, pinned, created_at, updated_at)
                   VALUES (?,?,?,?,?,?)""",
                [(user_id, f.strip(), "general", 0, now, now) for f in facts if f.strip()]
            )

    def search_messages_by_period(
        self,
        user_id: str,
        days_from: int,
        days_to: int = 0,
        keyword: str | None = None,
        session: str = "chat",
        limit: int = 40,
    ) -> list[dict]:
        """
        Busca mensagens num período: de days_from dias atrás até days_to dias atrás
        (days_to=0 = agora). Ex: 'semana passada' → days_from=14, days_to=7.
        keyword filtra por substring (case-insensitive via LIKE).
        """
        now = datetime.now()
        start = (now - timedelta(days=max(days_from, days_to))).isoformat()
        end = (now - timedelta(days=min(days_from, days_to))).isoformat()

        query = """SELECT role, content, created_at FROM messages
                   WHERE user_id = ? AND session = ? AND created_at BETWEEN ? AND ?"""
        params: list = [user_id, session, start, end]
        if keyword:
            query += " AND content LIKE ?"
            params.append(f"%{keyword}%")
        query += " ORDER BY id ASC LIMIT ?"
        params.append(limit)

        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    # ── Léxico (bordões / gírias / piadas internas) ───────────────────────────

    def add_term(self, user_id: str, term: str, meaning: str,
                 origin: str = "", pinned: bool = False) -> bool:
        """Adiciona um bordão ao léxico. Dedupe por termo normalizado (reforça uso)."""
        term = term.strip()
        meaning = meaning.strip()
        if not term or not meaning:
            return False
        now = datetime.now().isoformat()
        norm = _normalize_fact(term)
        with self._conn() as conn:
            for r in conn.execute("SELECT id, term FROM lexicon WHERE user_id = ?", (user_id,)).fetchall():
                if _normalize_fact(r["term"]) == norm:
                    conn.execute(
                        "UPDATE lexicon SET meaning=?, usage_count=usage_count+1, last_used=?, pinned=MAX(pinned,?) WHERE id=?",
                        (meaning, now, int(pinned), r["id"])
                    )
                    return False
            conn.execute(
                """INSERT INTO lexicon (user_id, term, meaning, origin, usage_count, pinned, created_at, last_used)
                   VALUES (?,?,?,?,0,?,?,?)""",
                (user_id, term, meaning, origin, int(pinned), now, now)
            )
        if self._vectors:
            self._vectors.add(f"term-{user_id}-{uuid.uuid4().hex[:12]}",
                              f"{term}: {meaning}",
                              {"user_id": user_id, "type": "lexicon"})
        return True

    def get_lexicon(self, user_id: str, limit: int = 20) -> list[dict]:
        """Bordões para injetar no prompt — fixados e mais usados primeiro."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT term, meaning FROM lexicon WHERE user_id = ?
                   ORDER BY pinned DESC, usage_count DESC, last_used DESC LIMIT ?""",
                (user_id, limit)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_lexicon_full(self, user_id: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT term, meaning, origin, usage_count, pinned, created_at, last_used "
                "FROM lexicon WHERE user_id = ? ORDER BY pinned DESC, usage_count DESC",
                (user_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def touch_term(self, user_id: str, term: str) -> None:
        """Registra que um bordão foi usado (incrementa contador)."""
        now = datetime.now().isoformat()
        norm = _normalize_fact(term)
        with self._conn() as conn:
            for r in conn.execute("SELECT id, term FROM lexicon WHERE user_id = ?", (user_id,)).fetchall():
                if _normalize_fact(r["term"]) == norm:
                    conn.execute(
                        "UPDATE lexicon SET usage_count=usage_count+1, last_used=? WHERE id=?",
                        (now, r["id"])
                    )
                    return

    # ── Reflexões / insights ──────────────────────────────────────────────────

    def add_reflection(self, user_id: str, content: str,
                       category: str = "insight", salience: float = 1.0) -> None:
        content = content.strip()
        if not content:
            return
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO reflections (user_id, category, content, salience, created_at) VALUES (?,?,?,?,?)",
                (user_id, category, content, salience, now)
            )

    def get_reflections(self, user_id: str, category: str | None = None,
                        limit: int = 8) -> list[dict]:
        """Reflexões ordenadas por saliência efetiva (com decay temporal)."""
        now = datetime.now()
        with self._conn() as conn:
            if category:
                rows = conn.execute(
                    "SELECT content, category, salience, created_at FROM reflections WHERE user_id=? AND category=?",
                    (user_id, category)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT content, category, salience, created_at FROM reflections WHERE user_id=?",
                    (user_id,)
                ).fetchall()
        scored = []
        for r in rows:
            eff = _effective_confidence(r["salience"], r["created_at"], False, now)
            scored.append((eff, dict(r)))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:limit]]

    # ── Diário ────────────────────────────────────────────────────────────────

    def add_diary_entry(self, user_id: str, content: str, mood: str = "neutro") -> None:
        content = content.strip()
        if not content:
            return
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO diary (user_id, content, mood, created_at) VALUES (?,?,?,?)",
                (user_id, content, mood, now)
            )
        if self._vectors:
            self._vectors.add(f"diary-{user_id}-{uuid.uuid4().hex[:12]}", content,
                              {"user_id": user_id, "type": "diary", "mood": mood})

    def get_recent_diary(self, user_id: str, limit: int = 3) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT content, mood, created_at FROM diary WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit)
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    # ── Notas de aprendizado ──────────────────────────────────────────────────

    def add_learning_note(self, user_id: str, topic: str, content: str, source: str = "") -> None:
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO learning_notes (user_id, topic, content, source, shared, created_at) VALUES (?,?,?,?,0,?)",
                (user_id, topic.strip(), content.strip(), source, now)
            )
        if self._vectors:
            self._vectors.add(f"note-{user_id}-{uuid.uuid4().hex[:12]}",
                              f"{topic}: {content}",
                              {"user_id": user_id, "type": "note"})

    def get_unshared_notes(self, user_id: str, limit: int = 3) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, topic, content, source FROM learning_notes WHERE user_id=? AND shared=0 ORDER BY id ASC LIMIT ?",
                (user_id, limit)
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_note_shared(self, note_id: int) -> None:
        with self._conn() as conn:
            conn.execute("UPDATE learning_notes SET shared=1 WHERE id=?", (note_id,))

    # ── Kernel versionado (identidade auto-autorada) ──────────────────────────

    def save_kernel(self, content: str, note: str = "", activate: bool = False) -> int:
        now = datetime.now().isoformat()
        with self._conn() as conn:
            if activate:
                conn.execute("UPDATE kernel_versions SET active=0")
            cur = conn.execute(
                "INSERT INTO kernel_versions (content, note, active, created_at) VALUES (?,?,?,?)",
                (content.strip(), note, int(activate), now)
            )
            return cur.lastrowid

    def get_active_kernel(self) -> str | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT content FROM kernel_versions WHERE active=1 ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return row["content"] if row else None

    def list_kernels(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, note, active, created_at FROM kernel_versions ORDER BY id DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def activate_kernel(self, kernel_id: int) -> bool:
        with self._conn() as conn:
            row = conn.execute("SELECT id FROM kernel_versions WHERE id=?", (kernel_id,)).fetchone()
            if not row:
                return False
            conn.execute("UPDATE kernel_versions SET active=0")
            conn.execute("UPDATE kernel_versions SET active=1 WHERE id=?", (kernel_id,))
        return True

    def deactivate_all_kernels(self) -> None:
        """Volta à persona padrão (nenhum kernel auto-autorado ativo)."""
        with self._conn() as conn:
            conn.execute("UPDATE kernel_versions SET active=0")

    # ── Propostas pendentes (framework de consentimento) ──────────────────────

    def add_proposal(self, kind: str, payload_json: str, rationale: str = "") -> int:
        now = datetime.now().isoformat()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO pending_proposals (kind, payload_json, rationale, status, created_at) VALUES (?,?,?, 'pending', ?)",
                (kind, payload_json, rationale, now)
            )
            return cur.lastrowid

    def get_pending_proposals(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, kind, payload_json, rationale, created_at FROM pending_proposals WHERE status='pending' ORDER BY id ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_proposal(self, proposal_id: int) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, kind, payload_json, rationale, status FROM pending_proposals WHERE id=?",
                (proposal_id,)
            ).fetchone()
        return dict(row) if row else None

    def set_proposal_status(self, proposal_id: int, status: str) -> None:
        with self._conn() as conn:
            conn.execute("UPDATE pending_proposals SET status=? WHERE id=?", (status, proposal_id))

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
