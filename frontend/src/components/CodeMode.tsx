import { useState, useRef, useEffect, useCallback } from 'react'
import { Play, Copy, Check, Send } from 'lucide-react'
import { Message } from '../types'

// ── Paleta PowerShell ─────────────────────────────────────────────────────────
const PS = {
  bg:       '#012456',
  bgDeep:   '#0a1628',
  text:     '#cccccc',
  prompt:   '#ffff00',
  output:   '#ffffff',
  error:    '#ff6b6b',
  accent:   '#4ec9b0',
  muted:    'rgba(204,204,204,0.4)',
  border:   'rgba(78,201,176,0.2)',
  selection:'rgba(255,255,0,0.15)',
} as const

const PS_FONT = '"Consolas", "Cascadia Code", "Courier New", monospace'
const PS_PROMPT = 'PS C:\\KRIRK>'

// ─── Sugestões ────────────────────────────────────────────────────────────────
const CODE_SUGGESTIONS = [
  'Escreve um script Python para listar arquivos do Desktop',
  'Calcula o fatorial de 15',
  'Explica o que é recursão com exemplo',
  'O que você pode fazer em modo coder?',
]

// ─── Parser de blocos de código ───────────────────────────────────────────────
type Segment = { type: 'text'; content: string } | { type: 'code'; lang: string; content: string }

function parseContent(text: string): Segment[] {
  const segments: Segment[] = []
  const re = /```(\w*)\n?([\s\S]*?)```/g
  let last = 0
  let match: RegExpExecArray | null
  while ((match = re.exec(text)) !== null) {
    if (match.index > last) {
      const t = text.slice(last, match.index).trim()
      if (t) segments.push({ type: 'text', content: t })
    }
    segments.push({ type: 'code', lang: match[1] || 'text', content: match[2].trim() })
    last = match.index + match[0].length
  }
  const tail = text.slice(last).trim()
  if (tail) segments.push({ type: 'text', content: tail })
  return segments
}

// ─── Bloco de código estilo terminal ─────────────────────────────────────────
function CodeBlock({ lang, content, onExecute }: {
  lang: string; content: string; onExecute?: (code: string) => void
}) {
  const [copied, setCopied] = useState(false)
  const canRun = lang === 'python' || lang === 'py' || lang === ''

  const handleCopy = () => {
    navigator.clipboard.writeText(content).catch(() => {})
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const langColor: Record<string, string> = {
    python: '#4ec9b0',
    py:     '#4ec9b0',
    bash:   '#ce9178',
    js:     '#dcdcaa',
    ts:     '#569cd6',
    json:   '#9cdcfe',
    sql:    '#c586c0',
  }
  const borderColor = langColor[lang] ?? PS.accent

  return (
    <div style={{
      margin: '8px 0',
      border: `1px solid ${PS.border}`,
      borderLeft: `3px solid ${borderColor}`,
    }}>
      {/* Barra do bloco */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '3px 8px',
        background: 'rgba(0,0,0,0.3)',
        borderBottom: `1px solid ${PS.border}`,
      }}>
        <span style={{ fontSize: 10, color: borderColor, fontFamily: PS_FONT }}>{lang || 'code'}</span>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <button
            onClick={handleCopy}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: copied ? '#34d399' : PS.muted,
              display: 'flex', alignItems: 'center', gap: 3,
              fontSize: 10, padding: '1px 4px',
            }}
          >
            {copied ? <><Check size={10} /> copiado</> : <><Copy size={10} /> copiar</>}
          </button>
          {canRun && onExecute && (
            <button
              onClick={() => onExecute(content)}
              style={{
                background: 'rgba(78,201,176,0.15)',
                border: `1px solid ${PS.border}`,
                cursor: 'pointer',
                color: PS.accent,
                fontSize: 10, padding: '1px 8px',
                display: 'flex', alignItems: 'center', gap: 3,
                fontFamily: PS_FONT,
              }}
            >
              <Play size={9} /> Executar
            </button>
          )}
        </div>
      </div>

      {/* Código */}
      <pre style={{
        margin: 0, padding: '10px 14px',
        background: PS.bgDeep,
        color: '#e6edf3',
        fontSize: 12, lineHeight: 1.6,
        fontFamily: PS_FONT,
        overflowX: 'auto', whiteSpace: 'pre',
      }}>
        {content}
      </pre>
    </div>
  )
}

