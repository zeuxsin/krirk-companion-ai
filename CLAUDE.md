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
```

A suite `tests\test_krirk.py` faz chamadas REAIS às APIs cloud e ao Ollama —
só rodar com autorização do usuário.

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

## Não alterar sem necessidade explícita

- `_stream_strip_reasoning` (orchestrator.py) — filtro de tags `<think>`.
- Pipeline de 2 fases do orchestrator (tool routing → resposta).
- `_safe_path` em file_tools.py (restrição de segurança ao home).
- `.gitignore` de `data/` e `.env`.

## Erros comuns a evitar

- Esquecer `npx tsc --noEmit` após editar TS (noUnusedLocals pega variável morta).
- Adicionar chamada de janela Tauri sem a permissão correspondente → falha
  silenciosa, difícil de debugar.
- Usar nomes de emoção em inglês (legado removido; `normalizeEmotion()` só
  existe para compatibilidade com dados antigos do banco).
- Commitar `data/` (contém memória pessoal do usuário).
- PowerShell 5.1: sem `&&`, sem heredoc bash — usar here-strings `@'…'@` para
  mensagens de commit multilinhas.

## Componentes legados (não usados, não deletar sem confirmar)

`ChatWindow.tsx`, `MessageBubble.tsx`, `AvatarWidget.tsx`, `EmotionIndicator.tsx`.
