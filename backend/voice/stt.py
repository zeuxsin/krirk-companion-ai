import base64
import io
from typing import Optional


class STTEngine:
    """Speech-to-Text usando faster-whisper (requer Python <=3.12 e GPU/CPU).

    Fallback: retorna None se não disponível.
    """

    def __init__(self, config: dict):
        self._config = config
        self._enabled = config.get("enabled", False)
        self._model = None
        self._model_name = config.get("model", "base")
        self._language = config.get("language", "pt")

        if self._enabled:
            self._load_model()

    def _load_model(self):
        try:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self._model_name,
                device="auto",
                compute_type="int8",
            )
            print(f"[STT] Whisper model '{self._model_name}' loaded")
        except ImportError:
            print("[STT] faster-whisper not installed. STT disabled.")
            self._enabled = False
        except Exception as e:
            print(f"[STT] Failed to load model: {e}")
            self._enabled = False

    async def transcribe_bytes(self, audio_data: bytes) -> Optional[str]:
        """Transcribes raw WAV audio bytes. Returns text or None."""
        if not self._enabled or self._model is None:
            return None
        try:
            import tempfile, os
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name
            segments, _ = self._model.transcribe(
                tmp_path,
                language=self._language,
                beam_size=5,
            )
            os.unlink(tmp_path)
            text = " ".join(s.text for s in segments).strip()
            return text if text else None
        except Exception as e:
            print(f"[STT] Transcription error: {e}")
            return None

    async def transcribe_base64(self, b64_audio: str) -> Optional[str]:
        audio_bytes = base64.b64decode(b64_audio)
        return await self.transcribe_bytes(audio_bytes)

    @property
    def enabled(self) -> bool:
        return self._enabled
