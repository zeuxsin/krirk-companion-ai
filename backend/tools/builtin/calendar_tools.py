"""
backend/tools/builtin/calendar_tools.py
Ponte com o Phantom System (C:\\calendario) — a agenda gamificada do usuário.

Dois caminhos, nesta ordem:
1. API do servidor local (server.py, http://127.0.0.1:8123): POST /api/inbox
   com campos ricos (hora separada, tipo tarefa/compromisso, boss). Com o app
   aberto, a tela atualiza NA HORA via SSE.
2. Fallback de arquivo (dados/krirk_inbox.js): quando o servidor está
   desligado — o app importa no próximo boot (mergeKrirkInbox no app.js).

A resolução de data ("amanhã", "quarta", "15/08") é DETERMINÍSTICA em Python —
modelos pequenos já erraram dia da semana em produção; código não erra.
"""
import json
import re
import time
import unicodedata
from datetime import date, timedelta
from pathlib import Path

import httpx

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

_COMPROMISSO_WORDS = {
    "compromisso", "evento", "consulta", "reuniao", "appointment", "event",
    "encontro", "visita",
}

_HORA_RE = re.compile(r"^(\d{1,2})(?:[:h.](\d{2}))?\s*(?:h(?:rs?|oras)?)?$")


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


def norm_hora(raw: str) -> str:
    """'14h' → '14:00', '14h30'/'14.30' → '14:30', '9:5' inválido → ''."""
    s = (raw or "").strip().lower()
    if not s:
        return ""
    m = _HORA_RE.match(s)
    if not m:
        return ""
    h = int(m.group(1))
    mi = int(m.group(2) or 0)
    if h > 23 or mi > 59:
        return ""
    return f"{h:02d}:{mi:02d}"


def norm_tipo(raw: str) -> str:
    return "compromisso" if _norm(raw) in _COMPROMISSO_WORDS else "tarefa"


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


async def _post_api(api_base: str, payload: dict) -> bool:
    """POST na caixa de entrada do servidor local. False = servidor fora."""
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            r = await client.post(f"{api_base}/api/inbox", json=payload)
            return r.status_code == 201
    except Exception:
        return False


