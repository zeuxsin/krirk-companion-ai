"""
backend/memory/profile_manager.py
Gerencia o perfil estruturado do usuário — campos tipados persistidos no SQLite.
Atualizado automaticamente em background via LLM após cada conversa.
"""
import json
import sqlite3
from copy import deepcopy
from datetime import datetime
from pathlib import Path

# Perfil padrão — campos nulos/vazios até serem descobertos
DEFAULT_PROFILE: dict = {
    "nome":       None,   # str  — primeiro nome ou apelido
    "idade":      None,   # str  — ex: "22 anos"
    "profissao":  None,   # str  — ex: "desenvolvedor"
    "cidade":     None,   # str  — ex: "São Paulo"
    "interesses": [],     # list — hobbies, tópicos favoritos
    "projetos":   [],     # list — projetos ativos do usuário
    "ferramentas":[],     # list — linguagens, apps, frameworks que usa
    "objetivos":  [],     # list — metas de curto/longo prazo
    "notas":      [],     # list — observações que não cabem nos outros campos
}

# Rótulos em PT para exibição no system prompt
_LABELS = {
    "nome":        "Nome",
    "idade":       "Idade",
    "profissao":   "Profissão",
    "cidade":      "Cidade",
    "interesses":  "Interesses",
    "projetos":    "Projetos",
    "ferramentas": "Ferramentas",
    "objetivos":   "Objetivos",
    "notas":       "Notas",
}


class ProfileManager:
    """Persiste e recupera o perfil estruturado do usuário no SQLite."""

    def __init__(self, db_path: str):
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ── Carga / salvamento ────────────────────────────────────────────────────

    def load(self, user_id: str) -> dict:
        """
        Carrega o perfil da coluna `preferences` em user_profile.
        Retorna uma cópia de DEFAULT_PROFILE se o usuário não tiver perfil ainda.
        """
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT preferences FROM user_profile WHERE user_id = ?",
                    (user_id,)
                ).fetchone()
        except Exception:
            return deepcopy(DEFAULT_PROFILE)

        if not row or not row["preferences"]:
            return deepcopy(DEFAULT_PROFILE)

        try:
            stored = json.loads(row["preferences"])
            # Merge com DEFAULT_PROFILE para garantir que novos campos existam
            profile = deepcopy(DEFAULT_PROFILE)
            for key in DEFAULT_PROFILE:
                if key in stored:
                    profile[key] = stored[key]
            return profile
        except (json.JSONDecodeError, TypeError):
            return deepcopy(DEFAULT_PROFILE)

    def save(self, user_id: str, profile: dict) -> None:
        """Salva o perfil como JSON na coluna `preferences` de user_profile."""
        now = datetime.now().isoformat()
        prefs_json = json.dumps(profile, ensure_ascii=False)
        try:
            with self._conn() as conn:
                conn.execute(
                    """INSERT INTO user_profile (user_id, preferences, first_seen, last_seen)
                       VALUES (?, ?, ?, ?)
                       ON CONFLICT(user_id) DO UPDATE SET
                         preferences = excluded.preferences,
                         last_seen   = excluded.last_seen""",
                    (user_id, prefs_json, now, now)
                )
        except Exception as e:
            print(f"[KRIRK][profile] Erro ao salvar: {e}")

    # ── Mesclagem de atualizações ─────────────────────────────────────────────

    def merge_update(self, current: dict, delta: dict) -> dict:
        """
        Mescla `delta` (atualizações extraídas do LLM) no perfil atual.

        Regras:
        - Campos string (nome, idade, profissao, cidade): sobrescreve se o valor no delta
          não for None/vazio.
        - Campos lista (interesses, projetos, ferramentas, objetivos, notas): faz UNION
          sem duplicatas (case-insensitive). Aceita tanto lista quanto string do delta.
        """
        merged = deepcopy(current)

        for key, new_val in delta.items():
            if key not in DEFAULT_PROFILE:
                continue  # ignora campos desconhecidos do LLM

            default = DEFAULT_PROFILE[key]

            if isinstance(default, list):
                # Campo lista — adiciona novos itens sem duplicatas
                existing = merged.get(key) or []
                if isinstance(new_val, str):
                    new_val = [new_val]
                if isinstance(new_val, list):
                    existing_lower = {str(x).lower().strip() for x in existing}
                    for item in new_val:
                        item = str(item).strip()
                        if item and item.lower() not in existing_lower:
                            existing.append(item)
                            existing_lower.add(item.lower())
                merged[key] = existing
            else:
                # Campo string/scalar — sobrescreve se valor válido
                if new_val is not None and str(new_val).strip():
                    merged[key] = str(new_val).strip()

        return merged

    # ── Formatação para o system prompt ──────────────────────────────────────

    def to_prompt_text(self, profile: dict) -> str | None:
        """
        Converte o perfil para texto legível para ser injetado no system prompt.
        Retorna None se o perfil estiver completamente vazio (nada descoberto ainda).
        """
        lines = []
        for key, label in _LABELS.items():
            val = profile.get(key)
            if val is None:
                continue
            if isinstance(val, list):
                if not val:
                    continue
                lines.append(f"{label}: {', '.join(str(v) for v in val)}")
            else:
                lines.append(f"{label}: {val}")

        return "\n".join(lines) if lines else None
