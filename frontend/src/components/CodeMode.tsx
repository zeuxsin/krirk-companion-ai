import React, { useState, useRef, useEffect, useCallback } from 'react'
import { Message } from '../types'

// ─── Sugestões do empty state ─────────────────────────────────────────────────
const CODE_SUGGESTIONS = [
  'Escreve um script Python para listar arquivos do Desktop',
  'Calcula o fatorial de 15',
  'Explica o que é recursão com exemplo',
  'O que você pode fazer em modo coder?',
]

// ─── Parseia texto em segmentos: texto puro vs blocos de código ───────────────
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

// ─── Bloco de código com botão Executar ──────────────────────────────────────
function CodeBlock({
  lang, content, onExecute,
}: { lang: string; content: string; onExecute?: (code: string) => void }) {
  const [copied, setCopied] = useState(false)
  const canRun = lang === 'python' || lang === 'py' || lang === ''

  const handleCopy = () => {
    navigator.clipboard.writeText(content).catch(() => {})
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div style={{
      borderRadius: 8, overflow: 'hidden',
      border: '1px solid rgba(124,58,237,0.25)',
      marginTop: 6, marginBottom: 6,
    }}>
      {/* Header do bloco */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '4px 10px',
        background: 'rgba(124,58,237,0.12)',
        fontSize: 11,
        color: 'rgba(167,139,250,0.8)',
      }}>
        <span>{lang || 'code'}</span>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            onClick={handleCopy}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: copied ? '#34d399' : 'rgba(255,255,255,0.4)',
              fontSize: 11, padding: '1px 4px',
            }}
          >
            {copied ? '✓ copiado' : '📋 copiar'}
          </button>
          {canRun && onExecute && (
            <button
              onClick={() => onExecute(content)}
              style={{
                background: 'rgba(124,58,237,0.3)',
                border: '1px solid rgba(124,58,237,0.4)',
                borderRadius: 4,
                cursor: 'pointer',
                color: '#e4e4e7',
                fontSize: 11, padding: '1px 8px',
                fontWeight: 600,
              }}
            >
              ▶ Executar
            </button>
          )}
        </div>
      </div>

      {/* Código */}
      <pre style={{
        margin: 0,
        padding: '10px 14px',
        background: '#0d1117',
        color: '#e6edf3',
        fontSize: 12,
        lineHeight: 1.6,
        fontFamily: '"Cascadia Code", "Fira Code", "Consolas", monospace',
        overflowX: 'auto',
        whiteSpace: 'pre',
      }}>
        {content}
      </pre>
    </div>
  )
}

