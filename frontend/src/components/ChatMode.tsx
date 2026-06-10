import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Message } from '../types'
import { VoiceButton } from './VoiceButton'

// ─── Sugestões do empty state ─────────────────────────────────────────────────
const SUGGESTIONS = [
  'Que horas são?',
  'Abre o YouTube',
  'Me conta uma curiosidade',
  'O que você pode fazer?',
]

// ─── ToolChip ─────────────────────────────────────────────────────────────────
function ToolChip({ msg }: { msg: Message }) {
  const [expanded, setExpanded] = React.useState(false)
  return (
    <div className="anim-fadein" style={{
      display: 'flex', justifyContent: 'center', marginBottom: 8,
    }}>
      <div style={{
        background: 'rgba(124,58,237,0.12)',
        border: '1px solid rgba(124,58,237,0.3)',
        borderRadius: 20,
        padding: '4px 12px',
        fontSize: 12,
        color: 'var(--color-krirk-muted)',
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
        maxWidth: '80%',
      }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {msg.isRunning ? (
            <span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>⚙</span>
          ) : '✓'}
          {msg.isRunning
            ? `Executando: ${msg.toolName}...`
            : msg.toolName}
          {!msg.isRunning && msg.toolResult && (
            <button
              onClick={() => setExpanded(e => !e)}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: 'var(--color-krirk-muted)', fontSize: 11, padding: '0 4px',
              }}
            >
              {expanded ? '▲ fechar' : '▼ ver resultado'}
            </button>
          )}
        </span>
        {expanded && msg.toolResult && (
          <pre style={{
            margin: 0, padding: '6px 10px',
            background: 'rgba(0,0,0,0.3)', borderRadius: 6,
            fontSize: 11, color: 'var(--color-krirk-text)',
            whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            maxHeight: 200, overflowY: 'auto',
            width: '100%',
          }}>
            {msg.toolResult}
          </pre>
        )}
      </div>
    </div>
  )
}

