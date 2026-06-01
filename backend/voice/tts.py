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
        if not self._enabled or not text.strip():
            return None
        try:
            import edge_tts
            communicate = edge_tts.Communicate(
                text=text,
                voice=self._voice,
                rate=self._rate,
                pitch=self._pitch,
            )
            audio_bytes = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes += chunk["data"]
            if audio_bytes:
                return base64.b64encode(audio_bytes).decode("utf-8")
        except ImportError:
            pass
        except Exception as e:
            print(f"[TTS] Error: {e}")
        return None

    def set_voice(self, voice: str):
        self._voice = voice

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
