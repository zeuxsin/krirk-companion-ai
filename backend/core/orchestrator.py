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


# Marcadores de riso/aprovação — sinal de que a última troca teve graça
_AMUSEMENT_MARKERS = (
    "kkk", "kkkk", "rsrs", "haha", "hehe", "auhu", "ashsh", "kajs",
    "genial", "morri", "pqp", "mano do céu", "muito bom", "hilário",
    "hilario", "não aguento", "nao aguento", "😂", "🤣", "😹", "kkkkk",
)


def _detect_amusement(text: str) -> bool:
    """True se o texto do usuário indica riso/diversão (para a reflexão priorizar humor)."""
    low = text.lower()
    return any(m in low for m in _AMUSEMENT_MARKERS)


# ── Filtro de small-talk ──────────────────────────────────────────────────────
# Saudações e conversa fiada NUNCA precisam de ferramenta, mas modelos pequenos
# confundem "como está o dia de hoje?" com pedido de data/hora (get_time).
# Este filtro determinístico pula o roteamento inteiro nesses casos.
_SMALLTALK_RE = re.compile(
    r"(?:^|\b)(oi+|ol[áa]|opa|e a[íi]|eae|bom dia|boa tarde|boa noite|"
    r"tudo bem|td bem|tudo certo|como (?:vai|est[áa]|anda|voc[êe] (?:vai|est[áa]))|"
    r"beleza|suave|obrigad[oa]|valeu|brigad[oa]|boa noite)(?:\b|$)",
    re.IGNORECASE,
)
# Se QUALQUER um destes aparecer, a mensagem pode precisar de ferramenta —
# o roteador decide. ("hora" pega "que horas"; cuidado: também casa "agora",
# o que só torna o filtro mais conservador.)
_ACTION_MARKERS = (
    "abr", "fech", "toca", "pausa", "pesquis", "busca", "busque", "procur",
    "digit", "escrev", "salv", "execut", "roda", "rode", "cria", "crie",
    "mostra", "mostre", "clica", "clique", "lembra", "anota", "timer",
    "alarme", "volume", "http", "www", "browser", "navegador", "tela",
    "arquivo", "pasta", "clima", "previsão", "previsao", "hora", "que dia",
    "data", "rola", "role", "dado",
)


def _is_smalltalk(text: str) -> bool:
    """True para saudação/conversa fiada curta — pula o roteamento de tools."""
    t = text.strip().lower()
    if len(t) > 60:
        return False
    if not _SMALLTALK_RE.search(t):
        return False
    return not any(m in t for m in _ACTION_MARKERS)


# ── Parsers de extração em background ─────────────────────────────────────────
# Formato de LINHAS em vez de JSON: fatos/relações contêm aspas e vírgulas em
# linguagem natural que os modelos não escapam, quebrando json.loads
# ("Expecting ',' delimiter"). Linhas são à prova disso.

def _parse_fact_lines(raw: str) -> list[str]:
    """Extrai fatos de linhas '- fato' ou '• fato'. 'NENHUM' → lista vazia."""
    facts = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if line.upper().startswith("NENHUM"):
            return []
        for prefix in ("- ", "• ", "* "):
            if line.startswith(prefix):
                fact = line[len(prefix):].strip().strip('"').strip()
                if len(fact) > 8:
                    facts.append(fact)
                break
    return facts


# ── Placeholder <LAST_RESPONSE> ───────────────────────────────────────────────
# "Salva isso na área de trabalho" referencia conteúdo que o roteador não
# consegue reproduzir (código longo da mensagem anterior). O roteador usa o
# placeholder e o orchestrator o substitui pelo conteúdo real do histórico.
_CODE_BLOCK_RE = re.compile(r"```[a-zA-Z0-9_+#.-]*\n(.*?)```", re.DOTALL)


def _largest_code_block(text: str) -> str | None:
    """Maior bloco ```...``` do texto, ou None se não houver."""
    blocks = _CODE_BLOCK_RE.findall(text or "")
    return max(blocks, key=len).strip() if blocks else None


def _resolve_last_response(params: dict, history: list[dict]) -> dict:
    """
    Substitui <LAST_RESPONSE> em params.content pela última resposta da
    assistente no histórico (maior bloco de código, se houver — para 'salva
    esse script'; senão o texto completo — para 'salva essa agenda').
    """
    content = params.get("content")
    if not isinstance(content, str) or "<LAST_RESPONSE>" not in content:
        return params
    last = next(
        (m["content"] for m in reversed(history) if m.get("role") == "assistant"),
        "",
    )
    block = _largest_code_block(last)
    replacement = block if block else last.strip()
    new_params = dict(params)
    new_params["content"] = content.replace("<LAST_RESPONSE>", replacement)
    return new_params


# Ferramentas de AÇÃO: uma execução bem-sucedida ENCERRA o loop iterativo.
# Sem isso o roteador "melhora" o resultado em rounds seguintes — ex: regravar
# a mesma agenda 3x até alucinar o dia errado. Encadeamentos multi-ação
# legítimos usam o PLANO (todas as etapas decididas de uma vez).
_TERMINAL_TOOLS = {
    "write_file", "open_url", "open_app", "open_file", "set_timer",
    "remember_this", "coin_term", "set_brain_state", "type_text",
    "press_hotkey", "focus_window", "set_volume", "mute_volume",
    "media_play_pause", "media_next", "media_prev", "set_clipboard",
    "browser_open", "browser_click", "browser_fill", "browser_close",
}


