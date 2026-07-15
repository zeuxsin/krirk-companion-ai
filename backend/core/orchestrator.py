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


_OPEN_TAGS  = ("<thought>", "<thinking>", "<think>", "<scratchpad>", "<reflection>")
_CLOSE_TAGS = ("</thought>", "</thinking>", "</think>", "</scratchpad>", "</reflection>")

async def _stream_strip_reasoning(
    source: AsyncGenerator[str, None],
) -> AsyncGenerator[str, None]:
    """
    Filtra tokens durante o streaming, suprimindo blocos <thought>…</thought>.
    Necessário quando o Google/Gemma é o provider — as thinking tokens chegam
    como tokens normais e seriam exibidas ao usuário sem este filtro.
    """
    buf = ""
    suppressed = False

    async for token in source:
        buf += token

        while True:
            low = buf.lower()

            if suppressed:
                # Procura tag de fechamento
                found_close = False
                for ctag in _CLOSE_TAGS:
                    pos = low.find(ctag)
                    if pos != -1:
                        buf = buf[pos + len(ctag):]
                        suppressed = False
                        found_close = True
                        break
                if found_close:
                    continue  # re-processa o restante do buffer
                # Sem tag de fechamento — descarta tudo exceto possível início de ctag
                tail = 20
                buf = buf[-tail:] if len(buf) > tail else buf
                break

            else:
                # Procura tag de abertura
                found_open = False
                for otag in _OPEN_TAGS:
                    pos = low.find(otag)
                    if pos != -1:
                        # Emite o que vem antes da tag
                        before = buf[:pos]
                        if before:
                            yield before
                        buf = buf[pos + len(otag):]
                        suppressed = True
                        found_open = True
                        break
                if found_open:
                    continue  # re-processa: pode já ter ctag no buffer
                # Sem tag de abertura — emite tudo exceto possível início de otag
                safe_len = len(buf) - 15
                if safe_len > 0:
                    yield buf[:safe_len]
                    buf = buf[safe_len:]
                break

    # Flush final
    if buf and not suppressed:
        yield buf

