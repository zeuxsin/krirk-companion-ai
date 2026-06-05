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
