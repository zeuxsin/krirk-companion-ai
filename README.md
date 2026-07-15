# KRIRK — Companion AI Desktop

> Companion AI pessoal para Windows com personalidade, voz, memória de longo prazo,
> emoções visuais e controle do PC.
> Local-first via Ollama, com fallback automático para APIs cloud gratuitas.

---

## O que é

KRIRK é uma companion AI de desktop inspirada em projetos como Neuro-sama e Hakko AI.
Ela conversa em português, fala em voz alta, ouve pelo microfone, lembra do que você
disse (e esquece o que ficou obsoleto), demonstra emoções com um avatar próprio e
executa tarefas no computador: abre apps, digita, lê a tela, navega na web e mais.

Projeto de **uso pessoal** — single-user, rodando no próprio PC.

---

## Funcionalidades

| Categoria | Recursos |
|-----------|----------|
| **Conversa** | Chat streaming com personalidade persistente (pt-BR) |
| **Multi-provider** | NVIDIA NIM → Google → Cerebras → Ollama com fallback automático e circuit breaker |
| **Voz** | TTS (edge-tts pt-BR) + STT (Whisper local via faster-whisper) |
| **Emoções** | 20 emoções com imagens de avatar, animações CSS e cores próprias |
| **Memória** | Curto prazo, fatos com dedupe + decay (esquecimento gradual), memórias fixadas ("lembra disso"), busca por período ("o que falamos semana passada?"), Knowledge Graph e memória semântica (ChromaDB) |
| **Agente** | Planner multi-etapas: decompõe pedidos como "abre o bloco de notas e digita X" em sequências de ferramentas |
| **Ferramentas (36+)** | Apps, sites, timers, volume, mídia, clipboard, PowerShell, arquivos, busca web, OCR de tela, teclado (atalhos/digitação), janelas, leitura de páginas |
| **Browser automatizado** | Playwright (Edge/Chrome): abre, lê, clica e preenche páginas — você vê a janela |
| **Visão** | Screenshot + upload de imagem analisados por modelo de visão (NVIDIA → gemma3 local) |
| **Proativo** | Comenta o que vê na tela e detecta troca de música no Spotify |
| **Plugins** | Solte um `.py` em `plugins/` com `register(registry)` e vira ferramenta da KRIRK |
| **API pública** | `POST /api/chat` e `GET /api/tools` para integrar scripts externos |
| **Desktop** | Janela nativa (Tauri v2), 4 modos de UI, avatar flutuante independente, system tray, hotkey global **Alt+K** |
| **Modo Coder** | Sessão separada do chat, visual de terminal, execução de Python |

---

## Pré-requisitos

### 1 — Ollama
Baixe em [ollama.com/download](https://ollama.com/download) e instale os modelos:

```bash
ollama pull gemma3:4b          # chat local + visão (fallback)
ollama pull qwen2.5-coder:7b   # roteamento de ferramentas (fallback)
ollama pull nomic-embed-text   # embeddings para memória semântica
```

### 2 — Python 3.11+ · Node.js 20+ · Rust (para o Tauri)

### 3 — Chaves de API (opcionais, mas recomendadas)
Copie `.env.example` para `.env` e preencha `NVIDIA_API_KEY`, `GOOGLE_API_KEY`,
`CEREBRAS_API_KEY` (free tiers). Sem elas, tudo roda 100% local via Ollama.

---

## Instalação

```bash
git clone https://github.com/zeuxsin/krirk-companion-ai.git
cd krirk-companion-ai

pip install -r requirements.txt
playwright install chromium        # browser automatizado (usa Edge/Chrome se falhar)

cd frontend
npm install
```

---

## Como rodar

```bash
# Terminal 1 — backend
python main.py                     # http://localhost:8000

# Terminal 2 — app desktop
cd frontend
npm run tauri dev
```

Ou frontend no browser (dev): `npm run dev` → http://localhost:5173

---

## Exemplos de comandos

- *"abre o bloco de notas e digita uma lista de compras"* — planner multi-etapas
- *"lê o que está na minha tela"* — OCR via modelo de visão
- *"o que a gente conversou semana passada?"* — busca temporal na memória
- *"lembra disso: minha senha do wifi está no caderno azul"* — memória fixada
- *"abre o site X no seu browser e me diz o que está escrito"* — browser automatizado
- *"rola um d20"* — plugin de exemplo

---

## Estrutura

```
KRIRK/
├── backend/
│   ├── agents/       planner.py (decisões multi-etapas)
│   ├── api/          FastAPI + WebSocket + API pública
│   ├── core/         orchestrator, personalidade, proativo
│   ├── memory/       SQLite + ChromaDB + KG + decay/dedupe
│   ├── providers/    router multi-provider com circuit breaker
│   ├── tools/        registry, executor, plugin_loader, builtin/
│   ├── voice/        TTS + STT
│   └── vision/       captura de tela
├── frontend/         React + TypeScript + Tauri v2
├── plugins/          seus plugins (.py com register(registry))
├── configs/          config.yaml + personality.json
├── tests/            test_unit.py (offline) + test_krirk.py (integração)
└── data/             SQLite + ChromaDB (gitignored — dados pessoais)
```

Documentação técnica completa: [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)

---

## Testes

```bash
# Offline (sem rede/Ollama) — rápido
.venv\Scripts\python.exe tests\test_unit.py

# Integração (chama APIs reais e Ollama)
.venv\Scripts\python.exe tests\test_krirk.py
```

---

## Configuração

| Arquivo | Propósito |
|---------|-----------|
| `configs/config.yaml` | Modelos por provider/tarefa, TTS/STT, memória, tools (whitelist), plugins, proativo |
| `configs/personality.json` | Nome, emoção inicial e notas de personalidade |
| `.env` | Chaves de API (nunca commitado) |
| `data/settings.json` | Settings de runtime persistidos (gerado automaticamente) |

## Hotkeys

| Ação | Atalho |
|------|--------|
| Mostrar/ocultar KRIRK | **Alt+K** (global) |
| Ocultar para bandeja | Botão ✕ da janela |
