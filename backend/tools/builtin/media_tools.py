"""
backend/tools/builtin/media_tools.py
Ferramentas de controle de volume e mídia para Windows.

Volume:  PowerShell + C# inline (Windows Core Audio COM) — sem dependências extras
Mídia:   ctypes keybd_event — sem dependências extras
"""
import asyncio
import ctypes
import subprocess

from backend.tools.base import Tool, ToolParam


# ── Constantes de teclas de mídia (Windows Virtual Key codes) ─────────────────
_VK_VOLUME_MUTE  = 0xAD
_VK_MEDIA_NEXT   = 0xB0
_VK_MEDIA_PREV   = 0xB1
_VK_MEDIA_PLAY   = 0xB3   # play/pause toggle
_KEYEVENTF_KEYUP = 0x0002

# ── C# inline para Windows Core Audio (compile-once via Add-Type) ─────────────
# Vtable correta do IAudioEndpointVolume (Windows SDK — COM slots 3-15):
#  0: RegisterControlChangeNotify
#  1: UnregisterControlChangeNotify
#  2: GetChannelCount
#  3: SetMasterVolumeLevel (dB)
#  4: SetMasterVolumeLevelScalar  ← usamos
#  5: GetMasterVolumeLevel (dB)
#  6: GetMasterVolumeLevelScalar  ← usamos
#  7: SetChannelVolumeLevel (dB)
#  8: SetChannelVolumeLevelScalar
#  9: GetChannelVolumeLevel (dB)
# 10: GetChannelVolumeLevelScalar
# 11: SetMute                     ← usamos
# 12: GetMute                     ← usamos
_AUDIO_CS = r"""
using System;
using System.Runtime.InteropServices;

[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"),
 InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IAudioEndpointVolume {
    int a(); int b(); int c(); int d();                            // 0-3
    [PreserveSig] int SetMasterVolumeLevelScalar(float fLevel, Guid ctx); // 4
    int e();                                                       // 5
    [PreserveSig] int GetMasterVolumeLevelScalar(out float pfLevel); // 6
    int f(); int g(); int h(); int i();                            // 7-10
    [PreserveSig] int SetMute(bool bMute, Guid ctx);               // 11
    [PreserveSig] int GetMute(out bool pbMute);                    // 12
}

[Guid("D666063F-1587-4E43-81F1-B948E807363F"),
 InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IMMDevice {
    [PreserveSig]
    int Activate(ref Guid iid, uint clsCtx, IntPtr pActivationParams,
                 [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
}

[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"),
 InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IMMDeviceEnumerator {
    int f();
    [PreserveSig]
    int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice ppEndpoint);
}

[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
public class MMDeviceEnumeratorClass {}

public static class WinAudio {
    static IAudioEndpointVolume GetVol() {
        var e = (IMMDeviceEnumerator)(new MMDeviceEnumeratorClass());
        IMMDevice dev;
        e.GetDefaultAudioEndpoint(0, 1, out dev);
        var iid = typeof(IAudioEndpointVolume).GUID;
        object o;
        dev.Activate(ref iid, 23, IntPtr.Zero, out o);
        return (IAudioEndpointVolume)o;
    }

    public static string GetStatus() {
        var v = GetVol(); float f; bool m;
        v.GetMasterVolumeLevelScalar(out f);
        v.GetMute(out m);
        int pct = (int)Math.Round(f * 100);
        return pct + " " + (m ? "1" : "0");
    }

    public static void SetLevel(float scalar) {
        GetVol().SetMasterVolumeLevelScalar(scalar, Guid.Empty);
    }

    public static string ToggleMute() {
        var v = GetVol(); bool m;
        v.GetMute(out m);
        v.SetMute(!m, Guid.Empty);
        return m ? "ativado" : "silenciado";
    }
}
"""

# PowerShell script base: garante que o tipo WinAudio seja definido antes de usar
_PS_HEADER = f"""
if (-not ([System.Management.Automation.PSTypeName]'WinAudio').Type) {{
    Add-Type -TypeDefinition @'
{_AUDIO_CS}
'@ -ErrorAction Stop
}}
"""


