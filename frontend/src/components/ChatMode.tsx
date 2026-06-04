import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Message } from '../types'
import { VoiceButton } from './VoiceButton'

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
  if (msg.role === 'tool') return <ToolChip msg={msg} />

  const isUser = msg.role === 'user'
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
          background: 'linear-gradient(135deg, #7c3aed, #a855f7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 12, fontWeight: 700, color: '#fff',
        }}>K</div>
      )}
      <div style={{
        maxWidth: '72%',
        padding: msg.thumbnail && !msg.content ? '6px' : '9px 13px',
        borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
        background: isUser ? 'var(--color-krirk-accent)' : 'rgba(255,255,255,0.06)',
        border: isUser ? 'none' : '1px solid var(--color-krirk-border)',
        color: 'var(--color-krirk-text)',
        fontSize: 13,
        lineHeight: 1.6,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
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
    </div>
  )
}

// ─── Props ────────────────────────────────────────────────────────────────────
interface Props {
  messages: Message[]
  addMsg: (msg: Message) => void
  sendMessage: (text: string) => void
  sendScreenshot: (prompt: string) => void
  connected: boolean
  aiStateBusy: boolean
}

// ─── ChatMode ─────────────────────────────────────────────────────────────────
export function ChatMode({ messages, addMsg, sendMessage, sendScreenshot, connected, aiStateBusy }: Props) {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Scroll para o fim a cada nova mensagem
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const submit = useCallback(() => {
    const text = input.trim()
    if (!text || !connected || aiStateBusy) return
    addMsg({ id: `user-${Date.now()}`, role: 'user', content: text, timestamp: new Date() })
    sendMessage(text)
    setInput('')
    inputRef.current?.focus()
  }, [input, connected, aiStateBusy, addMsg, sendMessage])

  const handleTranscript = useCallback((text: string) => {
    addMsg({ id: `user-${Date.now()}`, role: 'user', content: text, timestamp: new Date() })
    sendMessage(text)
  }, [addMsg, sendMessage])

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
      <div style={{
        flex: 1, overflowY: 'auto', padding: '14px 16px',
        display: 'flex', flexDirection: 'column',
      }}>
        {messages.length === 0 ? (
          <div style={{
            margin: 'auto', textAlign: 'center',
            color: 'var(--color-krirk-muted)', fontSize: 13,
          }}>
            Diz alguma coisa...
          </div>
        ) : (
          messages.map(m => <Bubble key={m.id} msg={m} />)
        )}
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
          onTranscript={handleTranscript}
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
