import asyncio
import json
from typing import AsyncGenerator

from backend.core.personality import PersonalitySystem
from backend.core.state import AIState, AISystemState
from backend.memory.memory_manager import MemoryManager
from backend.emotions.emotion_engine import EmotionEngine
from backend.voice.tts import TTSEngine
from backend.voice.stt import STTEngine


class Orchestrator:
    def __init__(self, config: dict):
        self._config = config
        self.personality = PersonalitySystem(config["personality"]["file"])
        self.state = AIState()
        self.memory = MemoryManager(config["memory"]["db_path"])
        self.emotion = EmotionEngine(self.personality.get_initial_emotion())
        self.tts = TTSEngine(config["tts"])
        self.stt = STTEngine(config["stt"])
        self._ollama_config = config["ollama"]

    async def _stream_ollama(
        self,
        messages: list[dict],
        images: list[str] | None = None,
    ) -> AsyncGenerator[str, None]:
        try:
            import ollama
            client = ollama.AsyncClient(host=self._ollama_config["base_url"])

            # Anexa imagens à última mensagem do usuário (para visão)
            if images:
                msgs = [m.copy() for m in messages]
                msgs[-1] = {**msgs[-1], "images": images}
            else:
                msgs = messages

            async for chunk in await client.chat(
                model=self._ollama_config["model"],
                messages=msgs,
                stream=True,
                options={
                    "temperature": self._ollama_config["temperature"],
                    "num_predict": self._ollama_config["max_tokens"],
                }
            ):
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content
        except ImportError:
            yield "[Erro: pacote 'ollama' não instalado. Execute: pip install ollama]"
        except Exception as e:
            yield f"[Erro ao conectar com Ollama: {e}. Certifique-se que o Ollama está rodando.]"

    async def process_text(
        self,
        message: str,
        user_id: str = "default",
    ) -> AsyncGenerator[dict, None]:
        """Main pipeline: text in → streaming tokens + complete response out."""

        self.state.set(AISystemState.THINKING)
        yield {"type": "status", "state": "thinking"}

        history = self.memory.get_recent_messages(
            user_id,
            limit=self._config["memory"]["short_term_limit"]
        )
        facts = self.memory.get_facts(user_id, limit=8)

        system_prompt = self.personality.build_system_prompt(
            current_emotion=self.emotion.current_emotion,
            user_facts=facts if facts else None,
        )

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        self.memory.save_message(user_id, "user", message)

        self.state.set(AISystemState.SPEAKING)
        yield {"type": "status", "state": "speaking"}

        full_response = ""
        async for token in self._stream_ollama(messages):
            full_response += token
            yield {"type": "token", "content": token}

        new_emotion = self.emotion.analyze_and_update(full_response)
        self.memory.save_message(user_id, "assistant", full_response, emotion=new_emotion)
        self.memory.update_intimacy(user_id, 0.1)

        audio_b64 = await self.tts.generate(full_response)

        self.state.set(AISystemState.IDLE)

        yield {
            "type": "response_complete",
            "content": full_response,
            "emotion": new_emotion,
            "audio": audio_b64,
        }
        yield {"type": "status", "state": "idle"}

    async def process_audio(
        self,
        audio_b64: str,
        user_id: str = "default",
    ) -> AsyncGenerator[dict, None]:
        """STT → text pipeline, then delegates to process_text."""

        self.state.set(AISystemState.LISTENING)
        yield {"type": "status", "state": "listening"}

        text = await self.stt.transcribe_base64(audio_b64)
        if not text:
            self.state.set(AISystemState.IDLE)
            yield {"type": "error", "message": "STT desabilitado ou sem resultado. Ative em configs/config.yaml ou use texto."}
            yield {"type": "status", "state": "idle"}
            return

        yield {"type": "transcription", "content": text}

        async for event in self.process_text(text, user_id):
            yield event

    async def process_screenshot(
        self,
        prompt: str = "Descreva o que você vê na minha tela. Seja específica e útil.",
        user_id: str = "default",
    ) -> AsyncGenerator[dict, None]:
        """Captura tela → envia para o modelo de visão → streama resposta."""

        self.state.set(AISystemState.THINKING)
        yield {"type": "status", "state": "thinking"}

        try:
            from backend.vision.capture import capture_screen, capture_thumbnail
            image_b64 = capture_screen()
            thumb_b64 = capture_thumbnail()
        except Exception as e:
            yield {"type": "error", "message": f"Erro ao capturar tela: {e}"}
            self.state.set(AISystemState.IDLE)
            yield {"type": "status", "state": "idle"}
            return

        # Envia thumbnail para o frontend exibir no chat
        yield {"type": "screenshot_taken", "thumbnail": thumb_b64}

        self.memory.save_message(user_id, "user", f"[Screenshot] {prompt}")

        system_prompt = self.personality.build_system_prompt(
            current_emotion=self.emotion.current_emotion,
            user_facts=self.memory.get_facts(user_id, limit=4),
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": prompt},
        ]

        self.state.set(AISystemState.SPEAKING)
        yield {"type": "status", "state": "speaking"}

        full_response = ""
        async for token in self._stream_ollama(messages, images=[image_b64]):
            full_response += token
            yield {"type": "token", "content": token}

        new_emotion = self.emotion.analyze_and_update(full_response)
        self.memory.save_message(user_id, "assistant", full_response, emotion=new_emotion)
        self.memory.update_intimacy(user_id, 0.1)

        audio_b64 = await self.tts.generate(full_response)
        self.state.set(AISystemState.IDLE)

        yield {
            "type": "response_complete",
            "content": full_response,
            "emotion": new_emotion,
            "audio": audio_b64,
        }
        yield {"type": "status", "state": "idle"}

    def get_status(self) -> dict:
        return {
            "state": self.state.current.value,
            "emotion": self.emotion.current_emotion,
            "model": self._ollama_config["model"],
            "tts_enabled": self._config["tts"]["enabled"],
            "stt_enabled": self._config["stt"]["enabled"],
        }
