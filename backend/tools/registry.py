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

    def all(self) -> list[Tool]:
        """Todas as tools registradas (usado pela API pública /api/tools)."""
        return list(self._tools.values())

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


def build_default_registry(config: dict, memory=None, router=None, orchestrator=None) -> ToolRegistry:
    """
    Instancia e registra as ferramentas padrão conforme a whitelist do config.
    Importa as tools sob demanda para evitar dependências circulares.
    router: ProviderRouter — necessário para tools que usam LLM (ex: read_screen).
    orchestrator: para tools que mexem no estado da Krirk (ex: set_brain_state).
    """
    whitelist: list[str] = config.get("whitelist", [])
    registry = ToolRegistry()

    # Pastas extras liberadas no sandbox de arquivos (ex: C:\calendario)
    try:
        from backend.tools.builtin.file_tools import set_allowed_dirs
        set_allowed_dirs(config.get("allowed_dirs", []))
    except Exception as e:
        print(f"[KRIRK][tools] Erro ao configurar allowed_dirs: {e}")

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
            make_create_folder,
            make_move_file,
        )
        file_factories = {
            "read_file":       make_read_file,
            "list_directory":  make_list_directory,
            "search_files":    make_search_files,
            "write_file":      make_write_file,
            "create_folder":   make_create_folder,
            "move_file":       make_move_file,
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

    # ── Ponte com o Phantom System (agenda gamificada em C:\calendario) ──────
    cal_dir = config.get("calendar_dir")
    if cal_dir:
        try:
            from backend.tools.builtin.calendar_tools import (
                make_add_calendar_task,
                make_list_calendar_tasks,
            )
            if "add_calendar_task" in whitelist:
                registry.register(make_add_calendar_task(cal_dir))
            if "list_calendar_tasks" in whitelist:
                registry.register(make_list_calendar_tasks(cal_dir))
        except Exception as e:
            print(f"[KRIRK][tools] Erro ao carregar calendar_tools: {e}")

    # ── Tools de busca web ────────────────────────────────────────────────────
    try:
        from backend.tools.builtin.web_tools import make_web_search, make_search_meme
        web_factories = {
            "web_search": make_web_search,
            "search_meme": make_search_meme,
        }
        for name, factory in web_factories.items():
            if name in whitelist:
                registry.register(factory())
    except Exception as e:
        print(f"[KRIRK][tools] Erro ao carregar web_tools: {e}")

    # ── Tools de desktop (abrir apps/URLs, timer) ────────────────────────────
    try:
        from backend.tools.builtin.desktop_tools import (
            make_open_url,
            make_open_app,
            make_set_timer,
        )
        desktop_factories = {
            "open_url":  make_open_url,
            "open_app":  make_open_app,
            "set_timer": make_set_timer,
        }
        for name, factory in desktop_factories.items():
            if name in whitelist:
                registry.register(factory())
    except Exception as e:
        print(f"[KRIRK][tools] Erro ao carregar desktop_tools: {e}")

    # ── Tool de execução de código Python ────────────────────────────────────
    try:
        from backend.tools.builtin.code_tools import make_execute_python
        if "execute_python" in whitelist:
            registry.register(make_execute_python())
    except Exception as e:
        print(f"[KRIRK][tools] Erro ao carregar code_tools: {e}")

    # ── Tools de memória (busca semântica, busca temporal, memorizar, léxico) ─
    if memory is not None:
        try:
            from backend.tools.builtin.memory_tools import (
                make_search_memory,
                make_search_history,
                make_remember_fact,
                make_coin_term,
            )
            if "search_memory" in whitelist:
                registry.register(make_search_memory(memory))
            if "search_history" in whitelist:
                registry.register(make_search_history(memory))
            if "remember_this" in whitelist:
                registry.register(make_remember_fact(memory))
            if "coin_term" in whitelist:
                registry.register(make_coin_term(memory))
            if "set_brain_state" in whitelist and orchestrator is not None:
                from backend.tools.builtin.memory_tools import make_set_brain_state
                registry.register(make_set_brain_state(orchestrator))
        except Exception as e:
            print(f"[KRIRK][tools] Erro ao carregar memory_tools: {e}")

    # ── Tools de visão (OCR de tela — precisam do router) ────────────────────
    if router is not None:
        try:
            from backend.tools.builtin.vision_tools import make_read_screen
            if "read_screen" in whitelist:
                registry.register(make_read_screen(router))
        except Exception as e:
            print(f"[KRIRK][tools] Erro ao carregar vision_tools: {e}")

    # ── Tools de automação (teclado, janelas, web) ────────────────────────────
    try:
        from backend.tools.builtin.automation_tools import (
            make_press_hotkey,
            make_type_text,
            make_list_windows,
            make_focus_window,
            make_fetch_url,
        )
        automation_factories = {
            "press_hotkey": make_press_hotkey,
            "type_text":    make_type_text,
            "list_windows": make_list_windows,
            "focus_window": make_focus_window,
            "fetch_url":    make_fetch_url,
        }
        for name, factory in automation_factories.items():
            if name in whitelist:
                registry.register(factory())
    except Exception as e:
        print(f"[KRIRK][tools] Erro ao carregar automation_tools: {e}")

    # ── Tools de browser automatizado (Playwright) ────────────────────────────
    try:
        from backend.tools.builtin.browser_tools import (
            make_browser_open,
            make_browser_read,
            make_browser_click,
            make_browser_fill,
            make_browser_close,
        )
        browser_factories = {
            "browser_open":  make_browser_open,
            "browser_read":  make_browser_read,
            "browser_click": make_browser_click,
            "browser_fill":  make_browser_fill,
            "browser_close": make_browser_close,
        }
        for name, factory in browser_factories.items():
            if name in whitelist:
                registry.register(factory())
    except Exception as e:
        print(f"[KRIRK][tools] Erro ao carregar browser_tools: {e}")

    print(f"[KRIRK][tools] {len(registry.list_names())} ferramentas registradas: {registry.list_names()}")
    return registry
