"""
backend/tools/builtin/file_tools.py
Ferramentas de acesso ao sistema de arquivos: ler, listar, buscar, escrever.
"""
import glob as glob_module
from datetime import datetime
from pathlib import Path

from backend.tools.base import Tool, ToolParam

_HOME = Path.home()

_PATH_ALIASES: dict[str, Path] = {
    "desktop":           _HOME / "Desktop",
    "área de trabalho":  _HOME / "Desktop",
    "area de trabalho":  _HOME / "Desktop",
    "documentos":        _HOME / "Documents",
    "documents":         _HOME / "Documents",
    "downloads":         _HOME / "Downloads",
    "imagens":           _HOME / "Pictures",
    "pictures":          _HOME / "Pictures",
    "músicas":           _HOME / "Music",
    "music":             _HOME / "Music",
    "vídeos":            _HOME / "Videos",
    "videos":            _HOME / "Videos",
}


# Pastas EXTRAS liberadas via config (tools.allowed_dirs) — além do home.
# Cada uma vira alias pelo nome ("calendario" → C:\calendario).
_EXTRA_DIRS: list[Path] = []
_EXTRA_ALIASES: list[str] = []


def set_allowed_dirs(dirs: list[str]) -> None:
    """Configura pastas extras permitidas (chamado no boot pelo registry)."""
    global _EXTRA_DIRS
    for alias in _EXTRA_ALIASES:
        _PATH_ALIASES.pop(alias, None)
    _EXTRA_ALIASES.clear()
    _EXTRA_DIRS = []
    for d in dirs or []:
        try:
            p = Path(d).resolve()
        except OSError:
            continue
        _EXTRA_DIRS.append(p)
        alias = p.name.lower()
        if alias and alias not in _PATH_ALIASES:
            _PATH_ALIASES[alias] = p
            _EXTRA_ALIASES.append(alias)


def _resolve_aliases(path_str: str) -> str:
    """Resolve atalhos de caminho como 'Desktop' ou 'Área de Trabalho'."""
    key = path_str.strip().lower()
    if key in _PATH_ALIASES:
        return str(_PATH_ALIASES[key])
    # Prefixo: "desktop/arquivo.txt" → home/Desktop/arquivo.txt
    for alias, real in _PATH_ALIASES.items():
        if key.startswith(alias + "/") or key.startswith(alias + "\\"):
            remainder = path_str[len(alias):].lstrip("/\\")
            return str(real / remainder)
    return path_str


def _safe_path(path_str: str) -> Path | None:
    """
    Resolve o caminho e verifica que está dentro do home do usuário.
    Retorna None se o caminho for considerado inseguro.
    """
    try:
        p = Path(path_str).expanduser()
        # Caminho relativo ("agenda_x/arq.py"): resolver contra o Desktop —
        # nunca contra o cwd do backend, que fica fora do home e sempre falharia
        if not p.is_absolute():
            p = _HOME / "Desktop" / p
        p = p.resolve()
        if p.is_relative_to(_HOME):
            return p
        for extra in _EXTRA_DIRS:
            if p.is_relative_to(extra):
                return p
        return None
    except Exception:
        return None


# ── read_file ─────────────────────────────────────────────────────────────────

async def _read_file(path: str, max_lines: int = 100) -> str:
    safe = _safe_path(_resolve_aliases(path))
    if safe is None:
        return f"[Erro] Caminho não permitido (deve estar dentro de {_HOME}): {path}"
    if not safe.exists():
        return f"[Erro] Arquivo não encontrado: {safe}"
    if not safe.is_file():
        return f"[Erro] '{safe}' não é um arquivo."
    try:
        text = safe.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        truncated = len(lines) > max_lines
        content = "\n".join(lines[:max_lines])
        suffix = f"\n... (truncado em {max_lines} de {len(lines)} linhas)" if truncated else ""
        return content + suffix
    except Exception as e:
        return f"[Erro] Não foi possível ler '{safe}': {e}"


def make_read_file() -> Tool:
    return Tool(
        name="read_file",
        description="Lê o conteúdo de um arquivo de texto. Limitado a 100 linhas por padrão.",
        params=[
            ToolParam("path", "Caminho completo do arquivo (deve estar dentro do home do usuário)", "string"),
            ToolParam("max_lines", "Número máximo de linhas a retornar", "int", required=False, default=100),
        ],
        func=_read_file,
    )


# ── list_directory ─────────────────────────────────────────────────────────────

