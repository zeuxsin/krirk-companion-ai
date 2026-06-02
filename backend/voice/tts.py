import asyncio
import base64
import io
from typing import Optional


class TTSEngine:
    def __init__(self, config: dict):
        self._config = config
        self._enabled = config.get("enabled", True)
        self._voice = config.get("voice", "pt-BR-FranciscaNeural")
        self._rate = config.get("rate", "+5%")
        self._pitch = config.get("pitch", "+0Hz")

    async def generate(self, text: str) -> Optional[str]:
        """Returns base64-encoded MP3 audio, or None if TTS is disabled/failed."""
        if not self._enabled:
            return None
        cleaned = text.strip()
        if not cleaned:
            return None
        try:
            import edge_tts
            communicate = edge_tts.Communicate(
                text=cleaned,
                voice=self._voice,
                rate=self._rate,
                pitch=self._pitch,
            )
            audio_bytes = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes += chunk["data"]
            if audio_bytes:
                b64 = base64.b64encode(audio_bytes).decode("utf-8")
                print(f"[TTS] Gerado {len(audio_bytes):,} bytes ({len(b64):,} base64) — voz: {self._voice}")
                return b64
            else:
                print("[TTS] Nenhum byte de áudio recebido do edge-tts")
        except ImportError:
            print("[TTS] edge-tts não instalado. Execute: pip install edge-tts")
        except Exception as e:
            print(f"[TTS] Erro: {type(e).__name__}: {e}")
        return None

    def set_voice(self, voice: str):
        self._voice = voice

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