from backend.core.personality import PersonalitySystem
from backend.core.state import AIState, AISystemState
from backend.memory.memory_manager import MemoryManager
from backend.emotions.emotion_engine import EmotionEngine
from backend.voice.tts import TTSEngine
from backend.voice.stt import STTEngine
from backend.providers.router import build_router, ProviderRouter

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

        # ── Provider router (NVIDIA → Google → Cerebras → Ollama) ────────────
        self.router: ProviderRouter = build_router(config)

        # ── Sistema de ferramentas (Fase 4 — dual-model) ──────────────────────
        self._tool_cfg = config.get("tools", {"enabled": False})
        self.tool_registry = None
        self.tool_executor = None
        if self._tool_cfg.get("enabled", False):
            try:
                from backend.tools.registry import build_default_registry
                from backend.tools.executor import ToolExecutor
                self.tool_registry = build_default_registry(
                    self._tool_cfg, memory=self.memory, router=self.router
                )

                # Plugins de terceiros (Fase 6) — plugins/*.py com register(registry)
                plugins_cfg = config.get("plugins", {})
                if plugins_cfg.get("enabled", True):
                    from backend.tools.plugin_loader import load_plugins
                    load_plugins(self.tool_registry, plugins_cfg.get("dir", "plugins"))

                self.tool_executor = ToolExecutor(
                    self.tool_registry,
                    timeout=self._tool_cfg.get("timeout_seconds", 10),
                )
                tool_model = self._tool_cfg.get("tool_model", self._ollama_config["model"])
                print(f"[KRIRK][tools] Modelo de roteamento: {tool_model}")
            except Exception as e:
                print(f"[KRIRK][tools] Falha ao inicializar ferramentas: {e}")

    # ── Streaming helpers (delegam ao ProviderRouter) ─────────────────────────

    async def _stream_ollama(
        self,
        messages: list[dict],
        images: list[str] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Chat com personalidade — usa task 'chat' no router."""
        if images:
            # Visão via router: NVIDIA (llama-3.2-vision) → Ollama (gemma3 multimodal)
            msgs = [m.copy() for m in messages]
            msgs[-1] = {**msgs[-1], "images": images}
            raw_stream = self.router.stream(
                "vision", msgs,
                temperature=self._ollama_config["temperature"],
                max_tokens=self._ollama_config["max_tokens"],
            )
            async for token in _stream_strip_reasoning(raw_stream):
                yield token
            return

        raw_stream = self.router.stream(
            "chat", messages,
            temperature=self._ollama_config["temperature"],
            max_tokens=self._ollama_config["max_tokens"],
        )
        async for token in _stream_strip_reasoning(raw_stream):
            yield token

    async def _stream_ollama_code(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        """Modo Coder — usa task 'code' no router."""
        raw_stream = self.router.stream(
            "code", messages,
            temperature=0.4,
            max_tokens=self._ollama_config["max_tokens"],
        )
        async for token in _stream_strip_reasoning(raw_stream):
            yield token

    async def _stream_ollama_tool(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        """Tool routing — usa task 'tools' no router (DeepSeek v4 Pro no NVIDIA)."""
        raw = await self.router.complete(
            "tools", messages,
            temperature=0.1,
            max_tokens=256,
        )
        if raw:
            yield raw

    # ── Decisão de tool (Fase 1) ──────────────────────────────────────────────

    async def _decide_tool(
        self,
        message: str,
        history: list | None = None,
        executed: list[tuple[str, str]] | None = None,
    ) -> dict | None:
        """
        Usa o modelo de roteamento para decidir QUAL ferramenta usar, se alguma.
        executed: ferramentas já executadas NESTA requisição [(nome, resultado)] —
        permite o loop de agente encadear passos até completar o pedido.
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

        # Passos já executados nesta requisição (loop de agente)
        executed_context = ""
        if executed:
            lines = [f"- {name}: {result[:200]}" for name, result in executed]
            executed_context = (
                "Tools ALREADY EXECUTED for this request (with results):\n"
                + "\n".join(lines)
                + "\nIf these results already fulfill the user's request, respond: none\n"
                "Otherwise, choose the NEXT tool needed to continue.\n\n"
            )

        planning_prompt = (
            "You are a tool router for a desktop AI assistant. "
            "Analyze the user's message and decide which tool to use, if any.\n\n"
            f"User home directory: {_HOME}\n\n"
            f"Available tools:\n{tool_desc}\n\n"
            f"{history_context}"
            f"{executed_context}"
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
            "- open_url: use for ANY request to open a website, URL, or online service "
            "(YouTube, Google, GitHub, Reddit, Twitter, Netflix, Twitch, etc.). "
            "NEVER use open_file for websites. Pass only the domain or URL, not a file path.\n"
            "- open_app: use for desktop applications/programs (Notepad, Spotify, Chrome, VS Code, etc.).\n"
            "- set_timer: use when the user asks for a timer, countdown, or reminder with a time duration.\n"
            "- fetch_url: use to READ the text content of a SPECIFIC page/site. "
            "web_search: to SEARCH the internet when no specific URL is known.\n"
            "- read_screen: use when the user asks to read/check/transcribe what is on their screen.\n"
            "- Multi-step requests may need a SEQUENCE of tools (e.g. open_app then type_text). "
            "Choose only the FIRST/NEXT step now; you will be asked again for the following step.\n"
        )

        raw = await self.router.complete(
            "tools",
            [{"role": "user", "content": planning_prompt}],
            temperature=0.1,
            max_tokens=256,
        )

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

        # Context management: recorta histórico longo e recupera resumo salvo
        ctx_cfg = self._config.get("context_management", {})
        history, conv_summary = self._trim_history(user_id, history)

        # Dispara resumo background se o histórico ainda está acima de 80% do limite
        if ctx_cfg.get("enabled", True):
            max_hist = ctx_cfg.get("max_history_tokens", 3000)
            total_tok = sum(self._estimate_tokens(m["content"]) for m in history)
            if total_tok > max_hist * 0.8:
                asyncio.create_task(self._summarize_history_bg(user_id, history))

        facts = self.memory.get_facts(user_id, limit=8)

        # Memórias semânticas relevantes via ChromaDB
        semantic_memories: list[str] = []
        if self._vector_cfg.get("enabled", True):
            raw = self.memory.search_semantic(
                user_id, query=message, n=self._vector_cfg.get("search_results", 5)
            )
            min_score = self._vector_cfg.get("min_score", 0.45)
            semantic_memories = [r["text"] for r in raw if r["score"] >= min_score]

        # ── FASE 1: Loop de agente — encadeia até max_rounds ferramentas ──────
        tool_result_context = ""
        executed_tools: list[tuple[str, str]] = []
        if self._tool_cfg.get("enabled", False) and self.tool_executor:
            max_rounds = self._tool_cfg.get("max_rounds", 4)
            prev_decision_json = None

            for _round in range(max_rounds):
                tool_decision = await self._decide_tool(
                    message, history, executed=executed_tools or None
                )
                if not tool_decision:
                    break

                # Guarda contra loop: mesma tool + mesmos params da rodada anterior
                decision_json = json.dumps(tool_decision, sort_keys=True)
                if decision_json == prev_decision_json:
                    print("[KRIRK][agent] Decisão repetida — encerrando loop.")
                    break
                prev_decision_json = decision_json

                tool_name = tool_decision.get("tool", "ferramenta")

                self.state.set(AISystemState.EXECUTING)
                yield {"type": "status", "state": "executing"}
                yield {"type": "tool_call", "tool": tool_name, "raw": json.dumps(tool_decision)}

                result = await self.tool_executor.execute_from_json(
                    json.dumps(tool_decision)
                )
                print(f"[KRIRK][agent] round {_round + 1}/{max_rounds}: {tool_name} → {result[:150]}")
                yield {"type": "tool_result", "tool": tool_name, "result": result}

                executed_tools.append((tool_name, result))

                # Erro na tool → não insiste em mais rodadas, deixa o modelo explicar
                if result.startswith("[Erro]"):
                    break

            if executed_tools:
                if len(executed_tools) == 1:
                    tool_result_context = (
                        f"Consultei {executed_tools[0][0]} e o resultado foi:\n\n"
                        f"{executed_tools[0][1]}"
                    )
                else:
                    parts_txt = "\n\n".join(
                        f"[{name}]\n{result}" for name, result in executed_tools
                    )
                    tool_result_context = (
                        f"Executei {len(executed_tools)} ferramentas em sequência. Resultados:\n\n"
                        f"{parts_txt}"
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
            conversation_summary=conv_summary,
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
            executed_names = [name for name, _ in executed_tools]
            if "web_search" in executed_names:
                tool_name_used = "web_search"
            elif "search_memory" in executed_names:
                tool_name_used = "search_memory"
            else:
                tool_name_used = executed_names[-1] if executed_names else ""
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
            elif len(executed_tools) > 1:
                followup_instruction = (
                    f"O usuário pediu: \"{message}\"\n"
                    "Você executou os passos acima em sequência. Confirme em português, "
                    "de forma natural e breve, o que foi feito e o resultado final. "
                    "Se algum passo falhou, explique qual e por quê."
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

    # ── Modo Coder ────────────────────────────────────────────────────────────

    async def process_code_chat(
        self,
        message: str,
        user_id: str = "default",
    ) -> AsyncGenerator[dict, None]:
        """
        Pipeline do Modo Coder:
        - Usa qwen2.5-coder diretamente (sem personalidade gemma3)
        - Suporta execute_python via roteamento normal
        - Sem TTS, sem extração de fatos/perfil/KG
        """
        self.state.set(AISystemState.THINKING)
        yield {"type": "status", "state": "thinking"}

        # Histórico próprio do Modo Coder — sessão isolada do chat
        history = self.memory.get_recent_messages(
            user_id,
            limit=self._config["memory"]["short_term_limit"],
            session="code",
        )

        system = (
            "You are an expert programming assistant. "
            "Respond in Brazilian Portuguese (pt-BR). "
            "Be technical, concise and direct. "
            "Use markdown code blocks with language tags (```python, ```javascript, etc). "
            "When asked to execute or test code, use the execute_python tool. "
            "Explain errors clearly and suggest fixes."
        )

        # ── Tool routing (mesmo _decide_tool do chat normal) ──────────────────
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
                print(f"[KRIRK][code] {tool_name} → {result[:150]}")
                yield {"type": "tool_result", "tool": tool_name, "result": result}
                tool_result_context = result

        # ── Monta contexto para qwen2.5-coder ────────────────────────────────
        llm_messages = [{"role": "system", "content": system}]

        # Apenas últimas 8 msgs do histórico (foco no contexto imediato)
        for m in history[-8:]:
            if m["role"] in ("user", "assistant"):
                llm_messages.append({"role": m["role"], "content": m["content"]})

        llm_messages.append({"role": "user", "content": message})

        if tool_result_context:
            llm_messages.append({
                "role": "assistant",
                "content": f"Resultado da execução:\n```\n{tool_result_context}\n```",
            })
            llm_messages.append({
                "role": "user",
                "content": "Explique o resultado acima de forma clara e objetiva.",
            })

        # Salva na sessão "code" — não polui o histórico do chat
        self.memory.save_message(user_id, "user", message, session="code")

        self.state.set(AISystemState.SPEAKING)
        yield {"type": "status", "state": "speaking"}

        full_response = ""
        async for token in self._stream_ollama_code(llm_messages):
            full_response += token
            yield {"type": "token", "content": token}

        clean_response = _strip_reasoning(full_response)
        self.memory.save_message(user_id, "assistant", clean_response, session="code")

        self.state.set(AISystemState.IDLE)
        yield {
            "type": "response_complete",
            "content": clean_response,
            "emotion": "neutro",
            "audio": None,   # Sem TTS no Modo Coder
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

    async def process_image_chat(
        self,
        image_b64: str,
        user_id: str = "default",
    ) -> AsyncGenerator[dict, None]:
        """Recebe imagem do usuário (base64) → passa para o modelo de visão → streama resposta."""

        self.state.set(AISystemState.THINKING)
        yield {"type": "status", "state": "thinking"}

        # Gera thumbnail para mostrar no chat (max 400px)
        thumb_b64 = image_b64
        try:
            import base64, io
            from PIL import Image
            raw = base64.b64decode(image_b64)
            img = Image.open(io.BytesIO(raw))
            img.thumbnail((400, 400), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=75)
            thumb_b64 = base64.b64encode(buf.getvalue()).decode()
        except Exception:
            pass

        yield {"type": "screenshot_taken", "thumbnail": f"data:image/jpeg;base64,{thumb_b64}"}

        prompt = "Descreva o que você vê nessa imagem que o usuário enviou. Seja específica e útil."
        self.memory.save_message(user_id, "user", "[Imagem enviada pelo usuário]")

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

    # ── Context Management ────────────────────────────────────────────────────

    def _estimate_tokens(self, text: str) -> int:
        """Estimativa rápida de tokens: ~4 chars por token (PT-BR + código)."""
        return max(1, len(text) // 4)

    def _trim_history(
        self,
        user_id: str,
        history: list[dict],
    ) -> tuple[list[dict], str | None]:
        """
        Se o histórico cabe no orçamento de tokens → retorna inteiro, sem resumo.
        Caso contrário → mantém as últimas `keep_recent` mensagens + recupera resumo salvo.
        """
        cfg = self._config.get("context_management", {})
        if not cfg.get("enabled", True):
            return history, None

        max_hist = cfg.get("max_history_tokens", 3000)
        keep = cfg.get("keep_recent", 8)

        total_tokens = sum(self._estimate_tokens(m["content"]) for m in history)
        if total_tokens <= max_hist:
            return history, None

        summary = self.memory.get_summary(user_id)
        trimmed = history[-keep:]
        return trimmed, summary

    async def _summarize_history_bg(
        self,
        user_id: str,
        history: list[dict],
    ) -> None:
        """
        Background task: resume o histórico completo via qwen2.5-coder
        e salva em conversation_summaries para o próximo turno.
        """
        try:
            text = "\n".join(
                f"{m['role'].upper()}: {m['content']}" for m in history
            )
            prompt = (
                "Resuma a seguinte conversa em 3-5 frases concisas em português. "
                "Foque nos tópicos discutidos, decisões tomadas e fatos importantes "
                "sobre o usuário. Seja compacto e objetivo.\n\n"
                + text
            )
            summary = await self.router.complete(
                "tools",
                [{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=512,
            )
            summary = summary.strip()
            self.memory.save_summary(user_id, summary, len(history))
            print(f"[KRIRK][context] Resumo gerado: {len(history)} msgs → {len(summary)} chars")
        except Exception as e:
            print(f"[KRIRK][context] Erro ao gerar resumo: {e}")

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