// ─── MessageBubble ────────────────────────────────────────────────────────────
function Bubble({ msg }: { msg: Message }) {
  const [hovered, setHovered] = useState(false)
  const [copied, setCopied] = useState(false)

  if (msg.role === 'tool') return <ToolChip msg={msg} />

  const isUser = msg.role === 'user'

  const handleCopy = () => {
    navigator.clipboard.writeText(msg.content).catch(() => {})
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const timeStr = msg.timestamp instanceof Date
    ? msg.timestamp.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
    : new Date(msg.timestamp).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })

  return (
    <div
      className="anim-fadein"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        marginBottom: 10,
        gap: 8,
        alignItems: 'flex-end',
        position: 'relative',
      }}
    >
      {!isUser && (
        <div title={msg.isProactive ? 'Comentário espontâneo' : undefined} style={{
          width: 26, height: 26, borderRadius: '50%', flexShrink: 0,
          background: msg.isProactive
            ? 'linear-gradient(135deg, #4f46e5, #7c3aed)'
            : 'linear-gradient(135deg, #7c3aed, #a855f7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: msg.isProactive ? 13 : 12, fontWeight: 700, color: '#fff',
          opacity: msg.isProactive ? 0.85 : 1,
        }}>{msg.isProactive ? '💭' : 'K'}</div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', alignItems: isUser ? 'flex-end' : 'flex-start', maxWidth: '72%' }}>
        <div style={{
          padding: msg.thumbnail && !msg.content ? '6px' : '9px 13px',
          borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
          background: isUser ? 'var(--color-krirk-accent)' : 'rgba(255,255,255,0.06)',
          border: isUser ? 'none' : '1px solid var(--color-krirk-border)',
          color: 'var(--color-krirk-text)',
          fontSize: 13,
          lineHeight: 1.6,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          position: 'relative',
        }}>
          {msg.thumbnail && (
            <img
              src={msg.thumbnail}
              alt="screenshot"
              style={{
                maxWidth: '100%', borderRadius: 6,
                display: 'block',
                marginBottom: msg.content ? 6 : 0,
                opacity: 0.9,
              }}
            />
          )}
          {msg.content}
          {msg.isStreaming && (
            <span style={{
              display: 'inline-block', width: 7, height: 13,
              background: '#a78bfa', marginLeft: 3, borderRadius: 2,
              verticalAlign: 'text-bottom',
              animation: 'blink 0.7s infinite',
            }} />
          )}
        </div>

        {/* Timestamp + copy button */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6, marginTop: 3,
          flexDirection: isUser ? 'row-reverse' : 'row',
        }}>
          <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.25)' }}>
            {timeStr}
          </span>
          {!isUser && (
            <button
              onClick={handleCopy}
              title="Copiar resposta"
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                fontSize: 11, padding: '0 2px', lineHeight: 1,
                color: copied ? '#34d399' : 'rgba(255,255,255,0.3)',
                opacity: hovered || copied ? 1 : 0,
                transition: 'opacity 0.15s, color 0.15s',
              }}
            >
              {copied ? '✓' : '📋'}
            </button>
          )}
        </div>
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
        background: 'linear-gradient(135deg, #7c3aed, #a855f7)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 12, fontWeight: 700, color: '#fff',
      }}>K</div>
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
function EmptyState({ onSend }: { onSend: (text: string) => void }) {
  return (
    <div style={{ margin: 'auto', textAlign: 'center', padding: '0 16px' }}>
      <div style={{ fontSize: 36, marginBottom: 8 }}>✨</div>
      <p style={{
        color: 'var(--color-krirk-muted)', fontSize: 13,
        marginBottom: 16, lineHeight: 1.5,
      }}>
        Olá! Como posso ajudar?
      </p>
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'center',
      }}>
        {SUGGESTIONS.map(s => (
          <button
            key={s}
            onClick={() => onSend(s)}
            style={{
              padding: '6px 12px', borderRadius: 20,
              border: '1px solid var(--color-krirk-border)',
              background: 'var(--color-krirk-surface)',
              color: 'var(--color-krirk-muted)',
              fontSize: 11, cursor: 'pointer',
              transition: 'border-color 0.15s, color 0.15s',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = 'rgba(124,58,237,0.5)'
              e.currentTarget.style.color = 'var(--color-krirk-text)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = 'var(--color-krirk-border)'
              e.currentTarget.style.color = 'var(--color-krirk-muted)'
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
  sendMessage: (text: string) => void
  sendAudio: (b64Wav: string) => void
  sendScreenshot: (prompt: string) => void
  connected: boolean
  aiStateBusy: boolean
}

// ─── ChatMode ─────────────────────────────────────────────────────────────────
export function ChatMode({
  messages, addMsg, sendMessage, sendAudio, sendScreenshot, connected, aiStateBusy,
}: Props) {
  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // "Thinking" = ocupado mas sem nenhuma mensagem em streaming nem tool rodando
  const isThinking = aiStateBusy
    && !messages.some(m => m.isStreaming)
    && !messages.some(m => m.role === 'tool' && m.isRunning)

  // Smart scroll: só rola para o fim se o usuário já está perto do fundo
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120
    if (nearBottom) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, isThinking])

  const sendSuggestion = useCallback((text: string) => {
    if (!connected || aiStateBusy) return
    addMsg({ id: `user-${Date.now()}`, role: 'user', content: text, timestamp: new Date() })
    sendMessage(text)
    inputRef.current?.focus()
  }, [connected, aiStateBusy, addMsg, sendMessage])

  const submit = useCallback(() => {
    const text = input.trim()
    if (!text || !connected || aiStateBusy) return
    addMsg({ id: `user-${Date.now()}`, role: 'user', content: text, timestamp: new Date() })
    sendMessage(text)
    setInput('')
    inputRef.current?.focus()
  }, [input, connected, aiStateBusy, addMsg, sendMessage])

  const handleVoiceError = useCallback((msg: string) => {
    addMsg({ id: `err-${Date.now()}`, role: 'assistant', content: msg, timestamp: new Date() })
  }, [addMsg])

  const handleScreenshot = useCallback(() => {
    if (!connected || aiStateBusy) return
    addMsg({ id: `user-${Date.now()}`, role: 'user', content: '📷 Analisando minha tela...', timestamp: new Date() })
    sendScreenshot('Descreva o que você vê na minha tela. Seja específica e útil.')
  }, [connected, aiStateBusy, addMsg, sendScreenshot])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
      {/* Header */}
      <div style={{
        padding: '10px 16px',
        borderBottom: '1px solid var(--color-krirk-border)',
        fontSize: 13,
        fontWeight: 600,
        color: 'var(--color-krirk-text)',
        background: 'var(--color-krirk-bg)',
      }}>
        Krirk
      </div>

      {/* Messages */}
      <div
        ref={scrollRef}
        style={{
          flex: 1, overflowY: 'auto', padding: '14px 16px',
          display: 'flex', flexDirection: 'column',
        }}
      >
        {messages.length === 0 && !isThinking ? (
          <EmptyState onSend={sendSuggestion} />
        ) : (
          messages.map(m => <Bubble key={m.id} msg={m} />)
        )}

        {/* Typing indicator — aparece enquanto AI está "pensando" */}
        {isThinking && <TypingIndicator />}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{
        padding: '10px 12px',
        borderTop: '1px solid var(--color-krirk-border)',
        display: 'flex', gap: 8, alignItems: 'center',
        background: 'var(--color-krirk-sidebar)',
      }}>
        <VoiceButton
          sendAudio={sendAudio}
          onError={handleVoiceError}
          disabled={!connected || aiStateBusy}
        />
        <button
          onClick={handleScreenshot}
          disabled={!connected || aiStateBusy}
          title="Analisar tela"
          style={{
            width: 34, height: 34, borderRadius: 8, border: 'none',
            background: 'var(--color-krirk-surface)',
            color: connected && !aiStateBusy ? 'var(--color-krirk-text)' : 'var(--color-krirk-muted)',
            cursor: connected && !aiStateBusy ? 'pointer' : 'not-allowed',
            fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0, transition: 'background 0.15s',
          }}
          onMouseEnter={e => { if (connected && !aiStateBusy) (e.currentTarget as HTMLButtonElement).style.background = 'rgba(124,58,237,0.2)' }}
          onMouseLeave={e => (e.currentTarget as HTMLButtonElement).style.background = 'var(--color-krirk-surface)'}
        >
          📷
        </button>
        <input
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), submit())}
          placeholder={connected ? 'Fala com a Krirk... (Enter para enviar)' : 'Reconectando...'}
          disabled={!connected || aiStateBusy}
          style={{
            flex: 1, padding: '8px 12px',
            borderRadius: 8,
            border: '1px solid var(--color-krirk-border)',
            background: 'var(--color-krirk-surface)',
            color: 'var(--color-krirk-text)',
            fontSize: 13, outline: 'none',
          }}
        />
        <button
          onClick={submit}
          disabled={!connected || aiStateBusy || !input.trim()}
          style={{
            width: 34, height: 34, borderRadius: 8, border: 'none',
            background: input.trim() && connected && !aiStateBusy
              ? 'var(--color-krirk-accent)' : 'var(--color-krirk-surface)',
            color: '#fff', cursor: 'pointer', fontSize: 14,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'background 0.15s', flexShrink: 0,
          }}
        >▶</button>
      </div>
    </div>
  )
}
