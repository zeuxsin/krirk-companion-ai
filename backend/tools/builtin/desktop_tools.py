"""
backend/tools/builtin/desktop_tools.py
Ferramentas de controle do desktop Windows.

- open_url   : abre URL no browser padrão
- open_app   : abre aplicativo pelo nome
- set_timer  : cria timer com alerta nativo (MessageBox) ao expirar
"""
import asyncio
import subprocess
import threading
from typing import Optional

from backend.tools.base import Tool


# ── open_url ─────────────────────────────────────────────────────────────────

async def _open_url(url: str) -> str:
    """Abre uma URL no browser padrão do Windows."""
    try:
        # Garante protocolo
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        subprocess.Popen(["start", url], shell=True)
        return f"URL aberta: {url}"
    except Exception as e:
        return f"[Erro] Não foi possível abrir a URL: {e}"


def make_open_url() -> Tool:
    return Tool(
        name="open_url",
        description=(
            "Abre uma URL no navegador padrão do Windows. "
            "Use quando o usuário pedir para abrir um site, link ou página web. "
            "Exemplos: 'abre o YouTube', 'vai no GitHub', 'abre google.com'."
        ),
        parameters={
            "url": {
                "type": "string",
                "description": "URL completa ou domínio a abrir (ex: 'youtube.com', 'https://github.com')",
            }
        },
        handler=_open_url,
    )


# ── open_app ─────────────────────────────────────────────────────────────────

# Mapeamento de nomes comuns → executável Windows
_APP_ALIASES: dict[str, str] = {
    "notepad":    "notepad.exe",
    "bloco de notas": "notepad.exe",
    "calculadora":"calc.exe",
    "calc":       "calc.exe",
    "explorador": "explorer.exe",
    "explorer":   "explorer.exe",
    "paint":      "mspaint.exe",
    "word":       "winword.exe",
    "excel":      "excel.exe",
    "powerpoint": "powerpnt.exe",
    "spotify":    "spotify.exe",
    "discord":    "discord.exe",
    "chrome":     "chrome.exe",
    "firefox":    "firefox.exe",
    "edge":       "msedge.exe",
    "vscode":     "code.exe",
    "vs code":    "code.exe",
    "terminal":   "wt.exe",
    "cmd":        "cmd.exe",
    "powershell": "powershell.exe",
    "obs":        "obs64.exe",
    "steam":      "steam.exe",
    "vlc":        "vlc.exe",
    "taskmgr":    "taskmgr.exe",
    "gerenciador de tarefas": "taskmgr.exe",
}


async def _open_app(app_name: str) -> str:
    """Abre um aplicativo do Windows pelo nome."""
    try:
        resolved = _APP_ALIASES.get(app_name.lower().strip(), app_name)
        subprocess.Popen(["start", "", resolved], shell=True)
        return f"Aplicativo aberto: {app_name}"
    except Exception as e:
        return f"[Erro] Não foi possível abrir '{app_name}': {e}"


def make_open_app() -> Tool:
    return Tool(
        name="open_app",
        description=(
            "Abre um aplicativo instalado no Windows pelo nome. "
            "Use quando o usuário pedir para abrir um programa. "
            "Exemplos: 'abre o Notepad', 'abre o Spotify', 'abre o VS Code', 'abre o Chrome'."
        ),
        parameters={
            "app_name": {
                "type": "string",
                "description": "Nome do aplicativo a abrir (ex: 'notepad', 'spotify', 'chrome', 'calc')",
            }
        },
        handler=_open_app,
    )


# ── set_timer ─────────────────────────────────────────────────────────────────

def _show_timer_alert(label: str, minutes: float) -> None:
    """Exibe MessageBox nativa do Windows quando o timer expira. Roda em thread."""
    try:
        import ctypes
        msg = f"Tempo esgotado!" + (f"\n{label}" if label else "")
        title = f"KRIRK — Timer ({int(minutes)} min)"
        # MB_OK | MB_ICONINFORMATION | MB_TOPMOST = 0x40040
        ctypes.windll.user32.MessageBoxW(0, msg, title, 0x40040)
    except Exception as e:
        print(f"[Timer] Erro ao exibir alerta: {e}")


async def _timer_task(minutes: float, label: str) -> None:
    """Aguarda N minutos em background e exibe alerta."""
    await asyncio.sleep(minutes * 60)
    threading.Thread(
        target=_show_timer_alert,
        args=(label, minutes),
        daemon=True,
    ).start()
    print(f"[Timer] Expirou: {label or f'{int(minutes)} min'}")


async def _set_timer(minutes: str, label: Optional[str] = "") -> str:
    """Inicia um timer assíncrono que alerta ao expirar."""
    try:
        mins = float(minutes)
        if mins <= 0 or mins > 1440:
            return "[Erro] Duração inválida. Use entre 0.1 e 1440 minutos (24h)."
        asyncio.create_task(_timer_task(mins, label or ""))
        descricao = label or f"{int(mins)} minuto{'s' if mins != 1 else ''}"
        return f"Timer de {descricao} iniciado. Vou te avisar quando acabar!"
    except ValueError:
        return f"[Erro] '{minutes}' não é um número válido de minutos."
    except Exception as e:
        return f"[Erro] Não foi possível criar o timer: {e}"


def make_set_timer() -> Tool:
    return Tool(
        name="set_timer",
        description=(
            "Cria um timer que dispara um alerta nativo do Windows ao expirar. "
            "Use quando o usuário pedir para colocar um cronômetro ou lembrete com tempo. "
            "Exemplos: 'coloca um timer de 25 minutos', 'me lembra em 10 minutos', "
            "'timer de 1h para o almoço'."
        ),
        parameters={
            "minutes": {
                "type": "string",
                "description": "Duração em minutos (pode ser decimal, ex: '25', '1.5', '90')",
            },
            "label": {
                "type": "string",
                "description": "Descrição opcional do timer (ex: 'Pausa Pomodoro', 'Almoço')",
            },
        },
        handler=_set_timer,
    )