def make_add_calendar_task(calendar_dir: str, api_base: str) -> Tool:
    inbox = Path(calendar_dir) / _INBOX_REL

    async def _add(titulo: str = "", data: str = "", hora: str = "",
                   tipo: str = "tarefa", xp: str = "", gold: str = "",
                   atributo: str = "dis", boss: str = "") -> str:
        titulo = (titulo or "").strip()
        if not titulo:
            return "[Erro] Informe o título da tarefa."
        resolved = resolve_date(data)
        if resolved is None:
            return (f"[Erro] Não entendi a data '{data}'. Use hoje/amanhã/dia "
                    "da semana/DD/MM ou YYYY-MM-DD.")
        tipo_n = norm_tipo(tipo)
        hora_n = norm_hora(hora)
        attr = _ATTR_MAP.get(_norm(atributo), "dis")
        # sem xp/gold explícitos o servidor aplica o padrão do tipo
        xp_default, gold_default = (10, 5) if tipo_n == "compromisso" else (20, 10)
        try:
            xp_i = max(5, min(200, int(float(xp)))) if str(xp).strip() else xp_default
        except (TypeError, ValueError):
            xp_i = xp_default
        try:
            gold_i = max(0, min(200, int(float(gold)))) if str(gold).strip() else gold_default
        except (TypeError, ValueError):
            gold_i = gold_default

        dia_semana = ["segunda", "terça", "quarta", "quinta", "sexta",
                      "sábado", "domingo"][date.fromisoformat(resolved).weekday()]
        quando = f"{resolved} ({dia_semana})" + (f" às {hora_n}" if hora_n else "")

        # 1) API do servidor local — tela atualiza na hora
        payload = {
            "titulo": titulo[:120], "tipo": tipo_n, "data": resolved,
            "hora": hora_n, "atributo": attr, "xp": xp_i, "gold": gold_i,
        }
        if (boss or "").strip():
            payload["boss"] = boss.strip()[:60]
        rotulo = ("Compromisso adicionado" if tipo_n == "compromisso"
                  else "Tarefa adicionada")
        if await _post_api(api_base, payload):
            extra = f", vinculado ao boss '{payload['boss']}'" if "boss" in payload else ""
            return (f"{rotulo} à agenda Phantom System: "
                    f"'{titulo}' em {quando}, {xp_i} XP / {gold_i} G{extra}. "
                    "Se o app estiver aberto, já apareceu na tela.")

        # 2) Fallback: ponte de arquivo (app importa no próximo boot).
        # Mesmas chaves PT da API — o mergeKrirkInbox entende; hora tem campo
        # próprio (nunca no título).
        entries = read_inbox(inbox)
        entry = {
            "id": f"krirk-{int(time.time() * 1000)}",
            "titulo": titulo[:120],
            "data": resolved,
            "hora": hora_n,
            "tipo": tipo_n,
            "atributo": attr,
            "xp": xp_i,
            "gold": gold_i,
        }
        if (boss or "").strip():
            entry["boss"] = boss.strip()[:60]
        entries.append(entry)
        try:
            write_inbox(inbox, entries)
        except OSError as e:
            return f"[Erro] Não consegui gravar na agenda: {e}"
        return (f"{rotulo} à fila da agenda Phantom "
                f"System: '{titulo}' em {quando}, {xp_i} XP / {gold_i} G. "
                "O servidor do calendário está desligado, então entra no "
                "calendário na próxima vez que o app for aberto.")

    return Tool(
        name="add_calendar_task",
        description=(
            "Adiciona tarefa ou compromisso à AGENDA REAL do usuário (app "
            "Phantom System). Use para qualquer 'coloca na agenda', 'adiciona "
            "tarefa', 'tenho X na quarta'."
        ),
        params=[
            ToolParam("titulo", "título (SEM o horário — ele vai no param hora)", "string"),
            ToolParam("data", "hoje | amanhã | dia da semana ('quarta', 'próxima quarta') | DD/MM | YYYY-MM-DD", "string"),
            ToolParam("hora", "horário HH:MM se houver (ex: '14:00', '13:30')", "string", required=False, default=""),
            ToolParam("tipo", "'compromisso' (consulta, reunião, evento — comparecer) ou 'tarefa' (produzir algo)", "string", required=False, default="tarefa"),
            ToolParam("xp", "XP (5-200; vazio = padrão do tipo)", "string", required=False, default=""),
            ToolParam("gold", "Gold (0-200; vazio = padrão do tipo)", "string", required=False, default=""),
            ToolParam("atributo", "for/int/agi/dis/cri (força, inteligência, agilidade, disciplina, criatividade)", "string", required=False, default="dis"),
            ToolParam("boss", "nome de um boss existente para vincular a tarefa (opcional)", "string", required=False, default=""),
        ],
        func=_add,
    )


def make_list_calendar_tasks(calendar_dir: str, api_base: str) -> Tool:
    inbox = Path(calendar_dir) / _INBOX_REL

    async def _list() -> str:
        # Fila do servidor (itens ainda não puxados pelo navegador)
        api_items: list[dict] = []
        try:
            async with httpx.AsyncClient(timeout=4) as client:
                r = await client.get(f"{api_base}/api/inbox")
                if r.status_code == 200 and isinstance(r.json(), list):
                    api_items = r.json()
        except Exception:
            pass
        file_items = read_inbox(inbox)
        if not api_items and not file_items:
            return ("Nenhuma tarefa na fila da agenda — o que foi adicionado "
                    "antes já entrou no calendário.")
        lines = []
        for e in api_items[-20:]:
            quando = e.get("data", "?") + (f" {e['hora']}" if e.get("hora") else "")
            lines.append(f"- {quando}: {e.get('titulo', '?')} ({e.get('xp', '?')} XP)")
        for e in file_items[-20:]:
            quando = (e.get("data") or e.get("date") or "?")
            if e.get("hora"):
                quando += f" {e['hora']}"
            nome = e.get("titulo") or e.get("title") or "?"
            lines.append(f"- {quando}: {nome} ({e.get('xp', '?')} XP)")
        return ("Na fila da agenda (entram no app aberto/próxima abertura):\n"
                + "\n".join(lines))

    return Tool(
        name="list_calendar_tasks",
        description="Lista as tarefas que a Krirk adicionou e ainda estão na fila da agenda Phantom System.",
        params=[],
        func=_list,
    )
