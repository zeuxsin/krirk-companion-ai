# KRIRK — Companion AI Desktop

> Companion AI local-first para Windows com personalidade, voz, memória e controle do PC.  
> Sem APIs de nuvem. Sem assinatura. Roda inteiramente no seu computador.

---

## O que é

KRIRK é uma companion AI de desktop inspirada em projetos como Neuro-sama e Monica. Ela conversa com você em português, fala em voz alta, ouve pelo microfone, lembra do que você disse e pode controlar o PC por comando de voz ou texto.

Toda a inferência acontece localmente via **Ollama** — sem enviar nenhum dado para servidores externos.

---

## Funcionalidades

| Categoria | Recursos |
|-----------|----------|
| **Conversa** | Chat streaming com personalidade persistente |
| **Voz** | TTS (edge-tts pt-BR) + STT (Whisper local via faster-whisper) |
| **Memória** | Fatos, perfil de usuário, Knowledge Graph e memória semântica (ChromaDB) |
| **Context Management** | Resumo automático do histórico para conversas longas |
| **Ferramentas** | Abrir sites, apps, timers, volume, mídia, clipboard, PowerShell, busca web e mais |
| **Proativo** | Comenta o que vê na tela e detecta troca de música no Spotify |
| **Desktop** | Janela nativa Windows (Tauri), system tray, hotkey global **Alt+K** |
| **Configurações** | UI completa: modelos, personalidade, memória, hardware |

---

## Pré-requisitos

