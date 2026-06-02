# KRIRK — Companion AI Desktop

Projeto de Companion AI Desktop inspirado em Neuro-sama/Monica/HakkoAI.
SDD completo em: `docs/SDD.pdf` (copie o PDF original para cá).

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3.11+ / FastAPI / WebSockets |
| LLM | Ollama local (qwen2.5:7b padrão) |
| TTS | edge-tts (pt-BR-FranciscaNeural) |
| STT | faster-whisper (desabilitado em Py3.14) |
| Memória | SQLite (short/long term) |
| Frontend | React + TypeScript + Vite |
| Avatar | (Fase 2 — Live2D/WebGL) |

## Estrutura

```
KRIRK/
├── backend/
│   ├── core/          # Orquestrador, personalidade, estado
│   ├── api/           # FastAPI app + WebSocket handler
│   ├── memory/        # SQLite memory manager
│   ├── voice/         # STT (faster-whisper) + TTS (edge-tts)
│   ├── emotions/      # Máquina de estados emocional
│   ├── agents/        # (Fase 4) Agentes de automação
│   ├── tools/         # (Fase 4) Tool calling
│   └── vision/        # (Fase 3) Visão computacional
├── frontend/          # React + TypeScript + Vite
├── configs/
│   ├── config.yaml    # Configuração principal
│   └── personality.json  # Personalidade da Krirk
├── data/              # DB SQLite (não versionado)
├── logs/              # Logs (não versionados)
└── models/            # Modelos locais (não versionados)
```

## Rodando o projeto

### 1. Backend

```bash
# Instalar dependências (usar Python 3.11 recomendado)
pip install -r requirements.txt

# Copiar e editar .env
cp .env.example .env

# Garantir que o Ollama está rodando com o modelo correto
ollama pull qwen2.5:7b
ollama serve

# Iniciar backend
python main.py
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Acesse: http://localhost:5173

### 3. WebSocket direto (teste)

```
ws://localhost:8000/ws
```

Mensagens:
```json
// Enviar texto
{"type": "chat", "content": "Oi Krirk!"}

// Enviar áudio (base64 webm)
{"type": "audio", "data": "<base64>"}

// Checar status
{"type": "status"}
```

## Configuração do Ollama

Edite `configs/config.yaml` para mudar o modelo:

```yaml
ollama:
  model: "qwen2.5:7b"      # Recomendado
  # model: "llama3.2:3b"   # Mais leve
  # model: "mistral:7b"    # Alternativa
  # model: "deepseek-r1:7b" # Com reasoning
```

## Roadmap (do SDD)

- [x] **Fase 1** — MVP Conversacional (chat + TTS + memória + personalidade)
- [ ] **Fase 2** — Companion AI (avatar Live2D + expressões + overlay)
- [ ] **Fase 3** — Multimodalidade (visão + OCR + leitura de tela)
- [ ] **Fase 4** — Sistema Agente (controle do PC + automação + web)
- [ ] **Fase 5** — Memória Avançada (vetorial + semântica)
- [ ] **Fase 6** — Ecossistema (plugins + API pública)

## Notas importantes

- **Python 3.14**: faster-whisper pode não ter wheels. Use `stt.enabled: false` em config.yaml ou instale Python 3.11/3.12 em venv separado.
- **edge-tts**: requer conexão com internet para gerar áudio (TTS).
- **Ollama**: deve estar rodando em `http://localhost:11434` antes de iniciar o backend.
- **Dados do usuário**: `data/memory.db` não é versionado no git (dados pessoais).
- **Voz (STT)**: usa Web Speech API do browser — requer **Chrome ou Edge**. Brave, Firefox e outros não suportam. A API também precisa de internet (envia áudio para o Google/Microsoft).
