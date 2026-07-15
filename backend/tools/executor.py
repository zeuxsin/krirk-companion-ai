"""
backend/tools/executor.py
Executa ferramentas de forma segura (com timeout e tratamento de erros).
"""
import json
import asyncio
from .registry import ToolRegistry


class ToolExecutor:
    def __init__(self, registry: ToolRegistry, timeout: float = 10.0):
        self._registry = registry
        self._timeout = timeout

    async def execute_from_json(self, json_str: str) -> str:
        """
        Recebe a string JSON extraída da tag <tool_call>,
        valida, executa a ferramenta com timeout e retorna o resultado como string.
        Em qualquer caso de erro retorna uma mensagem descritiva — nunca levanta exceção.
        """
        # ── Parse JSON ────────────────────────────────────────────────────────
        try:
            data = json.loads(json_str.strip())
        except json.JSONDecodeError as e:
            return f"[Erro] JSON inválido na chamada de ferramenta: {e}"

        tool_name = data.get("tool", "").strip()
        params    = data.get("params", {})

        if not tool_name:
            return "[Erro] Campo 'tool' ausente na chamada."

        # ── Busca no registry ─────────────────────────────────────────────────
        tool = self._registry.get(tool_name)
        if tool is None:
            available = ", ".join(self._registry.list_names()) or "nenhuma"
            return f"[Erro] Ferramenta '{tool_name}' não existe. Disponíveis: {available}"

        # ── Valida parâmetros obrigatórios ────────────────────────────────────
        for p in tool.params:
            if p.required and p.name not in params:
                return f"[Erro] Parâmetro obrigatório ausente: '{p.name}' para {tool_name}"

        # ── Filtra apenas os params que a tool aceita (ignora extras do LLM) ──
        valid_names = {p.name for p in tool.params}
        filtered = {k: v for k, v in params.items() if k in valid_names}
        # Aplica defaults para params opcionais não fornecidos
        for p in tool.params:
            if not p.required and p.name not in filtered and p.default is not None:
                filtered[p.name] = p.default

        # ── Executa com timeout (por-tool se definido, senão o padrão) ────────
        timeout = tool.timeout or self._timeout
        try:
            result = await asyncio.wait_for(
                tool.func(**filtered),
                timeout=timeout,
            )
            return str(result)
        except asyncio.TimeoutError:
            return f"[Erro] Ferramenta '{tool_name}' excedeu o tempo limite de {timeout}s."
        except Exception as e:
            return f"[Erro] Falha ao executar '{tool_name}': {type(e).__name__}: {e}"
