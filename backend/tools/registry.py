"""
backend/tools/registry.py
Registro global de ferramentas disponíveis para a KRIRK.
"""
from .base import Tool


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def get_descriptions(self) -> str:
        """
        Retorna um bloco de texto pronto para ser injetado no system prompt,
        descrevendo todas as ferramentas registradas.
        """
        if not self._tools:
            return ""
        lines = []
        for tool in self._tools.values():
            lines.append(tool.format_for_prompt())
        return "\n".join(lines)


def build_default_registry(config: dict) -> ToolRegistry:
    """
    Instancia e registra as ferramentas padrão conforme a whitelist do config.
    Importa as tools sob demanda para evitar dependências circulares.
    """
    whitelist: list[str] = config.get("whitelist", [])
    registry = ToolRegistry()

    # ── Tools do sistema ──────────────────────────────────────────────────────
    try:
        from backend.tools.builtin.system_tools import (
            make_run_powershell,
            make_get_clipboard,
            make_set_clipboard,
            make_get_active_window,
            make_open_file,
            make_get_system_info,
            make_get_time,
        )
        system_factories = {
            "run_powershell":    make_run_powershell,
            "get_clipboard":     make_get_clipboard,
            "set_clipboard":     make_set_clipboard,
            "get_active_window": make_get_active_window,
            "open_file":         make_open_file,
            "get_system_info":   make_get_system_info,
            "get_time":          make_get_time,
        }
        for name, factory in system_factories.items():
            if name in whitelist:
                registry.register(factory())
    except Exception as e:
        print(f"[KRIRK][tools] Erro ao carregar system_tools: {e}")

    # ── Tools de arquivo ──────────────────────────────────────────────────────
    try:
        from backend.tools.builtin.file_tools import (
            make_read_file,
            make_list_directory,
            make_search_files,
            make_write_file,
        )
        file_factories = {
            "read_file":       make_read_file,
            "list_directory":  make_list_directory,
            "search_files":    make_search_files,
            "write_file":      make_write_file,
        }
        for name, factory in file_factories.items():
            if name in whitelist:
                registry.register(factory())
    except Exception as e:
        print(f"[KRIRK][tools] Erro ao carregar file_tools: {e}")

    # ── Tools de mídia / volume ───────────────────────────────────────────────
    try:
        from backend.tools.builtin.media_tools import (
            make_get_volume,
            make_set_volume,
            make_mute_volume,
            make_media_play_pause,
            make_media_next,
            make_media_prev,
        )
        media_factories = {
            "get_volume":        make_get_volume,
            "set_volume":        make_set_volume,
            "mute_volume":       make_mute_volume,
            "media_play_pause":  make_media_play_pause,
            "media_next":        make_media_next,
            "media_prev":        make_media_prev,
        }
        for name, factory in media_factories.items():
            if name in whitelist:
                registry.register(factory())
    except Exception as e:
        print(f"[KRIRK][tools] Erro ao carregar media_tools: {e}")

    # ── Tools de busca web ────────────────────────────────────────────────────
    try:
        from backend.tools.builtin.web_tools import make_web_search
        web_factories = {
            "web_search": make_web_search,
        }
        for name, factory in web_factories.items():
            if name in whitelist:
                registry.register(factory())
    except Exception as e:
        print(f"[KRIRK][tools] Erro ao carregar web_tools: {e}")

    print(f"[KRIRK][tools] {len(registry.list_names())} ferramentas registradas: {registry.list_names()}")
    return registry
