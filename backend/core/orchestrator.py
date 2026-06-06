import asyncio
import json
import re
from pathlib import Path
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

_HOME = str(Path.home()).replace("\\", "/")


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

        # ── Sistema de ferramentas (Fase 4 — dual-model) ──────────────────────
        self._tool_cfg = config.get("tools", {"enabled": False})
        self.tool_registry = None
        self.tool_executor = None
        if self._tool_cfg.get("enabled", False):
            try:
                from backend.tools.registry import build_default_registry
                from backend.tools.executor import ToolExecutor
                self.tool_registry = build_default_registry(self._tool_cfg, memory=self.memory)
                self.tool_executor = ToolExecutor(
                    self.tool_registry,
                    timeout=self._tool_cfg.get("timeout_seconds", 10),
                )
                tool_model = self._tool_cfg.get("tool_model", self._ollama_config["model"])
                print(f"[KRIRK][tools] Modelo de roteamento: {tool_model}")
            except Exception as e:
                print(f"[KRIRK][tools] Falha ao inicializar ferramentas: {e}")

    # ── Streaming com o modelo principal (gemma3 — chat/personalidade) ────────

    async def _stream_ollama(
        self,
        messages: list[dict],
        images: list[str] | None = None,
    ) -> AsyncGenerator[str, None]:
        try:
            import ollama
            client = ollama.AsyncClient(host=self._ollama_config["base_url"])

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

    # ── Streaming com o modelo de tools (qwen2.5-coder — roteamento estruturado)

    async def _stream_ollama_tool(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        """Usa o modelo especializado em tools para gerar JSON estruturado."""
        try:
            import ollama
            tool_model = self._tool_cfg.get("tool_model", self._ollama_config["model"])
            client = ollama.AsyncClient(host=self._ollama_config["base_url"])
            async for chunk in await client.chat(
                model=tool_model,
                messages=messages,
                stream=True,
                options={
                    "temperature": 0.1,    # baixa temperatura para JSON preciso
                    "num_predict": 256,    # resposta curta — apenas o JSON de decisão
                }
            ):
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content
        except Exception as e:
            print(f"[KRIRK][tools] _stream_ollama_tool falhou: {e}")

    # ── Decisão de tool (Fase 1) ──────────────────────────────────────────────

    async def _decide_tool(self, message: str, history: list | None = None) -> dict | None:
        """
        Usa qwen2.5-coder para decidir QUAL ferramenta usar, se alguma.
        Retorna dict {"tool": str, "params": dict} ou None se nenhuma tool for necessária.
        """
        if not (self.tool_registry and self.tool_executor):
            return None

        tool_desc = self.tool_registry.get_descriptions()

        # Inclui as últimas 4 mensagens do histórico para dar contexto ao roteador
        # (ex: "abre de novo" — o qwen precisa saber que Notepad estava aberto antes)
        history_context = ""
        if history:
            recent = history[-4:]  # últimas 4 trocas
            lines = []
            for m in recent:
                role = "User" if m["role"] == "user" else "Assistant"
                lines.append(f"{role}: {m['content'][:120]}")
            if lines:
                history_context = "Recent conversation:\n" + "\n".join(lines) + "\n\n"

        planning_prompt = (
            "You are a tool router for a desktop AI assistant. "
            "Analyze the user's message and decide which tool to use, if any.\n\n"
            f"User home directory: {_HOME}\n\n"
            f"Available tools:\n{tool_desc}\n\n"
            f"{history_context}"
            f"User message: {message}\n\n"
            "Rules:\n"
            "- If a tool is needed, respond with ONLY valid JSON (no markdown, no explanation):\n"
            '  {"tool": "exact_tool_name", "params": {"param_name": "value"}}\n'
            "- If no tool is needed, respond with exactly: none\n"
            "- NEVER use a tool for: greetings, thanks, short replies, confirmations, "
            "reactions ('ok', 'isso aí', 'certo', 'sim', 'não', 'ótimo', 'entendi', 'legal', "
            "'exato', 'claro', 'show', 'beleza', 'tá'), opinions, or casual chat.\n"
            "- search_memory: ONLY use when the user is EXPLICITLY asking to recall past "
            "conversations ('você lembra?', 'o que eu te falei?', 'qual era mesmo?'). "
            "Do NOT use for confirmations or reactions to what was just said.\n"
            "- Use the EXACT tool name as listed above. Do not translate to Portuguese.\n"
            "- For run_powershell, write a complete PowerShell command.\n"
            "- For list_directory and read_file, use the full absolute path.\n"
            "- Use conversation history to resolve references like 'again', 'de novo', 'novamente'.\n"
        )

        raw = ""
        async for token in self._stream_ollama_tool([
            {"role": "user", "content": planning_prompt}
        ]):
            raw += token
            if len(raw) > 512:
                break

        raw = raw.strip()
        print(f"[KRIRK][tools] Decisão do roteador: {raw[:150]}")

        # "none" ou resposta vazia → sem tool
        if not raw or raw.lower().startswith("none"):
            return None

        # Extrai o primeiro bloco JSON da resposta (ignora texto extra)
        try:
            match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}', raw, re.DOTALL)
            if match:
                data = json.loads(match.group())
                if "tool" in data and "params" in data:
                    return data
        except Exception as e:
            print(f"[KRIRK][tools] Falha ao parsear decisão: {e} — raw: {raw[:100]}")

        return None

    # ── Pipeline principal ────────────────────────────────────────────────────

    async def process_text(
        self,
        message: str,
        user_id: str = "default",
    ) -> AsyncGenerator[dict, None]:
        """
        Pipeline de duas fases:
          Fase 1 — qwen2.5-coder decide qual tool usar (se alguma)
          Fase 2 — gemma3 gera a resposta final com personalidade
        """

        self.state.set(AISystemState.THINKING)
        yield {"type": "status", "state": "thinking"}

        history = self.memory.get_recent_messages(
            user_id,
            limit=self._config["memory"]["short_term_limit"]
        )
        facts = self.memory.get_facts(user_id, limit=8)

        # Memórias semânticas relevantes via ChromaDB
        semantic_memories: list[str] = []
        if self._vector_cfg.get("enabled", True):
            raw = self.memory.search_semantic(
                user_id, query=message, n=self._vector_cfg.get("search_results", 5)
            )
            min_score = self._vector_cfg.get("min_score", 0.45)
            semantic_memories = [r["text"] for r in raw if r["score"] >= min_score]

        # ── FASE 1: Roteamento via qwen2.5-coder ─────────────────────────────
        tool_result_context = ""
        if self._tool_cfg.get("enabled", False) and self.tool_executor:
            tool_decision = await self._decide_tool(message, history)

            if tool_decision:
                tool_name = tool_decision.get("tool", "ferramenta")

                self.state.set(AISystemState.EXECUTING)
                yield {"type": "status", "state": "executing"}
                yield {"type": "tool_call", "tool": tool_name, "raw": json.dumps(tool_decision)}

                result = await self.tool_executor.execute_from_json(
                    json.dumps(tool_decision)
                )
                print(f"[KRIRK][tools] {tool_name} → {result[:150]}")
                yield {"type": "tool_result", "tool": tool_name, "result": result}

                tool_result_context = (
                    f"Consultei {tool_name} e o resultado foi:\n\n"
                    f"{result}"
                )

        # ── FASE 2: Resposta final via gemma3 ─────────────────────────────────
        # Perfil estruturado do usuário (nome, profissão, etc.)
        profile = self.memory.get_profile(user_id)
        profile_text = self.memory.profile.to_prompt_text(profile)

        # Knowledge Graph — relações permanentes (entidades + verbos)
        kg_cfg = self._config.get("knowledge_graph", {})
        kg_text: str | None = None
        if kg_cfg.get("enabled", True):
            max_rel = kg_cfg.get("max_relations_in_prompt", 25)
            kg_text = self.memory.kg.to_prompt_text(user_id, max_relations=max_rel)

        system_prompt = self.personality.build_system_prompt(
            current_emotion=self.emotion.current_emotion,
            user_profile=profile_text,
            user_facts=facts if facts else None,
            semantic_memories=semantic_memories if semantic_memories else None,
            knowledge_graph=kg_text,
        )

        llm_messages = [{"role": "system", "content": system_prompt}]
        llm_messages.extend(history)
        llm_messages.append({"role": "user", "content": message})

        if tool_result_context:
            # Injeta o resultado como turno de conversa multi-turn:
            # assistant "já consultou" → user pede para responder
            # Isso força o modelo a usar o resultado em vez de inventar
            llm_messages.append({
                "role": "assistant",
                "content": tool_result_context,
            })

            # Instrução de resposta varia por tipo de tool:
            # web_search → resumo natural dos resultados
            # outros     → resposta curta e direta
            tool_name_used = tool_decision.get("tool", "") if tool_decision else ""
            if tool_name_used in ("web_search", "search_memory"):
                if tool_name_used == "web_search":
                    followup_instruction = (
                        f"O usuário pediu: \"{message}\"\n"
                        "Com base nos resultados da busca acima, responda em português de forma natural. "
                        "Resuma o que encontraste em 2-4 frases. Mencione a fonte principal se relevante. "
                        "Não invente informações além do que está nos resultados."
                    )
                else:  # search_memory
                    followup_instruction = (
                        f"O usuário perguntou: \"{message}\"\n"
                        "Com base nas memórias encontradas acima, responda em português de forma natural e pessoal. "
                        "Cite o que foi dito anteriormente com precisão. "
                        "Se as memórias não respondem diretamente à pergunta, diga que não encontrou registros claros sobre isso."
                    )
            else:
                followup_instruction = (
                    f"O usuário perguntou: \"{message}\"\n"
                    "Responda em português, de forma natural e bem curta. "
                    "Use APENAS a parte do resultado que responde diretamente à pergunta. "
                    "Se perguntou só a hora, diga só a hora. Se perguntou só o clipboard, diga só o conteúdo. "
                    "Não mencione dados extras que não foram pedidos."
                )

            llm_messages.append({
                "role": "user",
                "content": followup_instruction,
            })

        self.memory.save_message(user_id, "user", message)  # salva mensagem original (sem context)

        self.state.set(AISystemState.SPEAKING)
        yield {"type": "status", "state": "speaking"}

        full_response = ""
        async for token in self._stream_ollama(llm_messages):
            full_response += token
            yield {"type": "token", "content": token}

        # Pós-processamento: remove reasoning tags
        clean_response = _strip_reasoning(full_response)

        new_emotion = self.emotion.analyze_and_update(clean_response)
        self.memory.save_message(user_id, "assistant", clean_response, emotion=new_emotion)
        self.memory.update_intimacy(user_id, 0.1)

        # Background tasks — executam em paralelo sem bloquear a resposta
        asyncio.create_task(self.extract_facts_bg(message, clean_response, user_id))
        asyncio.create_task(self.update_profile_bg(message, clean_response, user_id))
        asyncio.create_task(self.extract_kg_bg(message, clean_response, user_id))

        audio_b64 = await self.tts.generate(clean_response)

        self.state.set(AISystemState.IDLE)

        yield {
            "type": "response_complete",
            "content": clean_response,
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
        Background task: extrai fatos sobre o usuário do último par de mensagens.
        Usa o modelo principal (gemma3) — não precisa de JSON estruturado.
        """
        prompt = (
            "Analise esta conversa e extraia fatos concretos e PERMANENTES sobre o USUÁRIO "
            "(não sobre a IA). Retorne APENAS um JSON com lista de fatos objetivos.\n"
            "Se não houver fatos relevantes, retorne {\"fatos\": []}.\n"
            "Exemplos BONS: nome, profissão, cidade, hobby específico, preferência clara.\n"
            "NÃO extraia: hora, data, dia da semana, clima, valores numéricos temporários, "
            "ações da conversa, perguntas feitas. Só inclua fatos que ainda serão verdade daqui a 6 meses.\n"
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
                if len(raw) > 1000:
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

    async def update_profile_bg(self, user_msg: str, asst_msg: str, user_id: str) -> None:
        """
        Background task: usa qwen2.5-coder para extrair atualizações estruturadas de perfil
        a partir do último par de mensagens e mescla no perfil persistido.
        Executado de forma assíncrona — nunca bloqueia a resposta principal.
        """
        current = self.memory.get_profile(user_id)
        current_json = json.dumps(current, ensure_ascii=False)

        prompt = (
            f"Current user profile (JSON):\n{current_json}\n\n"
            f"New conversation:\n"
            f"User: {user_msg}\n"
            f"Assistant: {asst_msg}\n\n"
            "Task: Extract ONLY profile updates revealed in this conversation.\n"
            "Rules:\n"
            "- Return a JSON with ONLY fields that changed or were newly discovered.\n"
            "- Use Portuguese for all values.\n"
            "- For list fields (interesses, projetos, ferramentas, objetivos, notas): "
            "return only NEW items to add, not the full list.\n"
            "- Do NOT extract: time, date, day of week, weather, or temporary values.\n"
            "- Only extract PERMANENT facts (still true in 6 months).\n"
            "- If nothing new was discovered, return exactly: {}\n\n"
            'Example: {"nome": "Erik", "profissao": "desenvolvedor", "interesses": ["Minecraft"]}\n'
            "JSON:"
        )

        try:
            raw = ""
            async for token in self._stream_ollama_tool([{"role": "user", "content": prompt}]):
                raw += token
                if len(raw) > 800:
                    break

            raw = raw.strip()
            if not raw or raw == "{}":
                return

            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if not match:
                return

            delta = json.loads(match.group())
            if not delta:
                return

            # Mescla delta no perfil atual e salva
            updated = self.memory.profile.merge_update(current, delta)
            self.memory.update_profile(user_id, updated)
            print(f"[KRIRK][profile] Atualizado: {delta}")

        except Exception as e:
            print(f"[KRIRK][profile] update_profile_bg falhou: {e}")

    async def extract_kg_bg(self, user_msg: str, asst_msg: str, user_id: str) -> None:
        """
        Background task: extrai entidades e relações permanentes via qwen2.5-coder.
        Persiste no KnowledgeGraphManager (SQLite) sem duplicatas.
        """
        prompt = (
            "Analise a conversa e extraia entidades e relações concretas "
            "APENAS sobre o USUÁRIO ou coisas que ele possui, usa, criou ou está envolvido.\n"
            "Retorne SOMENTE JSON válido no formato:\n"
            '{"entities": [{"name": "...", "type": "pessoa|projeto|tecnologia|lugar|conceito"}], '
            '"relations": [{"from": "...", "relation": "...", "to": "..."}]}\n\n'
            "Regras:\n"
            "- Verbos de relação curtos e objetivos: usa, criou, trabalha_em, mora_em, "
            "gosta_de, estuda, tem, conhece\n"
            "- Apenas fatos PERMANENTES (ainda verdadeiros em 6 meses)\n"
            "- Entidades específicas e nomeadas (não genéricas como 'linguagem', 'ferramenta')\n"
            "- Se nada relevante encontrado: {\"entities\": [], \"relations\": []}\n\n"
            f"User: {user_msg}\n"
            f"Assistant: {asst_msg}\n\n"
            "JSON:"
        )
        try:
            raw = ""
            async for token in self._stream_ollama_tool([{"role": "user", "content": prompt}]):
                raw += token
                if len(raw) > 1000:
                    break

            raw = raw.strip()
            if not raw:
                return

            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if not match:
                return

            data = json.loads(match.group())

            # Persiste entidades
            for entity in data.get("entities", []):
                name = str(entity.get("name", "")).strip()
                etype = str(entity.get("type", "conceito")).strip()
                if name and len(name) > 1:
                    self.memory.kg.upsert_entity(user_id, name, etype)

            # Persiste relações (também garante que as entidades existam)
            for rel in data.get("relations", []):
                efrom = str(rel.get("from", "")).strip()
                relation = str(rel.get("relation", "")).strip()
                eto = str(rel.get("to", "")).strip()
                if efrom and relation and eto:
                    self.memory.kg.upsert_entity(user_id, efrom, "conceito")
                    self.memory.kg.upsert_entity(user_id, eto, "conceito")
                    self.memory.kg.upsert_relation(user_id, efrom, relation, eto)
                    print(f"[KG] {efrom} → {relation} → {eto}")

        except Exception as e:
            print(f"[KG] extract_kg_bg falhou: {e}")

    def get_status(self) -> dict:
        return {
            "state": self.state.current.value,
            "emotion": self.emotion.current_emotion,
            "model": self._ollama_config["model"],
            "tts_enabled": self._config["tts"]["enabled"],
            "stt_enabled": self._config["stt"]["enabled"],
        }
