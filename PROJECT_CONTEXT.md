# PROJECT_CONTEXT.md — Memória técnica do KRIRK

> Atualizado em 2026-06-22 (commit `f1c007f`). Este arquivo é a referência para
> futuras sessões de desenvolvimento. Atualize-o quando a arquitetura mudar.

## Visão geral

KRIRK é uma **Companion AI de desktop** (inspiração: Neuro-sama / Hakko AI):
assistente com personalidade própria, voz, memória persistente, emoções visuais
e controle do PC do usuário. Local-first (Ollama), com fallback para APIs cloud
gratuitas. Single-user (`user_id` fixo `"default"`).

## Stack

| Camada | Tecnologia | Onde |
|---|---|---|
| Backend | Python 3.14 (venv `.venv`) + FastAPI + WebSocket | `backend/`, `main.py` |
| LLM routing | Multi-provider: NVIDIA NIM → Google → Cerebras → Ollama | `backend/providers/` |
| LLM local | Ollama (gemma3:4b chat, qwen2.5-coder:7b tools/code, nomic-embed-text) | `configs/config.yaml` |
| TTS | edge-tts `pt-BR-FranciscaNeural` (requer internet) | `backend/voice/tts.py` |
| STT | faster-whisper CPU, modelo "base", local | `backend/voice/stt.py` |
| Memória | SQLite (`data/memory.db`) + ChromaDB (`data/chroma/`) | `backend/memory/` |
| Frontend | React 18 + TypeScript + Vite (porta 5173) | `frontend/src/` |
| Desktop | Tauri v2 (Rust) — 3 janelas: main, settings, krirk-float | `frontend/src-tauri/` |
| Ícones UI | lucide-react (NUNCA emojis na UI) | — |
| Visão | mss + Pillow (screenshot) → modelo de visão | `backend/vision/capture.py` |

## Arquitetura e fluxo principal

```
Frontend (React/Tauri)
   │  WebSocket ws://localhost:8000/ws  (JSON events)
   ▼
backend/api/websocket.py  → dispatch por payload.type:
   chat | code_chat | audio | screenshot | image_chat | settings | status
   ▼
backend/core/orchestrator.py  — pipeline de 2 fases:
   FASE 1: _decide_tool() → parse_decision (backend/agents/planner.py) retorna:
     • {"type":"none"} — sem ferramenta
     • {"type":"tool",...} — loop iterativo até max_rounds (config: 4); cada rodada
       recebe os resultados anteriores. Guardas: decisão repetida / "[Erro]" → break.
     • {"type":"plan","steps":[{"tool","params"},...]} — plano COMPLETO com params,
       executado passo a passo SEM re-roteamento (formato robusto p/ modelos pequenos).
       Passos string (legado) são re-roteados com o pedido original anexado.
       Plano sem nenhum passo executado → contexto força resposta honesta.
   FASE 2: router.stream("chat"|"code", …) → resposta final streamada token a token
   + background tasks (asyncio.create_task): extract_facts_bg, update_profile_bg,
     extract_kg_bg, _summarize_history_bg
   ▼
backend/providers/router.py — ProviderRouter com fallback automático
   TASK_FALLBACK: chat/tools=[nvidia,google,cerebras,ollama], …
   Erros retriables (403/410/429/5xx/timeout/not found/gone) → próximo provider
   Circuit breaker: 2 falhas seguidas pausam o provider por 180s (nunca deixa
   a lista vazia — se todos pausados, usa a ordem completa)
   ATENÇÃO (2026-07): NVIDIA free tier instável — meta/llama-* mortos, só
   mistral-small responde (intermitente). Cerebras: gpt-oss-120b/gemma-4-31b/
   zai-glm-4.7 (llama3.1-* removidos). Verificar catálogos ao debugar timeout.
```

### Eventos WebSocket (backend → frontend)