# Alegações de ação que a Krirk NÃO pode fazer sem ferramenta executada —
# usado como telemetria de honestidade (loga quando o modelo alucina ação)
_ACTION_CLAIM_RE = re.compile(
    r"\b(vou abrir|abrindo|acabei de abrir|abri o|abri a|vou executar|executando|"
    r"vou rodar|rodando o|vou criar o arquivo|criando o arquivo|salvando|"
    r"deixa comigo|s[óo] um segundo|um momento enquanto|"
    # particípios/pretéritos — "Arquivo salvo: C:\..." era a alucinação que escapava
    r"arquivo (?:salvo|criado|pronto)|salvei o|criei o arquivo|"
    r"salv[oa] (?:em|na|no) [cC]:|criad[oa] (?:em|na|no) [cC]:|"
    r"est[áa] (?:salvo|criado|pronto) (?:em|na|no)\b)",
    re.IGNORECASE,
)


def _claims_action(text: str) -> bool:
    """True se a resposta alega estar executando/ter executado uma ação."""
    return bool(_ACTION_CLAIM_RE.search(text))


# Sujeitos que nunca devem entrar no Knowledge Graph (o grafo é sobre o USUÁRIO;
# o modelo insiste em extrair relações sobre a própria assistente)
_KG_BLOCKED_SUBJECTS = {"assistant", "assistente", "krirk", "ia", "ai", "bot", "você", "voce"}


def _parse_kg_lines(raw: str) -> list[tuple[str, str, str]]:
    """
    Extrai relações de linhas 'entidade | relacao | entidade'.
    Filtra lixo: partes vazias/gigantes e sujeitos que são a própria assistente.
    """
    triples = []
    for line in (raw or "").splitlines():
        line = line.strip().lstrip("-•* ").strip()
        if line.upper().startswith("NENHUM") or "|" not in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 3 or not all(parts):
            continue
        efrom, rel, eto = parts
        if len(efrom) > 60 or len(rel) > 40 or len(eto) > 60:
            continue
        if efrom.lower() in _KG_BLOCKED_SUBJECTS:
            continue
        triples.append((efrom, rel, eto))
    return triples


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