### 1 — Ollama
Baixe em [ollama.com/download](https://ollama.com/download) e instale.  
Em seguida, baixe os modelos necessários:

```bash
ollama pull gemma3:4b          # modelo principal de chat
ollama pull qwen2.5-coder:7b   # roteamento de ferramentas e extração
ollama pull nomic-embed-text   # embeddings para memória semântica
```

### 2 — Python 3.11
Recomendado: **Python 3.11.x** (3.14 tem incompatibilidades com pacotes de áudio/AI).  
Download: [python.org/downloads](https://www.python.org/downloads/release/python-3119/)  
⚠️ Marque **"Add Python to PATH"** durante a instalação.

### 3 — Node.js 20+ (LTS)
Download: [nodejs.org](https://nodejs.org/en/download)

### 4 — Rust + Cargo
Necessário para compilar o frontend Tauri.  
Download: [rustup.rs](https://rustup.rs/)

```bash
rustup update stable
```

### 5 — Git
Download: [git-scm.com](https://git-scm.com/download/win)

> **Dica:** Se o `git push` falhar com erro SSL, rode:
> ```bash
> git config --global http.sslBackend schannel
> ```

---

## Instalação

```bash
# 1. Clonar o repositório
git clone https://github.com/zeuxsin/krirk-companion-ai.git
cd krirk-companion-ai

# 2. Instalar dependências Python
pip install -r requirements.txt

# 3. Instalar dependências do frontend
cd frontend
npm install
cd ..
```

---

## Como rodar

### Modo desenvolvimento (recomendado para começar)

**Terminal 1 — Backend:**
```bash
python main.py
```
O servidor FastAPI sobe em `http://localhost:8000`.

**Terminal 2 — Frontend React (browser):**
```bash
cd frontend
npm run dev
```
Abre em `http://localhost:5173`.

### Modo app nativo (janela Windows com Tauri)

```bash
cd frontend
npm run tauri dev
```
> A primeira compilação Rust leva ~5 minutos. As seguintes são rápidas.

---

## Configuração

Todos os parâmetros ficam em `configs/config.yaml`:

```yaml
ollama:
  model: "gemma3:4b"        # modelo de chat (pode trocar por llama3.2, phi4-mini…)
  temperature: 0.85
  max_tokens: 1024

tts:
  enabled: true
  voice: "pt-BR-FranciscaNeural"

stt:
  enabled: true
  model: "base"             # tiny / base / small / medium

context_management:
  max_history_tokens: 3000  # acima disto, ativa resumo automático
  keep_recent: 8            # mensagens recentes sempre mantidas verbatim

proactive:
  enabled: true
  check_interval: 30        # segundos entre verificações de tela
```

A **personalidade** da KRIRK fica em `configs/personality.json`:

```json
{
  "name": "Krirk",
  "initial_emotion": "neutral",
  "custom_notes": ""
}
```

Você também pode editar tudo isso pela interface gráfica em **Configurações** (⚙️).

---

## Hotkeys

| Atalho | Ação |
|--------|------|
| `Alt+K` | Mostrar / ocultar a janela (global — funciona em qualquer janela) |
| `✕` na janela | Oculta para a bandeja (não fecha o processo) |

---

## Estrutura do projeto

```
KRIRK/
├── backend/
│   ├── api/            # FastAPI — endpoints REST e WebSocket
│   ├── core/           # Orchestrator, Personality, Proactive Monitor
│   ├── memory/         # MemoryManager, KnowledgeGraph, ProfileManager, VectorStore
│   ├── tools/          # Registry, Executor e ferramentas built-in
│   ├── voice/          # TTS (edge-tts) e STT (faster-whisper)
│   └── vision/         # Captura de tela (mss + Pillow)
├── configs/
│   ├── config.yaml     # Configuração principal
│   └── personality.json
├── frontend/
│   ├── src/            # React + TypeScript
│   └── src-tauri/      # Rust (Tauri v2) — janela nativa e hotkeys
├── data/               # SQLite + ChromaDB (gerado automaticamente, gitignored)
├── main.py             # Entrypoint do backend
└── requirements.txt
```

---

## Arquitetura

```
┌─────────────────────────────────────────────┐
│              Frontend (Tauri)               │
│  React UI  ←→  WebSocket  ←→  REST API     │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│           Backend (FastAPI)                 │
│                                             │
│  Orchestrator                               │
│  ├─ gemma3:4b    ← chat + personalidade     │
│  ├─ qwen2.5-coder ← ferramentas + extração  │
│  ├─ nomic-embed  ← memória semântica        │
│  ├─ STT (Whisper) ← microfone → texto       │
│  ├─ TTS (edge-tts) ← texto → áudio          │
│  └─ Tools (20+)  ← controle do PC          │
│                                             │
│  Memory Layer                               │
│  ├─ SQLite  ← fatos, perfil, KG, summaries │
│  └─ ChromaDB ← busca vetorial semântica     │
└─────────────────────────────────────────────┘
```

---

## Solução de problemas

| Problema | Solução |
|----------|---------|
| `Connection refused localhost:11434` | Ollama não está rodando. Abra o app ou rode `ollama serve` |
| `Model not found` | Execute `ollama pull gemma3:4b` (e os outros modelos) |
| `cublas64_12.dll not found` | Erro de GPU no Whisper — já corrigido para CPU no código |
| `cargo: command not found` | Rust não instalado — use [rustup.rs](https://rustup.rs/) |
| `faster-whisper not installed` | `pip install faster-whisper` |
| STT não transcreve nada | Ative em Configurações → Modelos → toggle STT |
| Tauri não compila | Certifique-se que Node 20+ e Rust stable estão instalados |

---

## Roadmap

- [x] MVP conversacional (chat + TTS + memória + personalidade)
- [x] STT local (Whisper) + Knowledge Graph + 20 ferramentas desktop
- [x] Context Management (resumo automático do histórico)
- [x] Hotkey global + system tray + configurações completas
- [ ] Avatar Live2D com lip-sync e expressões faciais
- [ ] Multimodalidade avançada (OCR + análise de código na tela)
- [ ] Automação com Playwright (preencher formulários, navegar)
- [ ] Memória de longo prazo refinada (Qdrant)
- [ ] Plugins e API pública

---

## Licença

MIT — faça o que quiser, mas mencione a origem se redistribuir.