async def _list_directory(path: str) -> str:
    safe = _safe_path(_resolve_aliases(path))
    if safe is None:
        return f"[Erro] Caminho não permitido: {path}"
    if not safe.exists():
        return f"[Erro] Diretório não encontrado: {safe}"
    if not safe.is_dir():
        return f"[Erro] '{safe}' não é um diretório."
    try:
        entries = sorted(safe.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        if not entries:
            return f"Diretório vazio: {safe}"
        lines = [f"Conteúdo de {safe}:", ""]
        for entry in entries[:80]:  # max 80 entradas
            try:
                stat = entry.stat()
                size = f"{stat.st_size:,} bytes" if entry.is_file() else "<pasta>"
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M")
                prefix = "[DIR]" if entry.is_dir() else "[ARQ]"
                lines.append(f"  {prefix} {entry.name}  ({size}, {mtime})")
            except Exception:
                lines.append(f"  {entry.name}")
        if len(list(safe.iterdir())) > 80:
            lines.append("  ... (lista truncada em 80 itens)")
        return "\n".join(lines)
    except PermissionError:
        return f"[Erro] Sem permissão para acessar '{safe}'."
    except Exception as e:
        return f"[Erro] {e}"


def make_list_directory() -> Tool:
    return Tool(
        name="list_directory",
        description="Lista os arquivos e pastas de um diretório (nome, tamanho, data de modificação).",
        params=[
            ToolParam("path", "Caminho do diretório a listar", "string"),
        ],
        func=_list_directory,
    )


# ── search_files ───────────────────────────────────────────────────────────────

async def _search_files(directory: str, pattern: str) -> str:
    safe = _safe_path(_resolve_aliases(directory))
    if safe is None:
        return f"[Erro] Diretório não permitido: {directory}"
    if not safe.exists():
        return f"[Erro] Diretório não encontrado: {safe}"
    try:
        matches = list(safe.rglob(pattern))[:50]  # max 50 resultados
        if not matches:
            return f"Nenhum arquivo encontrado para '{pattern}' em {safe}"
        lines = [f"Resultados para '{pattern}' em {safe}:"]
        for m in matches:
            try:
                size = f"{m.stat().st_size:,} bytes" if m.is_file() else "<pasta>"
                lines.append(f"  {m.relative_to(safe)}  ({size})")
            except Exception:
                lines.append(f"  {m.name}")
        if len(matches) == 50:
            lines.append("  ... (limitado a 50 resultados)")
        return "\n".join(lines)
    except Exception as e:
        return f"[Erro] {e}"


def make_search_files() -> Tool:
    return Tool(
        name="search_files",
        description="Busca arquivos por padrão (glob) em um diretório. Ex: pattern='*.py', pattern='relatorio*'.",
        params=[
            ToolParam("directory", "Diretório onde buscar", "string"),
            ToolParam("pattern", "Padrão glob (ex: *.txt, relatorio*)", "string"),
        ],
        func=_search_files,
    )


# ── create_folder ─────────────────────────────────────────────────────────────

async def _create_folder(path: str) -> str:
    safe = _safe_path(_resolve_aliases(path))
    if safe is None:
        return f"[Erro] Caminho não permitido (deve estar dentro de {_HOME}): {path}"
    try:
        safe.mkdir(parents=True, exist_ok=True)
        return f"Pasta criada: {safe}"
    except Exception as e:
        return f"[Erro] Não foi possível criar a pasta '{safe}': {e}"


def make_create_folder() -> Tool:
    return Tool(
        name="create_folder",
        description="Cria uma pasta (e as pastas-pai, se necessário) dentro do home do usuário.",
        params=[
            ToolParam("path", "Caminho da pasta a criar (ex: desktop/minha_pasta)", "string"),
        ],
        func=_create_folder,
    )


# ── move_file ─────────────────────────────────────────────────────────────────

async def _move_file(source: str, destination: str) -> str:
    src = _safe_path(_resolve_aliases(source))
    dst = _safe_path(_resolve_aliases(destination))
    if src is None or dst is None:
        return f"[Erro] Caminho não permitido (origem e destino devem estar dentro de {_HOME})."
    if not src.exists():
        return f"[Erro] Arquivo/pasta de origem não encontrado: {src}"
    try:
        import shutil
        if dst.exists() and dst.is_dir():
            final = dst / src.name
        else:
            final = dst
            final.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(final))
        return f"Movido: {src.name} → {final}"
    except Exception as e:
        return f"[Erro] Não foi possível mover '{src}': {e}"


def make_move_file() -> Tool:
    return Tool(
        name="move_file",
        description=(
            "Move um arquivo ou pasta para outro local (dentro do home do usuário). "
            "Se o destino for uma pasta existente, o item vai para dentro dela."
        ),
        params=[
            ToolParam("source", "Caminho do arquivo/pasta a mover", "string"),
            ToolParam("destination", "Pasta de destino ou novo caminho completo", "string"),
        ],
        func=_move_file,
    )


# ── write_file ─────────────────────────────────────────────────────────────────
# Desativado na whitelist padrão — usar com cautela

async def _write_file(path: str, content: str) -> str:
    safe = _safe_path(_resolve_aliases(path))
    if safe is None:
        return f"[Erro] Caminho não permitido (deve estar dentro de {_HOME}): {path}"
    try:
        safe.parent.mkdir(parents=True, exist_ok=True)
        safe.write_text(content, encoding="utf-8")
        return f"Arquivo salvo: {safe} ({len(content)} caracteres)"
    except Exception as e:
        return f"[Erro] Não foi possível escrever em '{safe}': {e}"


def make_write_file() -> Tool:
    return Tool(
        name="write_file",
        description="Cria ou sobrescreve um arquivo com o conteúdo fornecido. Use com cuidado.",
        params=[
            ToolParam("path", "Caminho completo onde salvar o arquivo", "string"),
            ToolParam("content", "Conteúdo a escrever no arquivo", "string"),
        ],
        func=_write_file,
    )
