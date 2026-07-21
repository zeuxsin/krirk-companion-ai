# CLAUDE.md — Instruções para sessões de desenvolvimento

> Leia `PROJECT_CONTEXT.md` primeiro — é a memória técnica completa do projeto.

## O que é

KRIRK — Companion AI de desktop (FastAPI + React/Tauri v2), local-first com
fallback cloud. Single-user. Detalhes de arquitetura no PROJECT_CONTEXT.md.

## Comandos essenciais

```powershell
.venv\Scripts\python.exe main.py           # backend :8000
cd frontend; npm run dev                   # frontend browser :5173
cd frontend; npm run tauri dev             # app desktop
cd frontend; npx tsc --noEmit              # checagem de tipos (rodar após TODA mudança TS)
.venv\Scripts\python.exe -m compileall backend main.py -q   # sintaxe Python
.venv\Scripts\python.exe tests\test_unit.py   # suite OFFLINE (500+ testes) — RODAR APÓS TODA MUDANÇA
```

`tests\test_unit.py` é a validação padrão (offline, sem rede). Já a suite
`tests\test_krirk.py` faz chamadas REAIS às APIs cloud e ao Ollama — só rodar
com autorização do usuário.

O usuário costuma rodar `python main.py` com reload — edições em `backend/*.py`
aplicam sozinhas na instância dele. ATENÇÃO: o reload vigia SÓ `backend/`
(`reload_dirs`); mudanças em `configs/config.yaml` exigem reiniciar o main.py.

## Regras obrigatórias

1. **Segredos**: chaves de API vivem SOMENTE em `.env` (gitignored). NUNCA
   hardcodar, logar, exibir ou commitar valores de chaves.
2. **Emoções**: exatamente 20, em português, definidas em
   `frontend/src/types/index.ts` e `backend/emotions/emotion_engine.py`.
   Ao adicionar/renomear: atualizar AMBOS + `utils/emotions.ts` (IMG/COLOR/ANIM)
   + PNGs em `public/avatar/` e `public/avatar/chat/`.
3. **Ícones**: lucide-react. Nunca emoji ou SVG inline na UI.
4. **Idioma**: UI, respostas da IA e comentários de código em pt-BR.
5. **Históricos separados**: chat usa `addChatMsg`/`messages`; coder usa
   `addCodeMsg`/`codeMessages`. Streaming usa `activeSessionRef`. Não
   reintroduzir um `addMsg` compartilhado em componentes.
6. **Tauri**: toda API de janela nova exige permissão em
   `capabilities/default.json` (falha silenciosa se faltar). Novas janelas:
   `tauri.conf.json` + array `windows` das capabilities.
7. **Posicionamento de janela**: usar `current_monitor()` no Rust; nunca
   `window.center()` (quebra dual-monitor).
8. **Providers**: novos modelos/providers entram em
   `backend/providers/router.py` (TASK_MODELS/TASK_FALLBACK) e
   `configs/config.yaml`; nunca chumbar modelo em outro lugar.
9. **Código substancial**: a tool `delegate_code` abre a JANELA REAL do Claude
   Code (modo interativo padrão, workspace `Krirk Code/`, modelo sonnet) —
   `backend/integrations/claude_code.py`, registrada no `app.py`. Sem cota →
   fallback gera 1 arquivo com o modelo de código da nuvem; sem CLI →
   `write_file + <GENERATE>`. No modo headless, prompt via STDIN, nunca argv.
10. **Honestidade é sagrada**: as camadas anti-alucinação de ação
   (`_ACTION_CLAIM_RE`, aceite determinístico de oferta `_is_acceptance`/
   `_pending_offer`, resposta canned pós-delegação, regra ACCEPTED OFFER no
   roteador) foram construídas caso a caso a partir de bugs REAIS — nunca
   enfraquecer sem validar os cenários da suite (seções 20 e 24 do test_unit).

## Não alterar sem necessidade explícita

- `_stream_strip_reasoning` (orchestrator.py) — filtro de tags `<think>`.
- Pipeline de 2 fases do orchestrator (tool routing → resposta).
- `_safe_path` em file_tools.py (sandbox: home + `tools.allowed_dirs`;
  caminho relativo resolve contra o Desktop).
- `.gitignore` de `data/` e `.env`.

## Erros comuns a evitar

- Esquecer `npx tsc --noEmit` após editar TS (noUnusedLocals pega variável morta).
- Adicionar chamada de janela Tauri sem a permissão correspondente → falha
  silenciosa, difícil de debugar.
- Usar nomes de emoção em inglês (legado removido; `normalizeEmotion()` só
  existe para compatibilidade com dados antigos do banco).
- Commitar `data/` (contém memória pessoal do usuário).
- PowerShell 5.1: sem `&&`, sem heredoc bash. Mensagens de commit multilinhas:
  escrever num arquivo temporário e usar `git commit -F <arquivo>` (here-strings
  quebram com acentos/aspas).
- `asyncio.create_subprocess_*` NÃO funciona sob o uvicorn no Windows
  (SelectorEventLoop → NotImplementedError de mensagem VAZIA). Subprocessos em
  tools: `subprocess.run` bloqueante via `asyncio.to_thread` (padrão em
  system_tools/code_tools/claude_code).

## Componentes legados (não usados, não deletar sem confirmar)

`ChatWindow.tsx`, `MessageBubble.tsx`, `AvatarWidget.tsx`, `EmotionIndicator.tsx`.