`connected` (com history), `status` (state), `token`, `response_complete`
(content + emotion + audio b64), `tool_call`, `tool_result`, `transcription`,
`screenshot_taken` (thumbnail), `proactive_comment`, `error`, `ack`, `memory_stats`.

### Frontend — modos e janelas

- `App.tsx` mantém dois históricos separados: `messages` (chat) e `codeMessages`
  (coder). `activeSessionRef` decide para onde vão tokens em streaming;
  `addChatMsg`/`addCodeMsg` são passados aos componentes (NÃO usar o antigo
  `addMsg` genérico em componentes de UI — causou bug de mensagens cruzadas).
- Modos: `chat` (janela normal 560×420, decorações nativas), `code` (mesma
  janela), `sidebar` (compacta 230×400, sem decoração, `CompactHeader` +
  `HudMode`), `avatar` (sem decoração + fundo transparente, `AvatarMode`).
- `adjustWindow(mode)` em App.tsx: invoke `set_compact_mode` (Rust) →
  `setDecorations` → body background.
- **Janela float independente** (`krirk-float` no tauri.conf.json):
  `AvatarFloat.tsx`, renderizada quando `?window=float`. Sincroniza via evento
  Tauri `krirk-update` ({emotion, aiState, message}) emitido pelo App.
  Comandos Rust: `open_avatar_float` / `close_avatar_float`.
- Janela settings: `?window=settings` → `SettingsPage.tsx`.

### Emoções — 20 nomes canônicos em PORTUGUÊS

`neutro, surpresa, pensando, curiosa, cansada, irritada, confusa, feliz,
empolgada, triste, zangada, assustada, envergonhada, timida, concentrada,
orgulhosa, determinada, codando, jogando, tranquila`

- Fonte da verdade frontend: `frontend/src/types/index.ts` (EmotionType) +
  `frontend/src/utils/emotions.ts` (EMOTION_TO_IMG, EMOTION_COLOR, EMOTION_ANIM,
  `normalizeEmotion()` converte nomes ingleses legados).
- Fonte backend: `backend/emotions/emotion_engine.py` (EMOTION_KEYWORDS).
- Imagens: `frontend/public/avatar/{nome}.png` (modo avatar/hud) e
  `frontend/public/avatar/chat/{nome}.png` (avatares 38×38 nas mensagens).
  Mesmos 20 nomes nas duas pastas. Fallback onError → neutro.

## Memória (backend/memory/)

- `memory_manager.py` — SQLite: messages (com `is_proactive` e `session`),
  facts (com `pinned`), user_profile, conversation_summaries + fachada para
  KG e vector store.
