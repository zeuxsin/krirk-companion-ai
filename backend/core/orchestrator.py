import asyncio
import json
import re
from typing import AsyncGenerator

# Tags de raciocínio interno que alguns modelos (gemma3, qwen) incluem na resposta
_REASONING_RE = re.compile(
    r'<(thought|thinking|think|scratchpad|reflection)>.*?</\1>',
    re.DOTALL | re.IGNORECASE,
)

def _strip_reasoning(text: str) -> str:
    """Remove blocos de raciocínio interno do texto antes de exibir ao usuário."""
    cleaned = _REASONING_RE.sub('', text)
    return re.sub(r'\n{3,}', '\n\n', cleaned).strip()

from backend.core.personality import PersonalitySystem
from backend.core.state import AIState, AISystemState
from backend.memory.memory_manager import MemoryManager
from backend.emotions.emotion_engine import EmotionEngine
from backend.voice.tts import TTSEngine
from backend.voice.stt import STTEngine


class Orchestrator:
    def __init__(self, config: dict):
        self._config = config
        self._ollama_config = config["ollama"]
        self.personality = PersonalitySystem(config["personality"]["file"])
        self.state = AIState()
        self._vector_cfg = config.get("vector_memory", {
            "enabled": True, "search_results": 5, "min_score": 0.45
        })
        self.memory = MemoryManager(
            config["memory"]["db_path"],
            chroma_path=self._vector_cfg.get("chroma_path", "data/chroma"),
            ollama_base_url=self._ollama_config["base_url"],
            ollama_model=self._vector_cfg.get("embed_model", "nomic-embed-text"),
        )
        self.emotion = EmotionEngine(self.personality.get_initial_emotion())
        self.tts = TTSEngine(config["tts"])
        self.stt = STTEngine(config["stt"])

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

        # Memórias semânticas relevantes — busca no histórico completo via ChromaDB
        semantic_memories: list[str] = []
        if self._vector_cfg.get("enabled", True):
            raw = self.memory.search_semantic(
                user_id, query=message, n=self._vector_cfg.get("search_results", 5)
            )
            min_score = self._vector_cfg.get("min_score", 0.45)
            semantic_memories = [r["text"] for r in raw if r["score"] >= min_score]

        system_prompt = self.personality.build_system_prompt(
            current_emotion=self.emotion.current_emotion,
            user_facts=facts if facts else None,
            semantic_memories=semantic_memories if semantic_memories else None,
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

        # Remove blocos de raciocínio interno antes de salvar e reproduzir
        clean_response = _strip_reasoning(full_response)

        new_emotion = self.emotion.analyze_and_update(clean_response)
        self.memory.save_message(user_id, "assistant", clean_response, emotion=new_emotion)
        self.memory.update_intimacy(user_id, 0.1)

        audio_b64 = await self.tts.generate(clean_response)

        self.state.set(AISystemState.IDLE)

        yield {
            "type": "response_complete",
            "content": clean_response,   # versão limpa substitui o streaming no frontend
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

    async def extract_facts_bg(self, user_msg: str, assistant_msg: str, user_id: str) -> None:
        """
        Tarefa de background: usa o LLM para extrair fatos sobre o usuário
        a partir do último par de mensagens e salva automaticamente na memória.
        Executado de forma assíncrona — nunca bloqueia a resposta principal.
        """
        prompt = (
            "Analise esta conversa e extraia fatos concretos e permanentes sobre o USUÁRIO "
            "(não sobre a IA). Retorne APENAS um JSON com lista de fatos objetivos. "
            "Se não houver fatos relevantes, retorne {\"fatos\": []}.\n"
            "Exemplos de fatos bons: nome, profissão, cidade, hobby, preferência clara.\n"
            "NÃO inclua suposições nem fatos sobre a conversa em si.\n\n"
            f"Usuário: {user_msg}\n"
            f"Assistente: {assistant_msg}\n\n"
            "JSON:"
        )
        try:
            messages = [{"role": "user", "content": prompt}]
            raw = ""
            async for token in self._stream_ollama(messages):
                raw += token
                if len(raw) > 1000:  # limite de segurança
                    break

            match = re.search(r'\{.*?\}', raw, re.DOTALL)
            if not match:
                return
            data = json.loads(match.group())
            for fact in data.get("fatos", []):
                fact = fact.strip()
                if fact and len(fact) > 8:
                    self.memory.save_fact(user_id, fact)
                    print(f"[KRIRK] Fato extraído: {fact}")
        except Exception as e:
            print(f"[KRIRK] extract_facts_bg falhou: {e}")

    def get_status(self) -> dict:
        return {
            "state": self.state.current.value,
            "emotion": self.emotion.current_emotion,
            "model": self._ollama_config["model"],
            "tts_enabled": self._config["tts"]["enabled"],
            "stt_enabled": self._config["stt"]["enabled"],
        }