// ─── Linha de mensagem estilo terminal ───────────────────────────────────────
function TerminalLine({ msg, onExecute }: { msg: Message; onExecute?: (code: string) => void }) {
  const isUser = msg.role === 'user'

  if (msg.role === 'tool') {
    return (
      <div className="anim-fadein" style={{
        padding: '2px 0', fontSize: 12, fontFamily: PS_FONT,
        color: PS.accent, marginBottom: 2,
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        {msg.isRunning
          ? <><span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>⚙</span> Executando: {msg.toolName}...</>
          : <><Check size={11} /> {msg.toolName} {msg.toolResult ? `→ ${msg.toolResult.slice(0, 80)}` : ''}</>}
      </div>
    )
  }

  if (isUser) {
    return (
      <div className="anim-fadein" style={{
        padding: '3px 0', fontSize: 13, fontFamily: PS_FONT,
        marginBottom: 2, lineHeight: 1.5,
        whiteSpace: 'pre-wrap', wordBreak: 'break-word',
      }}>
        <span style={{ color: PS.prompt, userSelect: 'none' }}>{PS_PROMPT} </span>
        <span style={{ color: PS.output }}>{msg.content}</span>
      </div>
    )
  }

  // Mensagem da KRIRK — sem bolha, texto flat com blocos de código
  const segments = parseContent(msg.content)
  return (
    <div className="anim-fadein" style={{
      paddingLeft: 0, marginBottom: 8,
    }}>
      {segments.map((seg, i) =>
        seg.type === 'code' ? (
          <CodeBlock key={i} lang={seg.lang} content={seg.content} onExecute={onExecute} />
        ) : (
          <p key={i} style={{
            margin: '2px 0',
            fontSize: 13, lineHeight: 1.6,
            fontFamily: PS_FONT,
            color: PS.text,
            whiteSpace: 'pre-wrap', wordBreak: 'break-word',
          }}>
            {seg.content}
          </p>
        )
      )}
      {msg.isStreaming && (
        <span style={{
          display: 'inline-block', width: 7, height: 14,
          background: PS.accent, marginLeft: 2,
          verticalAlign: 'text-bottom',
          animation: 'blink 0.7s infinite',
        }} />
      )}
    </div>
  )
}

// ─── Typing indicator ─────────────────────────────────────────────────────────
function TypingIndicator() {
  return (
    <div className="anim-fadein" style={{
      padding: '3px 0', fontSize: 12, fontFamily: PS_FONT, color: PS.muted,
    }}>
      {PS_PROMPT} <span className="typing-dots" style={{ display: 'inline-flex', gap: 2 }}>
        <span style={{ background: PS.muted }} /><span style={{ background: PS.muted }} /><span style={{ background: PS.muted }} />
      </span>
    </div>
  )
}

// ─── Empty state ──────────────────────────────────────────────────────────────
function CodeEmptyState({ onSend }: { onSend: (text: string) => void }) {
  return (
    <div style={{ margin: 'auto', padding: '0 8px', fontFamily: PS_FONT }}>
      <div style={{ color: PS.accent, fontSize: 13, marginBottom: 4 }}>
        Windows PowerShell · KRIRK Coder
      </div>
      <div style={{ color: PS.muted, fontSize: 11, marginBottom: 16, lineHeight: 1.6 }}>
        Copyright (C) Microsoft Corporation. Todos os direitos reservados.<br />
        Modelo: qwen2.5-coder · execute_python habilitado<br />
        Digite uma pergunta ou comando abaixo.
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {CODE_SUGGESTIONS.map(s => (
          <button
            key={s}
            onClick={() => onSend(s)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              textAlign: 'left', padding: '2px 0',
              fontFamily: PS_FONT, fontSize: 12,
              color: PS.muted,
              transition: 'color 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.color = PS.accent}
            onMouseLeave={e => e.currentTarget.style.color = PS.muted}
          >
            <span style={{ color: PS.prompt }}>{PS_PROMPT} </span>
            {s}
          </button>
        ))}
      </div>
    </div>
  )
}

// ─── Props ────────────────────────────────────────────────────────────────────
interface Props {
  messages: Message[]
  addMsg: (msg: Message) => void
  sendCodeMessage: (content: string) => void
  connected: boolean
  aiStateBusy: boolean
}

// ─── CodeMode ─────────────────────────────────────────────────────────────────
export function CodeMode({ messages, addMsg, sendCodeMessage, connected, aiStateBusy }: Props) {
  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const isThinking = aiStateBusy
    && !messages.some(m => m.isStreaming)
    && !messages.some(m => m.role === 'tool' && m.isRunning)

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120
    if (nearBottom) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isThinking])

  const send = useCallback((text: string) => {
    if (!text.trim() || !connected || aiStateBusy) return
    addMsg({ id: `user-${Date.now()}`, role: 'user', content: text, timestamp: new Date() })
    sendCodeMessage(text)
    setInput('')
    inputRef.current?.focus()
  }, [connected, aiStateBusy, addMsg, sendCodeMessage])

  const handleExecute = useCallback((code: string) => {
    send(`Execute este código Python:\n\`\`\`python\n${code}\n\`\`\``)
  }, [send])

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden',
      background: PS.bg, color: PS.text, fontFamily: PS_FONT,
    }}>
      {/* Barra de título */}
      <div style={{
        padding: '6px 16px',
        background: 'rgba(0,0,0,0.4)',
        borderBottom: `1px solid ${PS.border}`,
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <span style={{ fontSize: 12, color: PS.accent, fontWeight: 600 }}>
          Windows PowerShell · KRIRK Coder
        </span>
        <span style={{ fontSize: 10, color: PS.muted }}>
          qwen2.5-coder · execute_python habilitado
        </span>
      </div>

      {/* Mensagens */}
      <div ref={scrollRef} style={{
        flex: 1, overflowY: 'auto', padding: '10px 16px',
        display: 'flex', flexDirection: 'column',
      }}>
        {messages.length === 0 && !isThinking ? (
          <CodeEmptyState onSend={send} />
        ) : (
          messages.map(m => <TerminalLine key={m.id} msg={m} onExecute={handleExecute} />)
        )}
        {isThinking && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* Input estilo prompt PS */}
      <div style={{
        padding: '10px 12px',
        borderTop: `1px solid ${PS.border}`,
        background: 'rgba(0,0,0,0.3)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 0 }}>
          <span style={{
            color: PS.prompt, fontSize: 13, fontFamily: PS_FONT,
            flexShrink: 0, paddingRight: 6, userSelect: 'none',
          }}>
            {PS_PROMPT}
          </span>
          <input
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), send(input))}
            placeholder={connected ? '' : 'Reconectando...'}
            disabled={!connected || aiStateBusy}
            style={{
              flex: 1, background: 'transparent', border: 'none', outline: 'none',
              color: PS.output, fontSize: 13, fontFamily: PS_FONT,
              caretColor: PS.prompt,
            }}
          />
          <button
            onClick={() => send(input)}
            disabled={!connected || aiStateBusy || !input.trim()}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: input.trim() && connected && !aiStateBusy ? PS.accent : PS.muted,
              display: 'flex', alignItems: 'center',
              padding: '4px 6px', transition: 'color 0.15s',
            }}
          >
            <Send size={14} />
          </button>
        </div>
        <div style={{
          marginTop: 4, fontSize: 10, color: PS.muted,
          paddingLeft: `${PS_PROMPT.length + 1}ch`,
        }}>
          Enter envia · blocos Python têm botão Executar
        </div>
      </div>
    </div>
  )
}