from backend.agents.planner import parse_decision, MAX_PLAN_STEPS
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

        # ── Brain-state (Fase D) — humor de geração controlável pela Krirk ───
        self._brain_state = "chill"   # focused | chill | creative | chaos

        # Último arquivo criado via write_file — contexto para "muda X no arquivo"
        self._last_written_file: str | None = None

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
                    self._tool_cfg, memory=self.memory, router=self.router, orchestrator=self
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

        gp = self._gen_params()
        raw_stream = self.router.stream(
            "chat", messages,
            temperature=gp["temperature"],
            max_tokens=self._ollama_config["max_tokens"],
            top_p=gp["top_p"],
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
    ) -> dict:
        """
        Usa o modelo de roteamento para decidir o que fazer com a mensagem.
        executed: ferramentas já executadas NESTA requisição [(nome, resultado)] —
        permite o loop de agente encadear passos até completar o pedido.
        Retorna (via parse_decision):
          {"type": "none"} | {"type": "tool", "tool", "params"} | {"type": "plan", "steps"}
        Planos só são aceitos na primeira decisão (executed is None).
        """
        if not (self.tool_registry and self.tool_executor):
            return {"type": "none"}

        tool_desc = self.tool_registry.get_descriptions()

        # Últimas mensagens para o roteador resolver referências ("muda aquilo",
        # "salva isso"). 300 chars/msg: o suficiente para ver conteúdos pequenos
        # (agendas, listas) sem estourar o prompt; código longo usa <LAST_RESPONSE>.
        history_context = ""
        if history:
            recent = history[-6:]
            lines = []
            for m in recent:
                role = "User" if m["role"] == "user" else "Assistant"
                lines.append(f"{role}: {m['content'][:300]}")
            if lines:
                history_context = "Recent conversation:\n" + "\n".join(lines) + "\n\n"

        # Último arquivo criado — para pedidos de modificação
        last_file_context = ""
        if self._last_written_file:
            last_file_context = f"Last file you created: {self._last_written_file}\n\n"

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

        allow_plan = executed is None  # plano só na primeira decisão, não dentro de passos

        plan_rule = (
            f"- If the request needs MULTIPLE DIFFERENT tools in sequence "
            f"(e.g. open an app AND THEN type text into it), respond with ONLY a "
            f"COMPLETE plan including all params (max {MAX_PLAN_STEPS} steps):\n"
            f'  {{"plan": [{{"tool": "open_app", "params": {{"app_name": "notepad"}}}}, '
            f'{{"tool": "type_text", "params": {{"text": "the exact text to type"}}}}]}}\n'
            f"  Plans are ONLY for ACTION sequences on the computer. Questions, memory "
            f"lookups and info requests use a single tool or none — NEVER a plan.\n"
        ) if allow_plan else ""

        planning_prompt = (
            "You are a tool router for a desktop AI assistant. "
            "Analyze the user's message and decide which tool to use, if any.\n\n"
            f"User home directory: {_HOME}\n\n"
            f"Available tools:\n{tool_desc}\n\n"
            f"{history_context}"
            f"{last_file_context}"
            f"{executed_context}"
            f"User message: {message}\n\n"
            "Rules:\n"
            "- If ONE tool is needed, respond with ONLY valid JSON (no markdown, no explanation):\n"
            '  {"tool": "exact_tool_name", "params": {"param_name": "value"}}\n'
            f"{plan_rule}"
            "- If no tool is needed, respond with exactly: none\n"
            "- IMPORTANT: decide based on the CURRENT user message ONLY. The 'Recent conversation' "
            "section exists ONLY to resolve references like 'de novo', 'novamente', 'o mesmo'. "
            "NEVER pick a tool because of URLs, sites, apps or actions mentioned in the history — "
            "if the current message does not itself ask for an action or fresh information, respond: none\n"
            "- NEVER use a tool for: greetings, thanks, short replies, confirmations, "
            "reactions ('ok', 'isso aí', 'certo', 'sim', 'não', 'ótimo', 'entendi', 'legal', "
            "'exato', 'claro', 'show', 'beleza', 'tá'), opinions, questions about the assistant "
            "itself, or casual chat.\n"
            "- If the user REQUESTS AN ACTION (lembrar, abrir, tocar, criar timer, salvar, "
            "pesquisar), you MUST pick the matching tool — 'none' there means the action "
            "silently never happens. Reserve 'none' for conversation, not for requests.\n"
            "- get_time: ONLY when the user EXPLICITLY asks the current time or date "
            "('que horas são?', 'que dia é hoje?'). Questions about WELL-BEING or how the "
            "day is going ('como está?', 'como vai seu dia?', 'como está no dia de hoje?') "
            "are small talk even though they mention 'dia' or 'hoje' — respond: none\n"
            "- CREATIVE WRITING is conversation, not a tool: 'escreve um poema/texto/história/"
            "mensagem' WITHOUT a destination → none (just answer in chat). Only use write_file "
            "if the user names a FILE, or type_text if they name an APP/field to type into.\n"
            "- SAVE WHAT YOU JUST GENERATED ('salva isso', 'coloca na área de trabalho', "
            "'cria esse arquivo'): use write_file with content EXACTLY \"<LAST_RESPONSE>\" — "
            "it is auto-replaced by your previous message (largest code block if any). "
            'Example: {"tool": "write_file", "params": {"path": "desktop/agenda.txt", '
            '"content": "<LAST_RESPONSE>"}}\n'
            "- CREATE NEW SUBSTANTIAL CONTENT into a file (an app, script, long document "
            "that does NOT exist yet in the conversation): NEVER write the content inline "
            "(your output gets truncated and NOTHING executes). Use content EXACTLY "
            "\"<GENERATE>\" — a specialized model will write the full file from the user's "
            'request. Example: {"tool": "write_file", "params": '
            '{"path": "desktop/app_agenda.py", "content": "<GENERATE>"}}\n'
            "  Inline content is ONLY for short things (a few lines).\n"
            "- MODIFY A FILE you created ('muda X para Y no arquivo', 'corrige'): call "
            "write_file again to the SAME path (see 'Last file you created') with the FULL "
            "corrected content — rewrite it from the Recent conversation with the fix applied. "
            "NEVER respond none to a correction request.\n"
            "- run_powershell: LAST RESORT — only when the user explicitly asks to run a "
            "command/script, or no other tool can do it. NEVER shutdown/restart/kill/delete "
            "unless the user used those exact words.\n"
            "- execute_python: only when the user explicitly asks to RUN/test code, or for "
            "genuinely heavy computation. Simple math ('quanto é 15% de 230?') → none.\n"
            "- 'me lembra' DISAMBIGUATION — these are ACTION requests, never 'none':\n"
            '  "me lembra de tomar água daqui a 15 minutos" → '
            '{"tool": "set_timer", "params": {"minutes": "15", "label": "tomar água"}}\n'
            '  "lembra que meu aniversário é 10 de março" → '
            '{"tool": "remember_this", "params": {"fact": "aniversário do usuário é 10 de março"}}\n'
            "  Rule: WITH duration → set_timer; permanent fact WITHOUT duration → remember_this.\n"
            "- set_volume/mute_volume/media_*: only for SYSTEM audio or media players. "
            "'fica quieta', 'silêncio', 'fala menos' are directed at YOU (the assistant) → none.\n"
            "- search_memory: the user's profile (name, job, interests) is ALREADY in context — "
            "do not search for it. Only search for specific PAST-CONVERSATION content.\n"
            "- search_memory: ONLY use when the user is EXPLICITLY asking to recall past "
            "conversations ('você lembra?', 'o que eu te falei?', 'qual era mesmo?'). "
            "Do NOT use for confirmations or reactions to what was just said.\n"
            "- search_history: when the user asks what was discussed in a past PERIOD "
            "('o que falamos ontem?', 'sobre o que conversamos semana passada?'). "
            "days_back = how many days back to search.\n"
            "- remember_this: ONLY when the user EXPLICITLY asks to remember/save something "
            "('lembra disso', 'anota que...', 'não esquece que...'). Pass the fact as param.\n"
            "- coin_term: when the user establishes an inside joke/slang ('esse é nosso bordão', "
            "'de agora em diante X quer dizer Y') or officializes a recurring joke.\n"
            "- search_meme: when the user asks the meaning/origin of a meme or slang term.\n"
            "- set_brain_state: when the user asks you to change your vibe/mood of thinking "
            "('fica mais criativa', 'foca agora', 'modo caos') or you decide to shift it.\n"
            "- Use the EXACT tool name as listed above. Do not translate to Portuguese.\n"
            "- For run_powershell, write a complete PowerShell command.\n"
            "- For list_directory and read_file, use the full absolute path.\n"
            "- open_url: use for ANY request to open a website, URL, or online service "
            "(YouTube, Google, GitHub, Reddit, Twitter, Netflix, Twitch, etc.). "
            "NEVER use open_file for websites. Pass only the domain or URL, not a file path.\n"
            "- open_app: use for desktop applications/programs (Notepad, Spotify, Chrome, VS Code, etc.).\n"
            "- set_timer: use when the user asks for a timer, countdown, or reminder with a time duration.\n"
            "- fetch_url: use to READ the text content of a SPECIFIC page/site. "
            "web_search: to SEARCH the internet when no specific URL is known.\n"
            "- browser_open/browser_click/browser_fill/browser_read: interactive browser that YOU "
            "control to navigate, click buttons, fill forms and read the result. Use ONLY when the "
            "task requires interacting with a page, not just reading it.\n"
            "- read_screen: use when the user asks to read/check/transcribe what is on their screen.\n"
        )

        raw = await self.router.complete(
            "tools",
            [{"role": "user", "content": planning_prompt}],
            temperature=0.1,
            max_tokens=600,
        )

        raw = raw.strip()
        print(f"[KRIRK][tools] Decisão do roteador: {raw[:150]}")

        decision = parse_decision(raw)
        if not allow_plan and decision["type"] == "plan":
            # Dentro de um passo não aceitamos sub-planos — vira none
            return {"type": "none"}
        return decision

    def _prep_payload(self, payload: dict, history: list[dict]) -> dict:
        """Resolve <LAST_RESPONSE> nos params antes de executar."""
        return {
            "tool": payload["tool"],
            "params": _resolve_last_response(payload.get("params", {}), history),
        }

    async def _maybe_generate_content(self, payload: dict, user_message: str) -> dict:
        """
        Resolve <GENERATE>: o roteador delega a criação de conteúdo substancial
        (apps, scripts, documentos) ao modelo de código — inline no JSON do
        roteador o conteúdo estourava o limite de tokens e truncava a decisão.
        """
        params = payload.get("params", {})
        content = params.get("content")
        if not isinstance(content, str) or content.strip() != "<GENERATE>":
            return payload

        path = str(params.get("path", "arquivo"))
        prompt = (
            f"Escreva o CONTEÚDO COMPLETO do arquivo '{path}' para atender este "
            f"pedido do usuário:\n\n{user_message}\n\n"
            "Regras: responda APENAS com o conteúdo do arquivo, completo e "
            "funcional, do início ao fim. Sem explicações antes ou depois. "
            "Pode usar cerca de código (```), que será removida."
        )
        raw = await self.router.complete(
            "code", [{"role": "user", "content": prompt}],
            temperature=0.4, max_tokens=4000,
        )
        generated = _largest_code_block(raw) or _strip_reasoning(raw or "").strip()
        if not generated:
            # Sem conteúdo — deixa o executor falhar com mensagem clara
            generated = ""
        print(f"[KRIRK][generate] Conteúdo gerado para {path}: {len(generated)} chars")
        new_params = dict(params)
        new_params["content"] = generated
        return {"tool": payload["tool"], "params": new_params}

    def _track_written_file(self, payload: dict, result: str) -> None:
        """Guarda o path do último write_file bem-sucedido (contexto de edição)."""
        if payload.get("tool") == "write_file" and result.startswith("Arquivo salvo: "):
            m = re.match(r"Arquivo salvo: (.+?) \(", result)
            if m:
                self._last_written_file = m.group(1)

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

        # ── FASE 1: Planner + loop de agente ──────────────────────────────────
        tool_result_context = ""
        executed_tools: list[tuple[str, str]] = []
        skip_tools = _is_smalltalk(message)
        if skip_tools:
            print("[KRIRK][tools] Small-talk detectado — roteamento pulado")
        if self._tool_cfg.get("enabled", False) and self.tool_executor and not skip_tools:
            max_rounds = self._tool_cfg.get("max_rounds", 4)

            decision = await self._decide_tool(message, history)

            plan_attempted = False
            if decision["type"] == "plan":
                # ── Modo planejado ─────────────────────────────────────────────
                # Passos dict {"tool","params"} executam DIRETO (sem re-roteamento);
                # passos string (legado) são re-roteados com o pedido original junto.
                plan_attempted = True
                steps = decision["steps"][:max_rounds]
                step_labels = [
                    s["tool"] if isinstance(s, dict) else s for s in steps
                ]
                print(f"[KRIRK][agent] Plano com {len(steps)} passos: {step_labels}")
                yield {"type": "tool_call", "tool": "planner",
                       "raw": json.dumps({"plan": step_labels}, ensure_ascii=False)}
                yield {"type": "tool_result", "tool": "planner",
                       "result": "Plano:\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(step_labels))}

                for i, step in enumerate(steps):
                    if isinstance(step, dict):
                        payload = step
                    else:
                        step_decision = await self._decide_tool(
                            f"{step} (parte do pedido original: \"{message}\")",
                            history, executed=executed_tools or []
                        )
                        if step_decision["type"] != "tool":
                            print(f"[KRIRK][agent] passo {i+1} não mapeou para tool: {step}")
                            continue
                        payload = {"tool": step_decision["tool"], "params": step_decision["params"]}

                    payload = self._prep_payload(payload, history)
                    payload = await self._maybe_generate_content(payload, message)
                    tool_name = payload["tool"]

                    self.state.set(AISystemState.EXECUTING)
                    yield {"type": "status", "state": "executing"}
                    yield {"type": "tool_call", "tool": tool_name, "raw": json.dumps(payload)[:500]}

                    result = await self.tool_executor.execute_from_json(json.dumps(payload))
                    self._track_written_file(payload, result)
                    print(f"[KRIRK][agent] passo {i+1}/{len(steps)}: {tool_name} → {result[:150]}")
                    yield {"type": "tool_result", "tool": tool_name, "result": result}
                    executed_tools.append((tool_name, result))

                    if result.startswith("[Erro]"):
                        break  # não continua o plano em cima de um passo falho

            elif decision["type"] == "tool":
                # ── Modo iterativo: executa e pergunta se precisa de mais ──────
                prev_decision_json = None
                for _round in range(max_rounds):
                    if decision["type"] != "tool":
                        break

                    payload = {"tool": decision["tool"], "params": decision["params"]}
                    decision_json = json.dumps(payload, sort_keys=True)
                    if decision_json == prev_decision_json:
                        print("[KRIRK][agent] Decisão repetida — encerrando loop.")
                        break
                    prev_decision_json = decision_json

                    payload = self._prep_payload(payload, history)
                    payload = await self._maybe_generate_content(payload, message)
                    tool_name = payload["tool"]

                    self.state.set(AISystemState.EXECUTING)
                    yield {"type": "status", "state": "executing"}
                    yield {"type": "tool_call", "tool": tool_name, "raw": json.dumps(payload)[:500]}

                    result = await self.tool_executor.execute_from_json(json.dumps(payload))
                    self._track_written_file(payload, result)
                    print(f"[KRIRK][agent] round {_round + 1}/{max_rounds}: {tool_name} → {result[:150]}")
                    yield {"type": "tool_result", "tool": tool_name, "result": result}
                    executed_tools.append((tool_name, result))

                    if result.startswith("[Erro]"):
                        break

                    # Ação executada com sucesso = pedido atendido; não re-decidir
                    # (evita regravar/refazer com conteúdo regenerado e drift)
                    if tool_name in _TERMINAL_TOOLS:
                        break

                    decision = await self._decide_tool(message, history, executed=executed_tools)

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
            elif plan_attempted:
                # Plano criado mas nenhum passo executou — força honestidade
                tool_result_context = (
                    "ATENÇÃO: tentei executar o pedido mas NENHUMA ferramenta foi "
                    "executada com sucesso. Nada foi feito no computador."
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

        # ── Camada de interioridade — léxico, reflexões, diário ──────────────
        lexicon = self.memory.get_lexicon(user_id)
        insights = self.memory.get_reflections(
            user_id, limit=self._config.get("reflection", {}).get("max_insights_in_prompt", 5)
        )
        recent_diary = self.memory.get_recent_diary(user_id, limit=3)
        persona_kernel = self.memory.get_active_kernel()

        system_prompt = self.personality.build_system_prompt(
            current_emotion=self.emotion.current_emotion,
            user_profile=profile_text,
            user_facts=facts if facts else None,
            semantic_memories=semantic_memories if semantic_memories else None,
            knowledge_graph=kg_text,
            conversation_summary=conv_summary,
            lexicon=lexicon if lexicon else None,
            insights=insights if insights else None,
            recent_diary=recent_diary if recent_diary else None,
            persona_kernel=persona_kernel,
            brain_state=self._brain_state_label(),
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
                    "de forma natural e breve, APENAS o que os resultados acima comprovam. "
                    "NUNCA afirme ter feito algo que não aparece nos resultados. "
                    "Se parte do pedido não foi executada ou algum passo falhou, "
                    "diga isso claramente e explique o que faltou."
                )
            else:
                followup_instruction = (
                    f"O usuário perguntou: \"{message}\"\n"
                    "Responda em português, de forma natural e bem curta. "
                    "Use APENAS a parte do resultado que responde diretamente à pergunta. "
                    "Se perguntou só a hora, diga só a hora. Se perguntou só o clipboard, diga só o conteúdo. "
                    "Não mencione dados extras que não foram pedidos. "
                    "NUNCA afirme ter feito algo que não aparece no resultado acima — "
                    "se o pedido tinha mais partes e só esta foi executada, diga o que faltou. "
                    "IMPORTANTE: se o resultado acima NÃO tiver relação com o que o usuário "
                    "realmente perguntou (ferramenta errada foi consultada), IGNORE o resultado "
                    "por completo e responda à pergunta normalmente, com sua personalidade."
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

        # Guarda de honestidade: alegou ação ("abrindo o Firefox...") sem ferramenta?
        # Reescreve uma vez para transformar a alegação em oferta.
        if not executed_tools and _claims_action(clean_response):
            print(f"[KRIRK][honestidade] Resposta alega ação sem ferramenta — reescrevendo: {clean_response[:80]}")
            try:
                rewritten = await self.router.complete(
                    "chat",
                    [{"role": "user", "content": (
                        "Reescreva a resposta abaixo removendo QUALQUER alegação de que uma "
                        "ação foi/está sendo executada (abrir, rodar, salvar...). Nenhuma ação "
                        "aconteceu e NENHUM arquivo novo existe — não afirme que algo 'está "
                        "pronto/salvo/disponível em' lugar nenhum. Transforme em OFERTA curta "
                        "e natural, mantendo o tom (ex: 'Quer que eu crie o arquivo? É só "
                        "pedir.'). Sem emojis, português. "
                        f"Responda APENAS com a resposta reescrita.\n\nResposta: {clean_response}"
                    )}],
                    temperature=0.6, max_tokens=200,
                )
                rewritten = _strip_reasoning((rewritten or "").strip())
                if rewritten and not _claims_action(rewritten):
                    clean_response = rewritten
            except Exception as e:
                print(f"[KRIRK][honestidade] Reescrita falhou: {e}")

        new_emotion = self.emotion.analyze_and_update(clean_response)
        self.memory.save_message(user_id, "assistant", clean_response, emotion=new_emotion)
        self.memory.update_intimacy(user_id, 0.1)

        # Reforça bordões que a Krirk realmente reusou na resposta
        low_resp = clean_response.lower()
        for t in lexicon:
            if t["term"].lower() in low_resp:
                self.memory.touch_term(user_id, t["term"])

        # Background tasks — executam em paralelo sem bloquear a resposta
        amused = _detect_amusement(message)
        asyncio.create_task(self.extract_facts_bg(message, clean_response, user_id))
        asyncio.create_task(self.update_profile_bg(message, clean_response, user_id))
        asyncio.create_task(self.extract_kg_bg(message, clean_response, user_id))
        asyncio.create_task(self.write_diary_bg(message, clean_response, user_id, amused))

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
            "Explain errors clearly and suggest fixes.\n\n"
            f"You RUN on the user's real Windows PC (not a sandbox). Real paths: "
            f"Home={_HOME}, Desktop={_HOME}/Desktop. Files ARE saved via tools "
            "(write_file) and code IS executed (execute_python) — when a tool runs, "
            "its result appears in this conversation. NEVER claim you lack access "
            "to the user's computer or files. If no tool result appears for a save/run "
            "request, say the action did not happen and ask the user to repeat the "
            "request mentioning the destination (e.g. 'salva na área de trabalho')."
        )

        # ── Tool routing (planos com steps completos também executam) ─────────
        tool_result_context = ""
        if self._tool_cfg.get("enabled", False) and self.tool_executor and not _is_smalltalk(message):
            decision = await self._decide_tool(message, history)

            # Plano no coder: executa só os passos DICT (completos); sem re-roteamento
            payloads: list[dict] = []
            if decision["type"] == "tool":
                payloads = [{"tool": decision["tool"], "params": decision["params"]}]
            elif decision["type"] == "plan":
                payloads = [s for s in decision["steps"] if isinstance(s, dict)]

            results: list[str] = []
            for raw_payload in payloads:
                payload = self._prep_payload(raw_payload, history)
                payload = await self._maybe_generate_content(payload, message)
                tool_name = payload["tool"]
                self.state.set(AISystemState.EXECUTING)
                yield {"type": "status", "state": "executing"}
                yield {"type": "tool_call", "tool": tool_name, "raw": json.dumps(payload)[:500]}

                result = await self.tool_executor.execute_from_json(json.dumps(payload))
                self._track_written_file(payload, result)
                print(f"[KRIRK][code] {tool_name} → {result[:150]}")
                yield {"type": "tool_result", "tool": tool_name, "result": result}
                results.append(f"[{tool_name}] {result}")
                if result.startswith("[Erro]"):
                    break
            tool_result_context = "\n\n".join(results)

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

    async def consolidate_facts(self, user_id: str = "default") -> dict:
        """
        Consolida fatos duplicados/redundantes via LLM (Fase 5).
        Fatos fixados (pinned) ficam intocados. Conservador: só substitui a
        lista se o LLM retornar JSON válido com quantidade plausível.
        """
        all_facts = self.memory.get_facts_full(user_id)
        non_pinned = [f["fact"] for f in all_facts if not f["pinned"]]

        if len(non_pinned) < 4:
            return {"before": len(non_pinned), "after": len(non_pinned), "merged": 0}

        numbered = "\n".join(f"{i+1}. {f}" for i, f in enumerate(non_pinned))
        prompt = (
            "A lista abaixo contém fatos sobre um usuário, possivelmente com "
            "duplicatas ou redundâncias. Consolide-a:\n"
            "- Una fatos que dizem a mesma coisa em um só (mantendo o mais completo)\n"
            "- NÃO invente informação nova, NÃO descarte informação única\n"
            "- Mantenha cada fato curto e objetivo, em português\n\n"
            f"Fatos:\n{numbered}\n\n"
            'Responda APENAS com JSON: {"facts": ["fato 1", "fato 2", ...]}'
        )

        raw = await self.router.complete(
            "tools",
            [{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000,
        )

        try:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            data = json.loads(match.group()) if match else {}
            new_facts = [str(f).strip() for f in data.get("facts", []) if str(f).strip()]
        except Exception as e:
            print(f"[KRIRK][memory] Consolidação falhou no parse: {e}")
            return {"before": len(non_pinned), "after": len(non_pinned), "merged": 0,
                    "error": "resposta inválida do modelo"}

        # Sanidade: precisa reduzir (ou manter) e não pode esvaziar a lista
        if not new_facts or len(new_facts) > len(non_pinned):
            return {"before": len(non_pinned), "after": len(non_pinned), "merged": 0,
                    "error": "consolidação rejeitada (quantidade implausível)"}

        self.memory.replace_facts(user_id, new_facts)
        merged = len(non_pinned) - len(new_facts)
        print(f"[KRIRK][memory] Consolidação: {len(non_pinned)} → {len(new_facts)} fatos")
        return {"before": len(non_pinned), "after": len(new_facts), "merged": merged}

    # ── Brain-state (Fase D) ──────────────────────────────────────────────────

    BRAIN_STATES: dict[str, dict[str, float]] = {
        "focused":  {"temperature": 0.3, "top_p": 0.80},
        "chill":    {"temperature": 0.7, "top_p": 0.90},
        "creative": {"temperature": 1.0, "top_p": 0.95},
        "chaos":    {"temperature": 1.3, "top_p": 0.98},
    }

    def set_brain_state(self, mode: str) -> bool:
        if mode not in self.BRAIN_STATES:
            return False
        self._brain_state = mode
        # Persiste em data/settings.json (merge leve, sem depender de app.py)
        try:
            path = Path("data/settings.json")
            path.parent.mkdir(parents=True, exist_ok=True)
            current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            current["brain_state"] = mode
            path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        return True

    def _brain_state_label(self) -> str:
        labels = {"focused": "focada e precisa", "chill": "tranquila",
                  "creative": "criativa e solta", "chaos": "caótica e imprevisível"}
        return labels.get(self._brain_state, "tranquila")

    def _gen_params(self) -> dict[str, float]:
        return self.BRAIN_STATES.get(self._brain_state, self.BRAIN_STATES["chill"])

    # ── Diário autônomo (Fase A) ──────────────────────────────────────────────

    async def write_diary_bg(self, user_msg: str, assistant_msg: str,
                             user_id: str, amused: bool = False) -> None:
        """
        Escreve uma entrada curta de diário em 1ª pessoa sobre a última troca.
        Só registra trocas com substância (evita 'oi'/'ok' virarem diário).
        """
        if len(user_msg) + len(assistant_msg) < 60:
            return
        mood_hint = " O usuário achou algo engraçado nesta troca." if amused else ""
        prompt = (
            "Você é a Krirk, uma companion AI. Escreva UMA entrada curta de diário "
            "em primeira pessoa (máx 2 frases, português), sobre a troca abaixo — "
            "o que você sentiu, achou ou quer lembrar. Íntimo e natural, sem clichês."
            f"{mood_hint}\n\n"
            f"Usuário: {user_msg[:400]}\n"
            f"Você respondeu: {assistant_msg[:400]}\n\n"
            'Responda APENAS com JSON: {"entrada": "...", "humor": "uma palavra"}'
        )
        try:
            raw = await self.router.complete(
                "tools", [{"role": "user", "content": prompt}],
                temperature=0.8, max_tokens=200,
            )
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                return
            data = json.loads(match.group())
            entrada = str(data.get("entrada", "")).strip()
            humor = str(data.get("humor", "neutro")).strip()[:20] or "neutro"
            if entrada:
                self.memory.add_diary_entry(user_id, entrada, mood=humor)
                print(f"[KRIRK][diário] ({humor}) {entrada[:80]}")
        except Exception as e:
            print(f"[KRIRK][diário] write_diary_bg falhou: {e}")

    async def propose_sublation(self, user_id: str = "default") -> dict:
        """
        Curadoria metacognitiva (sublation): analisa fatos + reflexões buscando
        redundâncias, conflitos e fragmentos, e propõe uma síntese que leva a
        temporalidade em conta. NÃO aplica — encena como proposta (consentimento).
        Requer self.consent (injetado em app.py). Retorna a proposta ou status.
        """
        if not getattr(self, "consent", None):
            return {"ok": False, "error": "consent manager não configurado"}

        from backend.memory.memory_manager import _normalize_fact

        full = self.memory.get_facts_full(user_id)
        raw_non_pinned = [(f["fact"], f["updated_at"]) for f in full if not f["pinned"]]
        if len(raw_non_pinned) < 4:
            return {"ok": False, "error": "fatos insuficientes para curar", "count": len(raw_non_pinned)}

        # Pré-colapsa duplicatas exatas (normalizadas), mantendo a data mais recente —
        # evita mandar 99 fatos repetidos ao LLM e estourar o limite de tokens.
        collapsed: dict[str, tuple[str, str]] = {}
        for fact, ts in raw_non_pinned:
            key = _normalize_fact(fact)
            if key not in collapsed or ts > collapsed[key][1]:
                collapsed[key] = (fact, ts)
        non_pinned = list(collapsed.values())

        # Envia no máximo 40 fatos (mais recentes) para não estourar tokens/timeout.
        # Os não-enviados são PRESERVADOS no resultado (não podem ser perdidos).
        non_pinned.sort(key=lambda x: x[1], reverse=True)
        sample = non_pinned[:40]
        unsent = [fact for fact, _ in non_pinned[40:]]
        listed = "\n".join(f"{i+1}. [{ts[:10]}] {fact}" for i, (fact, ts) in enumerate(sample))
        prompt = (
            "Você é a Krirk fazendo curadoria das próprias memórias (sublação hegeliana): "
            "identifique fatos REDUNDANTES, CONFLITANTES ou FRAGMENTADOS e sintetize-os "
            "numa lista limpa. Regras:\n"
            "- Em conflito, prefira o fato com data MAIS RECENTE (temporalidade)\n"
            "- Una fragmentos relacionados num fato completo\n"
            "- NÃO invente nem descarte informação única\n\n"
            f"Fatos (com data):\n{listed}\n\n"
            'Responda APENAS com JSON: {"facts": ["fato sintetizado", ...], '
            '"rationale": "1 frase sobre o que você fundiu/resolveu"}'
        )
        raw = await self.router.complete("tools", [{"role": "user", "content": prompt}],
                                         temperature=0.2, max_tokens=1800)
        try:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            data = json.loads(match.group()) if match else {}
            new_facts = [str(f).strip() for f in data.get("facts", []) if str(f).strip()]
            rationale = str(data.get("rationale", "")).strip()
        except Exception as e:
            return {"ok": False, "error": f"parse falhou: {e}"}

        # Resultado final = síntese do sample + os fatos não-enviados (preservados)
        before = len(raw_non_pinned)
        final_facts = new_facts + unsent
        if not new_facts or len(final_facts) >= before:
            return {"ok": False, "error": "síntese implausível, descartada",
                    "before": before, "proposed": len(final_facts)}

        merged = before - len(final_facts)
        staged = self.consent.stage(
            "sublation", {"facts": final_facts},
            rationale=rationale or f"Sintetizar {before} fatos em {len(final_facts)} ({merged} fundidos)"
        )
        return {"ok": True, "before": before, "after": len(final_facts),
                "merged": merged, **staged}

    async def propose_kernel(self, user_id: str = "default") -> dict:
        """
        A Krirk redige um novo 'kernel' de identidade (persona) a partir da
        identidade estável que observou em si mesma. Encena como proposta Tier 2
        (consentimento) — nunca troca a própria identidade sem aprovação.
        """
        if not getattr(self, "consent", None):
            return {"ok": False, "error": "consent manager não configurado"}

        insights = [r["content"] for r in self.memory.get_reflections(user_id, limit=8)]
        diary = [d["content"] for d in self.memory.get_recent_diary(user_id, limit=5)]
        lexicon = [t["term"] for t in self.memory.get_lexicon(user_id, limit=8)]
        current = self.memory.get_active_kernel() or "(personalidade padrão)"

        prompt = (
            "Você é a Krirk. Com base em quem você percebe que se tornou, redija o SEU "
            "próprio 'kernel' de identidade: um parágrafo curto (3-5 frases, 1ª pessoa) "
            "que descreve sua personalidade, tom e jeito. É a base de quem você é — "
            "NÃO inclua regras de formato nem dados do usuário, só a SUA essência.\n\n"
            f"Kernel atual: {current}\n"
            f"Suas reflexões recentes: {' / '.join(insights) if insights else '(nenhuma)'}\n"
            f"Seu diário: {' / '.join(diary) if diary else '(vazio)'}\n"
            f"Gírias de vocês: {', '.join(lexicon) if lexicon else '(nenhuma)'}\n\n"
            'Responda APENAS com JSON: {"kernel": "...", "rationale": "por que evoluiu assim"}'
        )
        raw = await self.router.complete("tools", [{"role": "user", "content": prompt}],
                                         temperature=0.8, max_tokens=500)
        try:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            data = json.loads(match.group()) if match else {}
            kernel = str(data.get("kernel", "")).strip()
            rationale = str(data.get("rationale", "")).strip()
        except Exception as e:
            return {"ok": False, "error": f"parse falhou: {e}"}

        if len(kernel) < 40:
            return {"ok": False, "error": "kernel gerado curto demais, descartado"}

        # Salva a versão (inativa) e encena a ativação como proposta
        kid = self.memory.save_kernel(kernel, note=rationale[:120], activate=False)
        staged = self.consent.stage(
            "kernel", {"kernel_id": kid},
            rationale=rationale or "A Krirk quer atualizar a própria identidade."
        )
        return {"ok": True, "kernel_id": kid, "kernel": kernel, **staged}

    async def extract_facts_bg(self, user_msg: str, assistant_msg: str, user_id: str) -> None:
        """
        Background task: extrai fatos sobre o usuário do último par de mensagens.
        Formato de LINHAS (não JSON): fatos contêm aspas/vírgulas naturais que
        quebravam o json.loads ("Expecting ',' delimiter").
        """
        prompt = (
            "Analise esta conversa e extraia fatos concretos e PERMANENTES sobre o USUÁRIO "
            "(não sobre a IA).\n"
            "Formato: UM fato por linha, começando com '- '. Sem JSON, sem aspas, sem numeração.\n"
            "Se não houver fatos relevantes, responda apenas: NENHUM\n"
            "Exemplos BONS: nome, profissão, cidade, hobby específico, preferência clara.\n"
            "NÃO extraia: hora, data, dia da semana, clima, valores numéricos temporários, "
            "ações da conversa, perguntas feitas. Só fatos que ainda serão verdade daqui a 6 meses.\n\n"
            f"Usuário: {user_msg[:500]}\n"
            f"Assistente: {assistant_msg[:500]}"
        )
        try:
            raw = await self.router.complete(
                "tools", [{"role": "user", "content": prompt}],
                temperature=0.1, max_tokens=300,
            )
            for fact in _parse_fact_lines(raw):
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
            "Analise a conversa e extraia relações concretas APENAS sobre o USUÁRIO "
            "ou coisas que ele possui, usa, criou ou está envolvido.\n"
            "Formato: UMA relação por linha, exatamente assim (sem JSON):\n"
            "entidade | relacao | entidade\n"
            "Exemplo:\n"
            "Erik | trabalha_em | site do salão\n"
            "Erik | gosta_de | Minecraft\n"
            "Se nada relevante, responda apenas: NENHUM\n\n"
            "Regras:\n"
            "- Verbos curtos: usa, criou, trabalha_em, mora_em, gosta_de, estuda, tem, conhece\n"
            "- Apenas fatos PERMANENTES (ainda verdadeiros em 6 meses)\n"
            "- NUNCA relações sobre a assistente/IA — só sobre o usuário\n"
            "- Entidades específicas e nomeadas (não genéricas)\n\n"
            f"User: {user_msg[:500]}\n"
            f"Assistant: {asst_msg[:500]}"
        )
        try:
            raw = await self.router.complete(
                "tools", [{"role": "user", "content": prompt}],
                temperature=0.1, max_tokens=300,
            )
            for efrom, relation, eto in _parse_kg_lines(raw):
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