- **Longo prazo (Fase 5)**: save_fact deduplica por texto normalizado (reforça
  confiança em vez de duplicar); get_facts aplica decay exponencial (meia-vida
  30 dias, oculta < 0.25); purge_stale_facts no startup apaga não-fixados
  < 0.15 com +90 dias; pin_fact/remember_this cria memórias que nunca decaem;
  search_messages_by_period alimenta a tool search_history ("o que falamos
  semana passada"); POST /api/memory/consolidate mescla fatos redundantes via LLM.
- `knowledge_graph.py` — relações entidade→verbo→entidade em SQLite.
- `profile_manager.py` — perfil estruturado (nome, profissão, interesses…).
- `vector_store.py` — ChromaDB + embeddings nomic-embed-text.
- Context management: histórico acima de ~3000 tokens → recorte para 8 recentes
  + resumo salvo (gerado em background).

## Ferramentas (backend/tools/)

- `registry.py` (build_default_registry(config, memory, router), filtra pela
  whitelist do config.yaml), `executor.py` (timeout padrão 10s; `Tool.timeout`
  sobrescreve por-tool), `base.py` (classe Tool), `plugin_loader.py` (Fase 6).
- Builtin: system_tools (powershell, clipboard, janela ativa…), file_tools
  (read/write/list/search com `_safe_path` restrito ao home + PATH_ALIASES
  "desktop"/"documentos"…), desktop_tools (open_url com aliases+TLD completion,
  open_app com busca em PATH/Program Files/registry, set_timer, volume),
  web_tools (ddgs), media_tools,
  memory_tools (search_memory, search_history, remember_this),
  code_tools (execute_python, subprocess com timeout 8s),
  **vision_tools** (read_screen: OCR da tela via task "ocr" do router, timeout 60s),
  **automation_tools** (press_hotkey/type_text via pyautogui — type_text usa
  clipboard+ctrl+v para texto não-ASCII; list_windows/focus_window via PowerShell;
  fetch_url via httpx + truststore + HTMLParser stdlib),
  **browser_tools** (Playwright: browser_open/read/click/fill/close — sessão
  Chromium persistente headed; canais msedge → chrome → bundled, pois o
  chromium bundled dá erro SxS nesta máquina).
- Whitelist em `configs/config.yaml → tools.whitelist`.
- **delegate_code** (`backend/integrations/claude_code.py`): delega código
  substancial ao Claude Code CLI (`~\.local\bin\claude.exe`; fallback
  `shutil.which`). Headless: `-p --output-format json --permission-mode
  acceptEdits --max-turns N`, prompt via STDIN (nunca argv — aspas/acentos no
  Windows). Roda em BACKGROUND (single-slot: 1 tarefa por vez); ao terminar,
  anuncia via `ProactiveMonitor._broadcast_comment(trigger="claude_code")`
  (WS + TTS + Telegram + memória) com diff real de arquivos
  (snapshot mtime antes/depois, ignora __pycache__). Registrada no `app.py`
  (não no build_default_registry) quando `claude_code.enabled` + CLI presente.
  Config: `claude_code:` (model sonnet, timeout 600s, max_turns 30).
  Roteador prioriza p/ código real; `write_file+<GENERATE>` vira fallback.
- **Agenda real (Phantom System)**: o calendário gamificado do usuário vive em
  `C:\calendario` (app web + `server.py` local em http://127.0.0.1:8123;
  save em localStorage — a Krirk NÃO escreve no save). Ponte
  `add_calendar_task`/`list_calendar_tasks` (`calendar_tools.py`), DOIS
  caminhos: (1) POST /api/inbox no server.py — campos ricos (hora separada,
  tipo tarefa/compromisso com XP próprio, boss por nome) e a tela atualiza
  na hora via SSE; (2) fallback `dados\krirk_inbox.js` quando o servidor
  está desligado (app importa no boot via `mergeKrirkInbox()`; hora vai
  embutida no título — a ponte velha não tem o campo). Datas resolvidas
  DETERMINISTICAMENTE em Python (`resolve_date`) e hora normalizada
  (`norm_hora`: "14h"→"14:00") — nunca pelo LLM. Config:
  `tools.calendar_dir` + `tools.calendar_api`. Sandbox: `tools.allowed_dirs`
  libera pastas extras no `_safe_path` (alias pelo nome da pasta).
- **Plugins (Fase 6)**: `plugins/*.py` com `register(registry)` são carregados no
  boot (config `plugins.enabled`). NÃO passam pela whitelist. Erros isolados
  por plugin. Exemplo: `plugins/exemplo_dado.py` (roll_dice).

## Configuração

- `configs/config.yaml` — modelos, TTS/STT, memória, proativo, providers, tools.
- `configs/personality.json` — nome da Krirk, emoção inicial, notas custom.
- `.env` (**NUNCA commitar, NUNCA ler/exibir valores**): `NVIDIA_API_KEY`,
  `GOOGLE_API_KEY`, `CEREBRAS_API_KEY`, e opcionais BACKEND_HOST/PORT etc.
- `data/settings.json` — settings persistidos em runtime (TTS on/off, voz,
  proativo). Gitignored. Aplicado no startup em `app.py`.

## Comandos

```powershell
# Backend (Terminal 1)
cd C:\Krirk_AI\KRIRK
.venv\Scripts\python.exe main.py          # http://localhost:8000

# Frontend browser dev (Terminal 2)
cd frontend; npm run dev                   # http://localhost:5173

# App desktop completo
cd frontend; npm run tauri dev

# Build release
cd frontend; npm run tauri build

# Validações
cd frontend; npx tsc --noEmit                                  # tipos TS
.venv\Scripts\python.exe -m compileall backend main.py -q      # sintaxe Python
.venv\Scripts\python.exe tests\test_krirk.py                   # suite (26 testes;
#   ATENÇÃO: faz chamadas reais às APIs NVIDIA/Google/Cerebras e ao Ollama)
```

## Convenções obrigatórias

- Respostas da Krirk e UI em **pt-BR**; código/comentários em pt-BR.
- Ícones: **lucide-react**, nunca emoji/SVG inline na UI.
- Estilos: inline styles React (objetos JS) + CSS vars `--color-krirk-*`
  definidas em `index.css`. Sem styled-components/Tailwind.
- TS estrito: `noUnusedLocals`/`noUnusedParameters` ativos; JSX transform
  `react-jsx` (não importar React em arquivos só-JSX).
- Tauri: novas permissões vão em `frontend/src-tauri/capabilities/default.json`
  (falhas de permissão são SILENCIOSAS — sempre verificar lá primeiro).
- Novas janelas Tauri: declarar em `tauri.conf.json` E no array `windows` das
  capabilities.
- Commits: mensagens em pt-BR sem acentos no título, prefixos feat/fix/docs.

## Decisões técnicas a preservar

1. **Pipeline 2 fases** (router de tools separado do modelo de personalidade) —
   não fundir em um único modelo com function calling nativo sem discussão.
2. **Fallback multi-provider** com `_is_retriable` — novos providers entram em
   `TASK_MODELS`/`TASK_FALLBACK` no router.py + factory em openai_compat.py.
3. **Históricos chat/coder isolados de ponta a ponta**: frontend usa
   `messages`/`codeMessages`; backend usa a coluna `session` ('chat'|'code')
   na tabela messages. O Coder grava/lê só session='code'; mensagens de
   código não são indexadas no ChromaDB. `connected` envia `history` +
   `code_history`.
4. **`_stream_strip_reasoning`** filtra tags `<think>` em streaming — necessário
   para Google/Gemma; não remover.
5. **Transparência da janela**: `transparent: true` fixo no tauri.conf.json;
   o visual é controlado via `document.body.style.background` por modo.
6. **Dual-monitor**: `set_compact_mode` usa `current_monitor()` +
   `PhysicalPosition` — nunca usar `window.center()` (vai para o monitor primário).

## Problemas conhecidos / dívidas

- **Componentes legados não usados**: `ChatWindow.tsx`, `MessageBubble.tsx`,
  `AvatarWidget.tsx`, `EmotionIndicator.tsx` (nenhum import ativo). Não deletar
  sem confirmar com o usuário.
- **Emoções legadas no banco**: mensagens antigas em `data/memory.db` podem ter
  emotion em inglês; `normalizeEmotion()` no frontend cobre isso.
- `pasta /avatar/chat/` contém `neutra.png` (nome antigo) — o código usa
  `neutro`; verificar/renomear quando o usuário trocar as imagens.
- Endpoints REST de memória (`/api/memory/*`) não têm autenticação — aceitável
  para app local single-user, mas não expor a rede.
- `app.py` usa `@app.on_event("startup")` (deprecado no FastAPI moderno; migrar
  para lifespan handler eventualmente).
- Sem testes do frontend; suite Python depende de rede/chaves.
- `react-router-dom` está nas dependências mas não é usado (roteamento é via
  query param `?window=`).

## Visão multimodal (Fase 3)

- Imagens viajam nas mensagens como chave `"images": [b64, ...]`.
- Ollama aceita o formato nativamente; `openai_compat._to_openai_messages()`
  converte para content-array (image_url data URI) para NVIDIA/Google/Cerebras.
- Rota de visão: router task "vision" (NVIDIA llama-3.2-vision → Ollama gemma3);
  OCR: task "ocr" (NVIDIA phi-4-multimodal → gemma3).
- `capture.py`: capture_screen(monitor), capture_region(l,t,w,h), capture_thumbnail.
- Timeout de rede sobe para 45s automaticamente quando a mensagem tem imagens.

## API pública (Fase 6)

- `POST /api/chat` {message, user_id?, include_audio?} → {response, emotion,
  tools_used[], audio?} — resposta completa, sem streaming, para integrações.
- `GET /api/tools` → lista de tools registradas (builtin + plugins) com params.

## Interioridade escafoldada (diário, sonhos, identidade)

Camada de "vida interior autônoma" inspirada no companion do LocalLLaMA.
Armazéns em `memory_manager.py`: `lexicon`, `reflections`, `diary`,
`learning_notes`, `kernel_versions`, `pending_proposals`.

- **Memes internos**: tool `coin_term` cunha bordões (injetados no prompt,
  `touch_term` reforça o uso); `search_meme` busca gírias na web. `_detect_amusement`
  marca trocas engraçadas.
- **Diário autônomo**: `write_diary_bg` escreve entrada em 1ª pessoa após trocas
  com substância (bg task no `process_text`).
- **Reflexão** (`backend/core/reflection.py`): `dream()` sintetiza insights/humor/
  bordões + entrada de sonho; `research()` pesquisa um tópico e guarda nota de
  aprendizado. Agendados pelo `ProactiveMonitor` (timestamps em
  `data/reflection_state.json`; dream 3h, research 6h). Modo ativo puxa assunto.
  IMPORTANTE: o loop do ProactiveMonitor inicia se proativo OU reflexão estiverem
  habilitados; o toggle proativo das Configurações controla SÓ tela/Spotify —
  a reflexão roda independente (desacoplado em 2026-07-16).
- **UI Vida Interior**: aba 💭 na SettingsPage — brain-state, kernel (propor/
  ativar/rollback), bordões (excluir via DELETE /api/memory/term), reflexões
  ("Refletir agora"), diário e propostas pendentes (aprovar/recusar).
- **Sublation** (`orchestrator.propose_sublation`): cura fatos redundantes/
  conflitantes com temporalidade. Pré-colapsa dupes exatas, envia ≤40 ao LLM,
  preserva os não-enviados. Encena como proposta.
- **Consentimento** (`backend/core/consent.py`): tiers 0-3; ações Tier≥2 (sublation,
  kernel, wipe) viram `pending_proposals` aprovadas/recusadas pelo usuário. Evento
  WS `consent_request` → card no `App.tsx`.
- **Brain-state**: tool `set_brain_state` (focused/chill/creative/chaos → temperature
  + top_p). `top_p` propaga pelo router→providers. Persiste em settings.json.
- **Kernel auto-autorado**: `propose_kernel` — a Krirk redige a própria persona
  (Tier 2, consentimento); versionada em `kernel_versions` com rollback
  (`/api/kernel/rollback`, kernel_id=0 = padrão). Injetada como `persona_kernel`
  no prompt; o NÚCLEO IMUTÁVEL (formato/segurança) nunca é sobrescrito.
- Endpoints: `/api/reflection/dream|research`, `/api/memory/sublation`,
  `/api/proposals[/{id}/approve|reject]`, `/api/kernel[/propose|/rollback]`,
  `/api/brain_state`.

## Funcionalidades pendentes (roadmap)

- Live2D/lip-sync no avatar (Fase 2 completa do SDD) — único item grande restante.
- Fases 3, 4, 5, 6 e a interioridade escafoldada CONCLUÍDAS e validadas ao vivo.
- "Council" de outras IAs (do post do Reddit) — fora de escopo por ora.
