import asyncio
import base64
import io
import re
from typing import Optional


def clean_for_tts(text: str) -> str:
    """
    Remove elementos que não devem ser lidos em voz alta:
    emojis, asteriscos/markdown, URLs, etc.
    """
    # Remove texto entre asteriscos (ex: *sorri*, **negrito**)
    text = re.sub(r'\*+[^*]*\*+', '', text)
    # Remove texto entre underscores (_italic_)
    text = re.sub(r'_[^_]*_', '', text)
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    # Remove emojis e símbolos Unicode fora do range de texto normal
    text = re.sub(
        r'[\U00010000-\U0010ffff'   # emojis / supplementary planes
        r'\U0001F300-\U0001F9FF'    # misc symbols & pictographs (já coberto acima)
        r'☀-➿'            # misc symbols (☀ ✓ etc.)
        r'⌀-⏿'            # misc technical
        r'︀-️'            # variation selectors
        r'‍'                   # zero-width joiner
        r']',
        '', text, flags=re.UNICODE
    )
    # Remove tags de tool_call (não devem ser lidas em voz alta)
    text = re.sub(r'<tool_call>.*?</tool_call>', '', text, flags=re.DOTALL)
    # Remove outras tags XML/HTML genéricas que possam sobrar
    text = re.sub(r'<[^>]+>', '', text)
    # Remove caracteres de formatação (hashes de markdown, backticks)
    text = re.sub(r'[`#]', '', text)
    # Colapsa espaços múltiplos e linhas em branco
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'  +', ' ', text)
    return text.strip()


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
        cleaned = clean_for_tts(text)
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
