"""
backend/tools/builtin/calendar_tools.py
Ponte com o Phantom System (C:\\calendario) — a agenda gamificada do usuário.

O app salva tudo em localStorage do navegador, então a Krirk não escreve no
save diretamente: ela deposita tarefas em dados/krirk_inbox.js e o app as
importa (uma única vez cada) na próxima vez que for aberto.

A resolução de data ("amanhã", "quarta", "15/08") é DETERMINÍSTICA em Python —
modelos pequenos já erraram dia da semana em produção; código não erra.
"""
import json
import time
import unicodedata
from datetime import date, timedelta
from pathlib import Path

from backend.tools.base import Tool, ToolParam

_INBOX_REL = Path("dados") / "krirk_inbox.js"
_HEADER = "window.KRIRK_INBOX = "

_WEEKDAYS = {
    "segunda": 0, "segunda-feira": 0, "terca": 1, "terca-feira": 1,
    "quarta": 2, "quarta-feira": 2, "quinta": 3, "quinta-feira": 3,
    "sexta": 4, "sexta-feira": 4, "sabado": 5, "domingo": 6,
}

_ATTR_MAP = {
    "for": "for", "forca": "for", "fisico": "for", "exercicio": "for",
    "int": "int", "inteligencia": "int", "estudo": "int",
    "agi": "agi", "agilidade": "agi",
    "dis": "dis", "disciplina": "dis",
    "cri": "cri", "criatividade": "cri", "criativo": "cri",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").strip().lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def resolve_date(raw: str, today: date | None = None) -> str | None:
    """
    'hoje' | 'amanha' | 'depois de amanha' | dia da semana ('quarta',
    'proxima quarta') | 'DD/MM' | 'DD/MM/YYYY' | 'YYYY-MM-DD' → 'YYYY-MM-DD'.
    None se não der para resolver com segurança.
    """
    today = today or date.today()
    s = _norm(raw)
    if not s:
        return None
    if s == "hoje":
        return today.isoformat()
    if s in ("amanha", "amanha!"):
        return (today + timedelta(days=1)).isoformat()
    if s in ("depois de amanha", "depois-de-amanha"):
        return (today + timedelta(days=2)).isoformat()

    strict_next = False
    for pref in ("proxima ", "proximo ", "na proxima ", "no proximo "):
        if s.startswith(pref):
            s = s[len(pref):]
            strict_next = True
            break
    s = s.removeprefix("na ").removeprefix("no ")

    if s in _WEEKDAYS:
        delta = (_WEEKDAYS[s] - today.weekday()) % 7
        if delta == 0 and strict_next:
            delta = 7
        return (today + timedelta(days=delta)).isoformat()

    # YYYY-MM-DD
    try:
        return date.fromisoformat(s).isoformat()
    except ValueError:
        pass
    # DD/MM ou DD/MM/YYYY
    parts = s.split("/")
    if len(parts) in (2, 3):
        try:
            d, m = int(parts[0]), int(parts[1])
            y = int(parts[2]) if len(parts) == 3 else today.year
            if y < 100:
                y += 2000
            resolved = date(y, m, d)
            if len(parts) == 2 and resolved < today:
                resolved = date(y + 1, m, d)  # data já passou → ano que vem
            return resolved.isoformat()
        except ValueError:
            return None
    return None


def read_inbox(path: Path) -> list[dict]:
    """Extrai a lista JSON de dentro do wrapper JS (só a tool escreve nele)."""
    if not path.exists():
        return []
    txt = path.read_text(encoding="utf-8")
    start, end = txt.find("["), txt.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        data = json.loads(txt[start:end + 1])
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def write_inbox(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _HEADER + json.dumps(entries, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )


def make_add_calendar_task(calendar_dir: str) -> Tool:
    inbox = Path(calendar_dir) / _INBOX_REL

    async def _add(titulo: str = "", data: str = "", xp: str = "20",
                   gold: str = "10", atributo: str = "dis") -> str:
        titulo = (titulo or "").strip()
        if not titulo:
            return "[Erro] Informe o título da tarefa."
        resolved = resolve_date(data)
        if resolved is None:
            return (f"[Erro] Não entendi a data '{data}'. Use hoje/amanhã/dia "
                    "da semana/DD/MM ou YYYY-MM-DD.")
        try:
            xp_i = max(5, min(200, int(float(xp))))
        except (TypeError, ValueError):
            xp_i = 20
        try:
            gold_i = max(0, min(200, int(float(gold))))
        except (TypeError, ValueError):
            gold_i = 10
        attr = _ATTR_MAP.get(_norm(atributo), "dis")

        entries = read_inbox(inbox)
        entries.append({
            "id": f"krirk-{int(time.time() * 1000)}",
            "title": titulo[:120],
            "date": resolved,
            "attr": attr,
            "xp": xp_i,
            "gold": gold_i,
        })
        try:
            write_inbox(inbox, entries)
        except OSError as e:
            return f"[Erro] Não consegui gravar na agenda: {e}"
        dia_semana = ["segunda", "terça", "quarta", "quinta", "sexta",
                      "sábado", "domingo"][date.fromisoformat(resolved).weekday()]
        return (f"Tarefa adicionada à agenda Phantom System: '{titulo}' em "
                f"{resolved} ({dia_semana}), {xp_i} XP / {gold_i} G. "
                "Entra no calendário na próxima vez que o app for aberto.")

    return Tool(
        name="add_calendar_task",
        description=(
            "Adiciona uma tarefa/compromisso à AGENDA REAL do usuário (app "
            "Phantom System). Use para qualquer 'coloca na agenda', 'adiciona "
            "tarefa', 'tenho X na quarta'. Horário vai junto no título "
            "(ex: 'Psicóloga 13:30')."
        ),
        params=[
            ToolParam("titulo", "título da tarefa (inclua o horário se houver)", "string"),
            ToolParam("data", "hoje | amanhã | dia da semana ('quarta', 'próxima quarta') | DD/MM | YYYY-MM-DD", "string"),
            ToolParam("xp", "XP da tarefa (5-200)", "string", required=False, default="20"),
            ToolParam("gold", "Gold da tarefa (0-200)", "string", required=False, default="10"),
            ToolParam("atributo", "for/int/agi/dis/cri (força, inteligência, agilidade, disciplina, criatividade)", "string", required=False, default="dis"),
        ],
        func=_add,
    )


def make_list_calendar_tasks(calendar_dir: str) -> Tool:
    inbox = Path(calendar_dir) / _INBOX_REL

    async def _list() -> str:
        entries = read_inbox(inbox)
        if not entries:
            return "Nenhuma tarefa adicionada pela Krirk na fila da agenda."
        lines = [f"- {e.get('date', '?')}: {e.get('title', '?')} "
                 f"({e.get('xp', '?')} XP)" for e in entries[-20:]]
        return ("Tarefas que eu adicionei à agenda (entram no app quando ele "
                "for aberto):\n" + "\n".join(lines))

    return Tool(
        name="list_calendar_tasks",
        description="Lista as tarefas que a Krirk já adicionou à agenda Phantom System.",
        params=[],
        func=_list,
    )
