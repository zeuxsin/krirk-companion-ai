"""
backend/tools/builtin/memory_tools.py
Ferramenta de busca semântica no histórico de conversas e fatos da KRIRK.

Usa o ChromaDB já integrado via MemoryManager — sem dependências extras.
O user_id é sempre "default" (app single-user).
"""
from backend.tools.base import Tool, ToolParam


def make_search_memory(memory) -> Tool:
    """
    Factory que recebe o MemoryManager via closure.
    Acessa o ChromaDB diretamente para busca por similaridade semântica.
    """

    async def _search_memory(query: str, max_results: str = "6") -> str:
        try:
            n = min(int(max_results), 10)
        except (ValueError, TypeError):
            n = 6

        try:
            results = memory.search_semantic("default", query, n=n)
        except Exception as e:
            return f"[Erro] Falha ao buscar na memória: {e}"

        if not results:
            return f"Não encontrei memórias relevantes sobre '{query}'."

        # Filtra resultados com score muito baixo (< 35%)
        results = [r for r in results if r.get("score", 0) >= 0.35]
        if not results:
            return f"Não encontrei memórias suficientemente relevantes sobre '{query}'."

        lines = []
        for r in results:
            role = r.get("role", "")
            tipo = r.get("type", "")

            if tipo == "fact":
                label = "Fato registrado"
            elif role == "user":
                label = "Você disse"
            elif role == "assistant":
                label = "Krirk disse"
            else:
                label = "Memória"

            score_pct = round(r.get("score", 0) * 100)
            text = (r.get("text") or "")[:300]
            lines.append(f"[{label} — {score_pct}% relevante]\n{text}")

        return "\n\n---\n\n".join(lines)

    return Tool(
        name="search_memory",
        description=(
            "Busca em conversas e fatos anteriores usando similaridade semântica. "
            "Use quando o usuário perguntar sobre o que já foi discutido, "
            "como 'você lembra quando falei sobre X?', 'o que eu te disse sobre Y?', "
            "'qual era meu projeto mesmo?', 'você sabe meu nome?'."
        ),
        params=[
            ToolParam(
                name="query",
                description="Assunto ou frase a buscar no histórico de conversas",
                type="string",
                required=True,
            ),
            ToolParam(
                name="max_results",
                description="Número máximo de memórias a retornar (padrão: 6, máximo: 10)",
                type="string",
                required=False,
                default="6",
            ),
        ],
        func=_search_memory,
    )


def make_search_history(memory) -> Tool:
    """Busca mensagens por PERÍODO de tempo ('o que falamos semana passada?')."""

    async def _search_history(days_back: int = 7, keyword: str = "") -> str:
        try:
            days = max(1, min(365, int(days_back)))
        except (ValueError, TypeError):
            days = 7

        try:
            msgs = memory.search_messages_by_period(
                "default", days_from=days, days_to=0,
                keyword=keyword.strip() or None,
            )
        except Exception as e:
            return f"[Erro] Falha ao buscar histórico: {e}"

        if not msgs:
            extra = f" sobre '{keyword}'" if keyword.strip() else ""
            return f"Não encontrei conversas{extra} nos últimos {days} dias."

        lines = []
        last_date = None
        total = 0
        for m in msgs:
            date = (m.get("created_at") or "")[:10]
            if date != last_date:
                try:
                    d = date.split("-")
                    lines.append(f"\n== {d[2]}/{d[1]}/{d[0]} ==")
                except IndexError:
                    lines.append(f"\n== {date} ==")
                last_date = date
            who = "Você" if m["role"] == "user" else "Krirk"
            content = m["content"][:150]
            lines.append(f"{who}: {content}")
            total += len(content)
            if total > 3000:
                lines.append("... (histórico truncado)")
                break

        return f"Conversas dos últimos {days} dias:\n" + "\n".join(lines)

    return Tool(
        name="search_history",
        description=(
            "Recupera as conversas de um período específico no passado. "
            "Use quando o usuário perguntar o que foi conversado num período: "
            "'o que falamos ontem?', 'sobre o que conversamos semana passada?', "
            "'o que discutimos esse mês?'."
        ),
        params=[
            ToolParam(
                name="days_back",
                description="Quantos dias atrás buscar (1=ontem/hoje, 7=última semana, 30=último mês)",
                type="int",
                required=False,
                default=7,
            ),
            ToolParam(
                name="keyword",
                description="Palavra-chave opcional para filtrar as mensagens",
                type="string",
                required=False,
                default="",
            ),
        ],
        func=_search_history,
    )


def make_remember_fact(memory) -> Tool:
    """Memoriza permanentemente algo que o usuário pediu explicitamente para lembrar."""

    async def _remember(fact: str) -> str:
        fact = fact.strip()
        if not fact:
            return "[Erro] Nenhum fato informado para memorizar."
        try:
            memory.pin_fact("default", fact)
            return f"Memorizado permanentemente: {fact}"
        except Exception as e:
            return f"[Erro] Falha ao memorizar: {e}"

    return Tool(
        name="remember_this",
        description=(
            "Salva permanentemente uma informação que o usuário pediu EXPLICITAMENTE "
            "para lembrar ('lembra disso', 'anota que...', 'não esquece que...'). "
            "Memórias fixadas nunca são esquecidas."
        ),
        params=[
            ToolParam(
                name="fact",
                description="O fato a memorizar, reescrito de forma clara e completa",
                type="string",
                required=True,
            ),
        ],
        func=_remember,
    )
