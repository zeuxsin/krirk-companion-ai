"""
backend/tools/builtin/web_tools.py
Ferramentas de busca na web para a KRIRK.
"""
import asyncio

from backend.tools.base import Tool, ToolParam


# ── Busca web via DuckDuckGo ──────────────────────────────────────────────────

def _sync_web_search(query: str, max_results: int = 4) -> str:
    """Busca síncrona via DuckDuckGo — chamada via run_in_executor."""
    try:
        # ddgs v9+ — importação direta sem context manager
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS  # fallback para versão antiga

        ddgs = DDGS()
        # Em v9+ text() pode retornar generator ou list; converte explicitamente
        raw = ddgs.text(query, max_results=max_results)
        results = list(raw) if raw else []

        if not results:
            return f"Nenhum resultado encontrado para: {query}"

        lines = []
        for r in results:
            title = r.get("title") or r.get("Title") or "Sem título"
            href  = r.get("href")  or r.get("url") or r.get("link") or ""
            body  = r.get("body")  or r.get("snippet") or r.get("description") or ""
            body  = body[:300]
            lines.append(f"**{title}**\n{href}\n{body}")

        return "\n\n---\n\n".join(lines)

    except ImportError:
        return "[Erro] Pacote ddgs não instalado. Execute: pip install ddgs"
    except Exception as e:
        return f"[Erro] Falha na busca web: {type(e).__name__}: {e}"


async def _web_search(query: str, max_results: str = "4") -> str:
    loop = asyncio.get_event_loop()
    try:
        n = min(int(max_results), 6)   # máximo de 6 resultados
    except (ValueError, TypeError):
        n = 4
    return await loop.run_in_executor(None, _sync_web_search, query, n)


async def _search_meme(query: str) -> str:
    """Busca o significado/contexto de um meme ou gíria da internet."""
    loop = asyncio.get_event_loop()
    tuned = f"significado meme gíria {query} explicação"
    result = await loop.run_in_executor(None, _sync_web_search, tuned, 4)
    if result.startswith("[Erro]") or result.startswith("Nenhum"):
        return result
    return f"Sobre o meme/gíria '{query}':\n\n{result}"


def make_search_meme() -> Tool:
    return Tool(
        name="search_meme",
        description=(
            "Pesquisa o significado, origem ou contexto de um MEME ou GÍRIA da internet. "
            "Use quando o usuário perguntar 'o que significa o meme X', 'que gíria é essa', "
            "ou quando você quiser entender uma referência cultural para acompanhar o papo."
        ),
        params=[
            ToolParam("query", "O meme ou gíria a investigar", "string"),
        ],
        func=_search_meme,
    )


def make_web_search() -> Tool:
    return Tool(
        name="web_search",
        description=(
            "Busca informações atualizadas na internet usando DuckDuckGo. "
            "Use quando o usuário perguntar sobre eventos recentes, clima, preços, "
            "notícias, lançamentos ou qualquer informação que exija dados atualizados."
        ),
        params=[
            ToolParam(
                name="query",
                description="Termo de busca em português ou inglês",
                type="string",
                required=True,
            ),
            ToolParam(
                name="max_results",
                description="Número de resultados a retornar (padrão: 4, máximo: 6)",
                type="string",
                required=False,
                default="4",
            ),
        ],
        func=_web_search,
    )
