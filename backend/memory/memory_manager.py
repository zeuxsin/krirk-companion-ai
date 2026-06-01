import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class MemoryManager:
    def __init__(self, db_path: str = "data/memory.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._init_db()

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
                    emotion TEXT DEFAULT 'neutral',
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

                CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id);
                CREATE INDEX IF NOT EXISTS idx_facts_user ON facts(user_id);
            """)

    def save_message(self, user_id: str, role: str, content: str, emotion: str = "neutral"):
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO messages (user_id, role, content, emotion, created_at) VALUES (?,?,?,?,?)",
                (user_id, role, content, emotion, now)
            )
            conn.execute(
                """INSERT INTO user_profile (user_id, total_messages, first_seen, last_seen)
                   VALUES (?,1,?,?)
                   ON CONFLICT(user_id) DO UPDATE SET
                     total_messages = total_messages + 1,
                     last_seen = excluded.last_seen""",
                (user_id, now, now)
            )

    def get_recent_messages(self, user_id: str, limit: int = 20) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT role, content FROM messages
                   WHERE user_id = ?
                   ORDER BY id DESC LIMIT ?""",
                (user_id, limit)
            ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def save_fact(self, user_id: str, fact: str, category: str = "general"):
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO facts (user_id, fact, category, created_at, updated_at)
                   VALUES (?,?,?,?,?)""",
                (user_id, fact, category, now, now)
            )

    def get_facts(self, user_id: str, limit: int = 10) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT fact FROM facts WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
                (user_id, limit)
            ).fetchall()
        return [r["fact"] for r in rows]

    def get_profile(self, user_id: str) -> Optional[dict]:
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

    def get_stats(self, user_id: str) -> dict:
        profile = self.get_profile(user_id)
        facts_count = len(self.get_facts(user_id, limit=1000))
        return {
            "total_messages": profile["total_messages"] if profile else 0,
            "facts_stored": facts_count,
            "intimacy_level": profile["intimacy_level"] if profile else 0.0,
            "first_seen": profile["first_seen"] if profile else None,
        }