def _ps_run(command: str, timeout: int = 8) -> str:
    """Executa PowerShell síncrono — deve ser chamado via run_in_executor."""
    full_cmd = _PS_HEADER + command
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", full_cmd],
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
        out = r.stdout.strip()
        err = r.stderr.strip()
        if err and not out:
            return f"[Erro] {err[:300]}"
        return out
    except subprocess.TimeoutExpired:
        return "[Erro] Timeout ao executar PowerShell."
    except Exception as e:
        return f"[Erro] {e}"


def _send_key(vk: int) -> None:
    """Simula pressionar e soltar uma tecla virtual do Windows via ctypes."""
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
    ctypes.windll.user32.keybd_event(vk, 0, _KEYEVENTF_KEYUP, 0)


# ── Funções síncronas ─────────────────────────────────────────────────────────

def _sync_get_volume() -> str:
    raw = _ps_run("[WinAudio]::GetStatus()")
    if "[Erro]" in raw:
        return raw
    try:
        pct, muted = raw.split()
        mute_str = " (silenciado)" if muted == "1" else ""
        return f"Volume atual: {pct}%{mute_str}"
    except Exception:
        return f"Volume: {raw}"


def _sync_set_volume(level: int) -> str:
    scalar = round(max(0, min(100, level)) / 100, 4)
    raw = _ps_run(f"[WinAudio]::SetLevel([float]{scalar})")
    if "[Erro]" in raw:
        return raw
    return f"Volume ajustado para {level}%."


def _sync_mute_toggle() -> str:
    raw = _ps_run("[WinAudio]::ToggleMute()")
    if "[Erro]" in raw:
        return raw
    if raw in ("ativado", "silenciado"):
        return f"Áudio {raw}."
    return f"Mute alternado: {raw}"


# ── Wrappers async ────────────────────────────────────────────────────────────

async def _get_volume() -> str:
    return await asyncio.get_event_loop().run_in_executor(None, _sync_get_volume)


async def _set_volume(level: str = "50") -> str:
    try:
        lvl = max(0, min(100, int(level)))
    except (ValueError, TypeError):
        return "[Erro] Nível inválido. Use um número de 0 a 100."
    return await asyncio.get_event_loop().run_in_executor(None, _sync_set_volume, lvl)


async def _mute_volume() -> str:
    return await asyncio.get_event_loop().run_in_executor(None, _sync_mute_toggle)


async def _media_play_pause() -> str:
    await asyncio.get_event_loop().run_in_executor(None, _send_key, _VK_MEDIA_PLAY)
    return "Play/Pause enviado."


async def _media_next() -> str:
    await asyncio.get_event_loop().run_in_executor(None, _send_key, _VK_MEDIA_NEXT)
    return "Próxima faixa."


async def _media_prev() -> str:
    await asyncio.get_event_loop().run_in_executor(None, _send_key, _VK_MEDIA_PREV)
    return "Faixa anterior."


# ── Factories ─────────────────────────────────────────────────────────────────

def make_get_volume() -> Tool:
    return Tool(
        name="get_volume",
        description="Retorna o volume atual do sistema em percentual e informa se está silenciado.",
        params=[],
        func=_get_volume,
    )


def make_set_volume() -> Tool:
    return Tool(
        name="set_volume",
        description="Ajusta o volume do sistema para um nível específico de 0 a 100.",
        params=[
            ToolParam("level", "Nível de volume desejado (0 = mudo, 100 = máximo)", "string"),
        ],
        func=_set_volume,
    )


def make_mute_volume() -> Tool:
    return Tool(
        name="mute_volume",
        description="Alterna o silêncio (mute) do sistema. Silencia se ligado, ativa se mudo.",
        params=[],
        func=_mute_volume,
    )


def make_media_play_pause() -> Tool:
    return Tool(
        name="media_play_pause",
        description="Envia o comando Play/Pause para o player de mídia ativo (Spotify, YouTube, etc.).",
        params=[],
        func=_media_play_pause,
    )


def make_media_next() -> Tool:
    return Tool(
        name="media_next",
        description="Pula para a próxima faixa ou vídeo no player de mídia ativo.",
        params=[],
        func=_media_next,
    )


def make_media_prev() -> Tool:
    return Tool(
        name="media_prev",
        description="Volta para a faixa ou vídeo anterior no player de mídia ativo.",
        params=[],
        func=_media_prev,
    )
