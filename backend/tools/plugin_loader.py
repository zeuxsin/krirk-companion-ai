"""
backend/tools/plugin_loader.py
Sistema de plugins da KRIRK (Fase 6).

Cada arquivo plugins/*.py é um plugin. O contrato é mínimo:

    # plugins/meu_plugin.py
    from backend.tools.base import Tool, ToolParam

    def register(registry):
        async def _minha_tool(param: str) -> str:
            return f"resultado: {param}"
        registry.register(Tool(
            name="minha_tool",
            description="O que a ferramenta faz (o LLM lê isto).",
            params=[ToolParam("param", "descrição do parâmetro", "string")],
            func=_minha_tool,
        ))

Arquivos começando com "_" são ignorados. Erros em um plugin não afetam
os demais nem o boot do backend.
"""
import importlib.util
from pathlib import Path


def load_plugins(registry, plugins_dir: str = "plugins") -> list[str]:
    """
    Carrega todos os plugins de plugins_dir no registry.
    Retorna a lista de nomes de plugins carregados com sucesso.
    """
    loaded: list[str] = []
    pdir = Path(plugins_dir)
    if not pdir.is_dir():
        return loaded

    for file in sorted(pdir.glob("*.py")):
        if file.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(
                f"krirk_plugin_{file.stem}", file
            )
            if spec is None or spec.loader is None:
                print(f"[KRIRK][plugins] {file.name}: spec inválido, ignorado")
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if not hasattr(module, "register"):
                print(f"[KRIRK][plugins] {file.name} ignorado: sem função register(registry)")
                continue

            before = set(registry.list_names())
            module.register(registry)
            new_tools = sorted(set(registry.list_names()) - before)
            loaded.append(file.stem)
            print(f"[KRIRK][plugins] {file.stem} carregado — tools: {new_tools or '(nenhuma)'}")
        except Exception as e:
            print(f"[KRIRK][plugins] Erro ao carregar {file.name}: {type(e).__name__}: {e}")

    return loaded
