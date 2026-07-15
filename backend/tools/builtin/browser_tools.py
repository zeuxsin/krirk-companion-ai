"""
backend/tools/builtin/browser_tools.py
Automação de browser via Playwright (Fase 4 completa).

Mantém UMA sessão Chromium persistente (headed — o usuário vê o que a KRIRK
faz). A sessão abre sob demanda no primeiro browser_open e sobrevive entre
mensagens, permitindo fluxos multi-etapas: abrir → preencher → clicar → ler.

Requer: pip install playwright && playwright install chromium
"""
import asyncio

from backend.tools.base import Tool, ToolParam

# Sessão única do browser (módulo-level, protegida por lock)
_session: dict = {"pw": None, "browser": None, "page": None}
_lock = asyncio.Lock()

_PAGE_TIMEOUT_MS = 8000


# Ordem de tentativa: Edge (sempre presente no Win11) → Chrome → Chromium bundled.
# O Chromium bundled do Playwright pode falhar com erro SxS em algumas máquinas.
_LAUNCH_CHANNELS: tuple = ("msedge", "chrome", None)


async def _get_page(create: bool = True):
    """Retorna a página ativa, criando browser/página se necessário."""
    async with _lock:
        page = _session.get("page")
        if page is not None and not page.is_closed():
            return page
        if not create:
            return None

        from playwright.async_api import async_playwright

        if _session["pw"] is None:
            _session["pw"] = await async_playwright().start()

        browser = _session.get("browser")
        if browser is None or not browser.is_connected():
            last_err: Exception | None = None
            for channel in _LAUNCH_CHANNELS:
                try:
                    _session["browser"] = await _session["pw"].chromium.launch(
                        headless=False, channel=channel
                    )
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
            if last_err is not None:
                raise last_err

        page = await _session["browser"].new_page()
        page.set_default_timeout(_PAGE_TIMEOUT_MS)
        _session["page"] = page
        return page


async def _close_session() -> None:
    async with _lock:
        browser = _session.get("browser")
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass
        _session["browser"] = None
        _session["page"] = None


# ── browser_open ──────────────────────────────────────────────────────────────

async def _browser_open(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        page = await _get_page()
        await page.goto(url, wait_until="domcontentloaded")
        title = await page.title()
        return f"Página aberta no browser: '{title}' ({page.url})"
    except ModuleNotFoundError:
        return "[Erro] Playwright não instalado. Rode: pip install playwright && playwright install chromium"
    except Exception as e:
        return f"[Erro] Falha ao abrir {url}: {type(e).__name__}: {e}"


def make_browser_open() -> Tool:
    return Tool(
        name="browser_open",
        description=(
            "Abre uma URL no browser AUTOMATIZADO que a KRIRK controla (visível ao usuário). "
            "Primeiro passo de qualquer interação: depois use browser_read, browser_click, browser_fill."
        ),
        params=[ToolParam("url", "URL a abrir", "string")],
        func=_browser_open,
        timeout=30,
    )


# ── browser_read ──────────────────────────────────────────────────────────────

async def _browser_read(max_chars: int = 3000) -> str:
    page = await _get_page(create=False)
    if page is None:
        return "[Erro] Nenhuma página aberta. Use browser_open primeiro."
    try:
        title = await page.title()
        text = await page.inner_text("body")
        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        max_chars = max(500, min(10000, int(max_chars)))
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n... (truncado em {max_chars} caracteres)"
        return f"[{title}] ({page.url})\n\n{text}"
    except Exception as e:
        return f"[Erro] Falha ao ler a página: {type(e).__name__}: {e}"


def make_browser_read() -> Tool:
    return Tool(
        name="browser_read",
        description="Lê o texto visível da página atualmente aberta no browser automatizado.",
        params=[
            ToolParam("max_chars", "Máximo de caracteres a retornar", "int",
                      required=False, default=3000),
        ],
        func=_browser_read,
        timeout=30,
    )


# ── browser_click ─────────────────────────────────────────────────────────────

async def _browser_click(text: str) -> str:
    page = await _get_page(create=False)
    if page is None:
        return "[Erro] Nenhuma página aberta. Use browser_open primeiro."
    text = text.strip()
    if not text:
        return "[Erro] Informe o texto do elemento a clicar."
    try:
        # Estratégias em ordem: botão → link → qualquer elemento com o texto
        for locator in (
            page.get_by_role("button", name=text),
            page.get_by_role("link", name=text),
            page.get_by_text(text, exact=False),
        ):
            try:
                await locator.first.click(timeout=3000)
                await page.wait_for_load_state("domcontentloaded", timeout=5000)
                title = await page.title()
                return f"Cliquei em '{text}'. Página atual: '{title}' ({page.url})"
            except Exception:
                continue
        return f"[Erro] Não encontrei elemento clicável com o texto '{text}'. Use browser_read para ver a página."
    except Exception as e:
        return f"[Erro] Falha ao clicar: {type(e).__name__}: {e}"


def make_browser_click() -> Tool:
    return Tool(
        name="browser_click",
        description="Clica em um botão/link/elemento da página aberta, identificado pelo texto visível.",
        params=[ToolParam("text", "Texto visível do botão ou link a clicar", "string")],
        func=_browser_click,
        timeout=30,
    )


# ── browser_fill ──────────────────────────────────────────────────────────────

async def _browser_fill(field: str, value: str) -> str:
    page = await _get_page(create=False)
    if page is None:
        return "[Erro] Nenhuma página aberta. Use browser_open primeiro."
    field = field.strip()
    try:
        for locator in (
            page.get_by_label(field, exact=False),
            page.get_by_placeholder(field, exact=False),
            page.locator(f'input[name="{field}"]'),
            page.get_by_role("textbox", name=field),
            page.get_by_role("searchbox"),
        ):
            try:
                await locator.first.fill(value, timeout=3000)
                return f"Campo '{field}' preenchido com '{value}'."
            except Exception:
                continue
        return f"[Erro] Não encontrei campo '{field}'. Use browser_read para ver a página."
    except Exception as e:
        return f"[Erro] Falha ao preencher: {type(e).__name__}: {e}"


def make_browser_fill() -> Tool:
    return Tool(
        name="browser_fill",
        description=(
            "Preenche um campo de texto/formulário da página aberta. "
            "field = rótulo, placeholder ou name do campo; value = texto a digitar."
        ),
        params=[
            ToolParam("field", "Rótulo/placeholder/name do campo", "string"),
            ToolParam("value", "Valor a preencher", "string"),
        ],
        func=_browser_fill,
        timeout=30,
    )


# ── browser_close ─────────────────────────────────────────────────────────────

async def _browser_close() -> str:
    await _close_session()
    return "Browser automatizado fechado."


def make_browser_close() -> Tool:
    return Tool(
        name="browser_close",
        description="Fecha o browser automatizado da KRIRK.",
        params=[],
        func=_browser_close,
        timeout=15,
    )