// ─── Bolha de mensagem para o CodeMode ───────────────────────────────────────
function CodeBubble({ msg, onExecute }: {
  msg: Message
  onExecute?: (code: string) => void
}) {
  if (msg.role === 'tool') {
    return (
      <div className="anim-fadein" style={{
        display: 'flex', justifyContent: 'center', marginBottom: 8,
      }}>
        <div style={{
          background: 'rgba(124,58,237,0.12)',
          border: '1px solid rgba(124,58,237,0.3)',
          borderRadius: 20, padding: '4px 14px',
          fontSize: 12, color: 'rgba(167,139,250,0.8)',
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          {msg.isRunning
            ? <><span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>⚙</span> Executando {msg.toolName}...</>
            : <>✓ {msg.toolName}</>}
        </div>
      </div>
    )
  }

  const isUser = msg.role === 'user'
  const timeStr = new Date(msg.timestamp).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
  const segments = isUser ? null : parseContent(msg.content)

  return (
    <div className="anim-fadein" style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
      marginBottom: 10,
      gap: 8,
      alignItems: 'flex-end',
    }}>
      {!isUser && (
        <div style={{
          width: 26, height: 26, borderRadius: '50%', flexShrink: 0,
          background: 'linear-gradient(135deg, #0ea5e9, #6d28d9)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 12, fontWeight: 700, color: '#fff',
        }}>Q</div>
      )}

      <div style={{
        maxWidth: '80%', display: 'flex', flexDirection: 'column',
        alignItems: isUser ? 'flex-end' : 'flex-start',
      }}>
        {isUser ? (
          <div style={{
            padding: '8px 12px',
            borderRadius: '14px 14px 4px 14px',
            background: 'var(--color-krirk-accent)',
            color: '#fff', fontSize: 13, lineHeight: 1.6,
            whiteSpace: 'pre-wrap', wordBreak: 'break-word',
          }}>
            {msg.content}
            {msg.isStreaming && (
              <span style={{
                display: 'inline-block', width: 7, height: 13,
                background: '#a78bfa', marginLeft: 3, borderRadius: 2,
                verticalAlign: 'text-bottom', animation: 'blink 0.7s infinite',
              }} />
            )}
          </div>
        ) : (
          <div style={{
            padding: segments?.length === 0 ? 0 : '2px 0',
            color: 'var(--color-krirk-text)',
            fontSize: 13, lineHeight: 1.7,
            maxWidth: '100%',
          }}>
            {segments?.map((seg, i) =>
              seg.type === 'code' ? (
                <CodeBlock key={i} lang={seg.lang} content={seg.content} onExecute={onExecute} />
              ) : (
                <p key={i} style={{ margin: '4px 0', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                  {seg.content}
                </p>
              )
            )}
            {msg.isStreaming && (
              <span style={{
                display: 'inline-block', width: 7, height: 13,
                background: '#a78bfa', marginLeft: 3, borderRadius: 2,
                verticalAlign: 'text-bottom', animation: 'blink 0.7s infinite',
              }} />
            )}
          </div>
        )}

        <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.2)', marginTop: 3 }}>
          {timeStr}
        </span>
      </div>
    </div>
  )
}

// ─── Typing indicator ─────────────────────────────────────────────────────────
function TypingIndicator() {
  return (
    <div className="anim-fadein" style={{
      display: 'flex', gap: 8, marginBottom: 10, alignItems: 'flex-end',
    }}>
      <div style={{
        width: 26, height: 26, borderRadius: '50%', flexShrink: 0,
        background: 'linear-gradient(135deg, #0ea5e9, #6d28d9)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 12, fontWeight: 700, color: '#fff',
      }}>Q</div>
      <div style={{
        padding: '10px 14px',
        borderRadius: '16px 16px 16px 4px',
        background: 'rgba(255,255,255,0.06)',
        border: '1px solid var(--color-krirk-border)',
        display: 'flex', alignItems: 'center',
      }}>
        <span className="typing-dots">
          <span /><span /><span />
        </span>
      </div>
    </div>
  )
}

// ─── Empty state ──────────────────────────────────────────────────────────────
function CodeEmptyState({ onSend }: { onSend: (text: string) => void }) {
  return (
    <div style={{ margin: 'auto', textAlign: 'center', padding: '0 16px' }}>
      <div style={{ fontSize: 36, marginBottom: 8 }}>💻</div>
      <p style={{
        color: 'rgba(14,165,233,0.9)', fontSize: 14, fontWeight: 600,
        marginBottom: 4,
      }}>
        Modo Coder
      </p>
      <p style={{
        color: 'var(--color-krirk-muted)', fontSize: 12,
        marginBottom: 20, lineHeight: 1.5,
      }}>
        qwen2.5-coder · Python execution habilitado
      </p>
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'center',
      }}>
        {CODE_SUGGESTIONS.map(s => (
          <button
            key={s}
            onClick={() => onSend(s)}
            style={{
              padding: '7px 12px', borderRadius: 20,
              border: '1px solid rgba(14,165,233,0.25)',
              background: 'rgba(14,165,233,0.06)',
              color: 'var(--color-krirk-muted)',
              fontSize: 11, cursor: 'pointer',
              transition: 'border-color 0.15s, color 0.15s, background 0.15s',
              textAlign: 'left',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = 'rgba(14,165,233,0.5)'
              e.currentTarget.style.color = 'var(--color-krirk-text)'
              e.currentTarget.style.background = 'rgba(14,165,233,0.1)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = 'rgba(14,165,233,0.25)'
              e.currentTarget.style.color = 'var(--color-krirk-muted)'
              e.currentTarget.style.background = 'rgba(14,165,233,0.06)'
            }}
          >
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
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const isThinking = aiStateBusy
    && !messages.some(m => m.isStreaming)
    && !messages.some(m => m.role === 'tool' && m.isRunning)

  // Smart scroll
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
    const prompt = `Execute este código Python:\n\`\`\`python\n${code}\n\`\`\``
    send(prompt)
  }, [send])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
      {/* Header */}
      <div style={{
        padding: '10px 16px',
        borderBottom: '1px solid var(--color-krirk-border)',
        background: 'var(--color-krirk-bg)',
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <span style={{ fontSize: 15 }}>💻</span>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-krirk-text)' }}>
            Modo Coder
          </div>
          <div style={{ fontSize: 10, color: 'rgba(14,165,233,0.7)' }}>
            qwen2.5-coder · execute_python habilitado
          </div>
        </div>
      </div>

      {/* Mensagens */}
      <div ref={scrollRef} style={{
        flex: 1, overflowY: 'auto', padding: '14px 16px',
        display: 'flex', flexDirection: 'column',
      }}>
        {messages.length === 0 && !isThinking ? (
          <CodeEmptyState onSend={(text) => send(text)} />
        ) : (
          messages.map(m => (
            <CodeBubble key={m.id} msg={m} onExecute={handleExecute} />
          ))
        )}

        {isThinking && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{
        padding: '10px 12px',
        borderTop: '1px solid var(--color-krirk-border)',
        background: 'var(--color-krirk-sidebar)',
      }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={connected ? 'Pergunte sobre código ou peça para executar algo... (Shift+Enter = nova linha)' : 'Reconectando...'}
            disabled={!connected || aiStateBusy}
            rows={1}
            style={{
              flex: 1, padding: '8px 12px',
              borderRadius: 8,
              border: '1px solid rgba(14,165,233,0.2)',
              background: 'var(--color-krirk-surface)',
              color: 'var(--color-krirk-text)',
              fontSize: 13, outline: 'none',
              resize: 'none', lineHeight: 1.5,
              minHeight: 36, maxHeight: 120,
              overflowY: 'auto',
              fontFamily: 'inherit',
            }}
            onInput={e => {
              const el = e.currentTarget
              el.style.height = 'auto'
              el.style.height = `${Math.min(el.scrollHeight, 120)}px`
            }}
          />
          <button
            onClick={() => send(input)}
            disabled={!connected || aiStateBusy || !input.trim()}
            style={{
              width: 34, height: 34, borderRadius: 8, border: 'none', flexShrink: 0,
              background: input.trim() && connected && !aiStateBusy
                ? 'linear-gradient(135deg, #0ea5e9, #6d28d9)'
                : 'var(--color-krirk-surface)',
              color: '#fff', cursor: 'pointer', fontSize: 14,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'background 0.15s',
            }}
          >▶</button>
        </div>
        <div style={{
          marginTop: 5, fontSize: 10, color: 'rgba(255,255,255,0.2)',
          paddingLeft: 2,
        }}>
          Enter envia · Shift+Enter nova linha · blocos Python têm botão ▶ Executar
        </div>
      </div>
    </div>
  )
}
