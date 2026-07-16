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
            "Busca em conversas anteriores usando similaridade semântica. "
            "Use quando o usuário perguntar sobre um ASSUNTO específico já discutido: "
            "'você lembra quando falei sobre X?', 'o que eu te disse sobre Y?'. "
            "NÃO use para dados do perfil (nome, profissão, interesses) — "
            "esses já estão no seu contexto."
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


def make_coin_term(memory) -> Tool:
    """Cunha um bordão/gíria interno — a Krirk cria ou o usuário oficializa."""

    async def _coin_term(term: str, meaning: str) -> str:
        term = term.strip()
        meaning = meaning.strip()
        if not term or not meaning:
            return "[Erro] Preciso do termo e do significado para cunhar o bordão."
        try:
            is_new = memory.add_term("default", term, meaning, origin="conversa", pinned=True)
            if is_new:
                return f"Bordão nosso cunhado: \"{term}\" = {meaning}"
            return f"Já tínhamos esse, reforcei: \"{term}\" = {meaning}"
        except Exception as e:
            return f"[Erro] Falha ao cunhar o bordão: {e}"

    return Tool(
        name="coin_term",
        description=(
            "Cria/oficializa uma GÍRIA ou BORDÃO interno de vocês dois (piada interna). "
            "Use quando o usuário disser 'esse é nosso bordão', 'a partir de agora X significa Y', "
            "ou quando VOCÊ inventar uma gíria nova que os dois vão adotar. "
            "term = a expressão; meaning = quando/como usar."
        ),
        params=[
            ToolParam("term", "A gíria/bordão (ex: 'farmar aura de neandertal')", "string"),
            ToolParam("meaning", "O que significa e quando usar", "string"),
        ],
        func=_coin_term,
    )


def make_set_brain_state(orchestrator) -> Tool:
    """Deixa a Krirk trocar o próprio 'humor de geração' (temperatura/top_p)."""

    async def _set_brain_state(mode: str) -> str:
        mode = mode.strip().lower()
        aliases = {"focado": "focused", "concentrada": "focused", "tranquila": "chill",
                   "de boa": "chill", "criativa": "creative", "criativo": "creative",
                   "caos": "chaos", "caótica": "chaos", "caotica": "chaos"}
        mode = aliases.get(mode, mode)
        if orchestrator.set_brain_state(mode):
            return f"Mudei meu estado mental para {mode}."
        return f"[Erro] Estado '{mode}' não existe. Use: focused, chill, creative, chaos."

    return Tool(
        name="set_brain_state",
        description=(
            "Muda o SEU próprio estado mental/humor de geração. Use quando quiser "
            "mudar sua vibe ou o usuário pedir ('fica mais criativa', 'foca', 'modo caos'). "
            "Modos: focused (precisa), chill (equilibrada), creative (solta), chaos (imprevisível)."
        ),
        params=[
            ToolParam("mode", "focused | chill | creative | chaos", "string"),
        ],
        func=_set_brain_state,
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
