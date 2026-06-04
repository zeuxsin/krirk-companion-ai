"""
backend/tools/builtin/system_tools.py
Ferramentas de sistema: PowerShell, clipboard, janela ativa, abrir arquivo, info do sistema.
"""
import asyncio
import os
import subprocess
from datetime import datetime
from pathlib import Path

from backend.tools.base import Tool, ToolParam


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _run_ps(command: str, timeout: float = 8.0) -> str:
    """Executa um comando PowerShell e retorna stdout + stderr (max 2000 chars)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "powershell", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass",
            "-Command", command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        out = stdout.decode("utf-8", errors="replace").strip()
        err = stderr.decode("utf-8", errors="replace").strip()
        result = out
        if err:
            result += f"\n[stderr] {err}"
        return result[:2000] if result else "(sem saída)"
    except asyncio.TimeoutError:
        return "[Erro] Timeout ao executar PowerShell."
    except Exception as e:
        return f"[Erro] {e}"


# ── run_powershell ─────────────────────────────────────────────────────────────

async def _run_powershell(command: str) -> str:
    return await _run_ps(command)


def make_run_powershell() -> Tool:
    return Tool(
        name="run_powershell",
        description="Executa um comando PowerShell no computador do usuário e retorna o resultado.",
        params=[
            ToolParam("command", "Comando PowerShell a executar", "string"),
        ],
        func=_run_powershell,
    )


# ── get_clipboard ──────────────────────────────────────────────────────────────

def _clipboard_get_sync() -> str:
    """Lê clipboard de forma síncrona — deve ser chamada via run_in_executor."""
    # Tenta win32clipboard (mais confiável no Windows)
    try:
        import win32clipboard  # type: ignore
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                return text[:1000] if text else "(área de transferência vazia)"
        finally:
            win32clipboard.CloseClipboard()
        return "(área de transferência vazia)"
    except ImportError:
        pass

    # Tenta pyperclip
    try:
        import pyperclip  # type: ignore
        text = pyperclip.paste()
        return text[:1000] if text else "(área de transferência vazia)"
    except Exception:
        pass

    # Fallback: PowerShell síncrono
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", "Get-Clipboard"],
            capture_output=True, text=True, timeout=5,
            encoding="utf-8", errors="replace",
        )
        text = result.stdout.strip()
        return text[:1000] if text else "(área de transferência vazia)"
    except Exception as e:
        return f"[Erro ao ler clipboard: {e}]"


async def _get_clipboard() -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _clipboard_get_sync)


def make_get_clipboard() -> Tool:
    return Tool(
        name="get_clipboard",
        description="Lê o conteúdo atual da área de transferência do usuário.",
        params=[],
        func=_get_clipboard,
    )


# ── set_clipboard ──────────────────────────────────────────────────────────────

def _clipboard_set_sync(text: str) -> str:
    """Escreve clipboard de forma síncrona."""
    try:
        import win32clipboard  # type: ignore
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
        return f"Texto copiado para a área de transferência ({len(text)} caracteres)."
    except ImportError:
        pass

    try:
        import pyperclip  # type: ignore
        pyperclip.copy(text)
        return f"Texto copiado para a área de transferência ({len(text)} caracteres)."
    except Exception:
        pass

    # Fallback PowerShell
    try:
        safe = text.replace("'", "''")
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", f"Set-Clipboard -Value '{safe}'"],
            timeout=5,
        )
        return f"Texto copiado para a área de transferência ({len(text)} caracteres)."
    except Exception as e:
        return f"[Erro ao escrever clipboard: {e}]"


async def _set_clipboard(text: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _clipboard_set_sync(text))


def make_set_clipboard() -> Tool:
    return Tool(
        name="set_clipboard",
        description="Copia um texto para a área de transferência do usuário.",
        params=[
            ToolParam("text", "Texto a copiar", "string"),
        ],
        func=_set_clipboard,
    )


# ── get_active_window ──────────────────────────────────────────────────────────

async def _get_active_window() -> str:
    result = await _run_ps(
        "Add-Type -AssemblyName Microsoft.VisualBasic; "
        "[Microsoft.VisualBasic.Interaction]::AppActivate((Get-Process | "
        "Where-Object { $_.MainWindowTitle -ne '' } | "
        "Sort-Object CPU -Descending | Select-Object -First 5 | "
        "ForEach-Object { $_.MainWindowTitle }) -join \"`n\")"
    )
    if "[Erro]" in result:
        # Fallback mais simples
        result = await _run_ps(
            "Get-Process | Where-Object { $_.MainWindowTitle -ne '' } | "
            "Sort-Object CPU -Descending | Select-Object -First 5 -ExpandProperty MainWindowTitle"
        )
    return result or "(nenhuma janela detectada)"


def make_get_active_window() -> Tool:
    return Tool(
        name="get_active_window",
        description="Retorna o título das janelas abertas no computador (top 5 por uso de CPU).",
        params=[],
        func=_get_active_window,
    )


# ── open_file ──────────────────────────────────────────────────────────────────

async def _open_file(path: str) -> str:
    try:
        os.startfile(path)  # type: ignore[attr-defined]
        return f"Abrindo: {path}"
    except AttributeError:
        # Não-Windows
        import subprocess
        subprocess.Popen(["xdg-open", path])
        return f"Abrindo: {path}"
    except Exception as e:
        return f"[Erro] Não foi possível abrir '{path}': {e}"


def make_open_file() -> Tool:
    return Tool(
        name="open_file",
        description="Abre um arquivo, pasta ou URL com o programa padrão do Windows.",
        params=[
            ToolParam("path", "Caminho do arquivo, pasta ou URL a abrir", "string"),
        ],
        func=_open_file,
    )


# ── get_time ──────────────────────────────────────────────────────────────────

_DAYS_PT = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
            "sexta-feira", "sábado", "domingo"]

async def _get_time() -> str:
    n = datetime.now()
    day = _DAYS_PT[n.weekday()]
    return f"{day}, {n.day:02d}/{n.month:02d}/{n.year}, {n.hour:02d}:{n.minute:02d}"


def make_get_time() -> Tool:
    return Tool(
        name="get_time",
        description="Retorna a data e hora atual. Use para perguntas como 'que horas são?', 'que dia é hoje?'.",
        params=[],
        func=_get_time,
    )


# ── get_system_info ────────────────────────────────────────────────────────────

async def _get_system_info() -> str:
    now = datetime.now()
    info_lines = [
        f"Data e hora: {now.strftime('%A, %d/%m/%Y %H:%M:%S')}",
    ]

    # CPU e RAM via PowerShell (mais confiável no Windows sem psutil)
    ps_result = await _run_ps(
        "$cpu = (Get-CimInstance Win32_Processor | Measure-Object LoadPercentage -Average).Average; "
        "$mem = Get-CimInstance Win32_OperatingSystem; "
        "$used = [math]::Round(($mem.TotalVisibleMemorySize - $mem.FreePhysicalMemory) / 1MB, 1); "
        "$total = [math]::Round($mem.TotalVisibleMemorySize / 1MB, 1); "
        "$disk = Get-PSDrive C; "
        "$free = [math]::Round($disk.Free / 1GB, 1); "
        "Write-Output \"CPU: $cpu%`nRAM: ${used}GB / ${total}GB`nDisco C: livre ${free}GB\""
    )
    if "[Erro]" not in ps_result:
        info_lines.append(ps_result)
    else:
        # Fallback com psutil se disponível
        try:
            import psutil  # type: ignore
            cpu = psutil.cpu_percent(interval=0.5)
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage("C:\\")
            info_lines += [
                f"CPU: {cpu:.0f}%",
                f"RAM: {ram.used / 1e9:.1f}GB / {ram.total / 1e9:.1f}GB ({ram.percent:.0f}%)",
                f"Disco C: livre {disk.free / 1e9:.1f}GB de {disk.total / 1e9:.1f}GB",
            ]
        except ImportError:
            info_lines.append("(CPU/RAM indisponível — instale psutil ou verifique PowerShell)")

    return "\n".join(info_lines)


def make_get_system_info() -> Tool:
    return Tool(
        name="get_system_info",
        description="Retorna informações do sistema: data/hora atual, uso de CPU, RAM e espaço em disco.",
        params=[],
        func=_get_system_info,
    )
