"""
backend/tools/builtin/automation_tools.py
Ferramentas de automação do desktop (Fase 4): teclado, janelas e leitura web.

Teclado usa pyautogui (com failsafe: mover o mouse para o canto sup. esquerdo aborta).
Janelas usam PowerShell (sem dependências extras).
fetch_url usa requests + HTMLParser da stdlib (sem BeautifulSoup).
"""
import asyncio
import re
import subprocess
from html.parser import HTMLParser

from backend.tools.base import Tool, ToolParam


# ── press_hotkey ──────────────────────────────────────────────────────────────

_KEY_ALIASES = {
    "windows": "win", "super": "win", "control": "ctrl",
    "escape": "esc", "return": "enter", "del": "delete",
}


def _parse_hotkey(keys: str) -> list[str]:
    """'ctrl+shift+s' → ['ctrl','shift','s']. Normaliza aliases comuns."""
    parts = [p.strip().lower() for p in keys.split("+") if p.strip()]
    return [_KEY_ALIASES.get(p, p) for p in parts]


async def _press_hotkey(keys: str) -> str:
    parts = _parse_hotkey(keys)
    if not parts:
        return "[Erro] Nenhuma tecla informada."
    try:
        import pyautogui
        valid = set(pyautogui.KEYBOARD_KEYS)
        invalid = [p for p in parts if p not in valid]
        if invalid:
            return f"[Erro] Teclas desconhecidas: {invalid}. Exemplos válidos: ctrl, shift, alt, win, enter, tab, f5, a-z."
        await asyncio.to_thread(pyautogui.hotkey, *parts)
        return f"Atalho pressionado: {'+'.join(parts)}"
    except Exception as e:
        return f"[Erro] Falha ao pressionar atalho: {e}"


def make_press_hotkey() -> Tool:
    return Tool(
        name="press_hotkey",
        description=(
            "Pressiona um atalho de teclado na janela ativa. "
            "Ex: 'ctrl+s' (salvar), 'alt+tab' (trocar janela), 'win+d' (mostrar desktop), 'f5' (atualizar)."
        ),
        params=[
            ToolParam("keys", "Teclas separadas por '+' (ex: ctrl+shift+s)", "string"),
        ],
        func=_press_hotkey,
    )


# ── type_text ─────────────────────────────────────────────────────────────────

async def _type_text(text: str) -> str:
    if not text:
        return "[Erro] Texto vazio."
    try:
        import pyautogui
        if text.isascii():
            await asyncio.to_thread(pyautogui.write, text, 0.02)
        else:
            # pyautogui.write só digita ASCII — para acentos usa clipboard + ctrl+v
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value ([Console]::In.ReadToEnd())"],
                input=text, capture_output=True, text=True, timeout=5,
            )
            if proc.returncode != 0:
                return f"[Erro] Falha ao copiar texto: {proc.stderr[:100]}"
            await asyncio.to_thread(pyautogui.hotkey, "ctrl", "v")
        return f"Texto digitado ({len(text)} caracteres)."
    except Exception as e:
        return f"[Erro] Falha ao digitar: {e}"


def make_type_text() -> Tool:
    return Tool(
        name="type_text",
        description="Digita um texto na janela/campo atualmente em foco (como se o usuário digitasse).",
        params=[
            ToolParam("text", "Texto a digitar", "string"),
        ],
        func=_type_text,
    )


# ── list_windows ──────────────────────────────────────────────────────────────

async def _list_windows() -> str:
    try:
        proc = await asyncio.to_thread(
            subprocess.run,
            ["powershell", "-NoProfile", "-Command",
             "Get-Process | Where-Object {$_.MainWindowTitle} | "
             "ForEach-Object { \"$($_.ProcessName): $($_.MainWindowTitle)\" }"],
            capture_output=True, text=True, timeout=8,
        )
        out = (proc.stdout or "").strip()
        if not out:
            return "Nenhuma janela visível encontrada."
        return f"Janelas abertas:\n{out}"
    except Exception as e:
        return f"[Erro] Falha ao listar janelas: {e}"


def make_list_windows() -> Tool:
    return Tool(
        name="list_windows",
        description="Lista todas as janelas abertas no momento (processo: título).",
        params=[],
        func=_list_windows,
    )


# ── focus_window ──────────────────────────────────────────────────────────────

async def _focus_window(title: str) -> str:
    if not title.strip():
        return "[Erro] Título vazio."
    safe_title = title.replace("'", "''")
    try:
        proc = await asyncio.to_thread(
            subprocess.run,
            ["powershell", "-NoProfile", "-Command",
             f"$ok = (New-Object -ComObject WScript.Shell).AppActivate('{safe_title}'); "
             f"if ($ok) {{ 'OK' }} else {{ 'NOTFOUND' }}"],
            capture_output=True, text=True, timeout=8,
        )
        if "OK" in (proc.stdout or ""):
            return f"Janela '{title}' trazida para frente."
        return f"[Erro] Janela com título contendo '{title}' não encontrada. Use list_windows para ver as janelas abertas."
    except Exception as e:
        return f"[Erro] Falha ao focar janela: {e}"


def make_focus_window() -> Tool:
    return Tool(
        name="focus_window",
        description="Traz uma janela para frente pelo título (busca parcial). Use list_windows antes se não souber o título exato.",
        params=[
            ToolParam("title", "Título (ou parte do título) da janela", "string"),
        ],
        func=_focus_window,
    )


# ── fetch_url ─────────────────────────────────────────────────────────────────

class _TextExtractor(HTMLParser):
    """Extrai texto legível de HTML, ignorando script/style/nav."""
    _SKIP = {"script", "style", "noscript", "svg", "head", "nav", "footer"}
    _BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
              "section", "article", "blockquote", "pre"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in self._BLOCK:
            self._chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in self._BLOCK:
            self._chunks.append("\n")

    def handle_data(self, data):
        if self._skip_depth == 0 and data.strip():
            self._chunks.append(data)

    def get_text(self) -> str:
        text = "".join(self._chunks)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        return text.strip()


def _html_to_text(html: str) -> str:
    """Converte HTML em texto legível (função pura — testável offline)."""
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        pass
    return parser.get_text()


async def _fetch_url(url: str, max_chars: int = 4000) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        import requests

        def _get():
            return requests.get(
                url, timeout=8,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) KRIRK/0.1"},
            )
        resp = await asyncio.to_thread(_get)
        if resp.status_code >= 400:
            return f"[Erro] HTTP {resp.status_code} ao acessar {url}"

        ctype = resp.headers.get("content-type", "")
        if "html" in ctype:
            text = _html_to_text(resp.text)
        else:
            text = resp.text

        max_chars = max(500, min(12000, int(max_chars)))
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n... (truncado em {max_chars} caracteres)"
        return f"Conteúdo de {url}:\n\n{text}" if text else f"[Erro] Página vazia: {url}"
    except Exception as e:
        return f"[Erro] Falha ao acessar {url}: {type(e).__name__}: {e}"


def make_fetch_url() -> Tool:
    return Tool(
        name="fetch_url",
        description=(
            "Baixa e retorna o TEXTO de uma página web específica. "
            "Use quando o usuário quer o conteúdo de uma URL/site conhecido. "
            "Para PROCURAR algo na internet, use web_search."
        ),
        params=[
            ToolParam("url", "URL da página (ex: https://exemplo.com/artigo)", "string"),
            ToolParam("max_chars", "Máximo de caracteres a retornar", "int", required=False, default=4000),
        ],
        func=_fetch_url,
        timeout=20,
    )
