import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Camera, Copy, Check, Paperclip, Send } from 'lucide-react'
import { Message, EmotionType } from '../types'
import { VoiceButton } from './VoiceButton'
import { avatarChatSrc, EMOTION_COLOR } from '../utils/emotions'

// ─── Sugestões do empty state ─────────────────────────────────────────────────
const SUGGESTIONS = [
  'Que horas são?',
  'Abre o YouTube',
  'Me conta uma curiosidade',
  'O que você pode fazer?',
]

// ─── AvatarChatImg — avatar da Krirk com fallback em cadeia ──────────────────
function AvatarChatImg({ emotion, isProactive }: { emotion?: EmotionType; isProactive?: boolean }) {
  const emo = emotion ?? 'neutro'
  const borderColor = isProactive ? EMOTION_COLOR['tranquila'] : EMOTION_COLOR[emo as EmotionType] ?? '#7c3aed'

  const [src, setSrc] = useState(() => avatarChatSrc(emo as EmotionType))
  const fallbackStage = useRef(0)

  useEffect(() => {
    fallbackStage.current = 0
    setSrc(avatarChatSrc(emo as EmotionType))
  }, [emo])

  const handleError = () => {
    fallbackStage.current += 1
    if (fallbackStage.current === 1) {
      // Fallback dentro da pasta chat: tenta neutra
      setSrc('/avatar/chat/neutra.png')
    }
    // fallbackStage 2+ → deixa a img com o erro (sem loop infinito)
  }

  return (
    <img
      src={src}
      onError={handleError}
      alt={emo}
      title={isProactive ? 'Comentário espontâneo' : undefined}
      style={{
        width: 38, height: 38, borderRadius: '50%', flexShrink: 0,
        objectFit: 'cover',
        border: `2px solid ${isProactive ? borderColor : 'transparent'}`,
        boxShadow: isProactive ? `0 0 6px ${borderColor}66` : 'none',
      }}
    />
  )
}

// ─── UserAvatarImg — avatar do usuário com fallback SVG ──────────────────────
function UserAvatarImg() {
  const [showFallback, setShowFallback] = useState(false)

  if (showFallback) {
    return (
      <div style={{
        width: 38, height: 38, borderRadius: '50%', flexShrink: 0,
        background: 'rgba(124,58,237,0.2)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        border: '1px solid rgba(124,58,237,0.3)',
      }}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="rgba(168,85,247,0.8)" strokeWidth="2">
          <circle cx="12" cy="8" r="4"/>
          <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
        </svg>
      </div>
    )
  }

  return (
    <img
      src="/avatar/chat/user.png"
      onError={() => setShowFallback(true)}
      alt="Você"
      style={{
        width: 38, height: 38, borderRadius: '50%', flexShrink: 0,
        objectFit: 'cover',
        border: '1px solid rgba(124,58,237,0.3)',
      }}
    />
  )
}

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
          ) : <Check size={12} />}
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
        <AvatarChatImg emotion={msg.emotion} isProactive={msg.isProactive} />
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
              alt="imagem"
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
                padding: '0 2px', lineHeight: 1,
                color: copied ? '#34d399' : 'rgba(255,255,255,0.4)',
                opacity: hovered || copied ? 1 : 0,
                transition: 'opacity 0.15s, color 0.15s',
                display: 'flex', alignItems: 'center',
              }}
            >
              {copied ? <Check size={12} /> : <Copy size={12} />}
            </button>
          )}
        </div>
      </div>

      {isUser && <UserAvatarImg />}
    </div>
  )
}

// ─── Typing indicator ─────────────────────────────────────────────────────────
function TypingIndicator() {
  return (
    <div className="anim-fadein" style={{
      display: 'flex', gap: 8, marginBottom: 10, alignItems: 'flex-end',
    }}>
      <AvatarChatImg emotion="neutra" />
      <div style={{
        padding: '10px 14px', marginLeft: 2,
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
  sendImageMessage?: (b64: string) => void
  connected: boolean
  aiStateBusy: boolean
}

// ─── ChatMode ─────────────────────────────────────────────────────────────────
export function ChatMode({
  messages, addMsg, sendMessage, sendAudio, sendScreenshot, sendImageMessage, connected, aiStateBusy,
}: Props) {
  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const isThinking = aiStateBusy
    && !messages.some(m => m.isStreaming)
    && !messages.some(m => m.role === 'tool' && m.isRunning)

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
    addMsg({ id: `user-${Date.now()}`, role: 'user', content: 'Analisando minha tela...', timestamp: new Date() })
    sendScreenshot('Descreva o que você vê na minha tela. Seja específica e útil.')
  }, [connected, aiStateBusy, addMsg, sendScreenshot])

  const handleImageUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !connected || aiStateBusy) return
    const reader = new FileReader()
    reader.onload = () => {
      const b64 = (reader.result as string).split(',')[1]
      const thumbUrl = reader.result as string
      addMsg({
        id: `user-${Date.now()}`,
        role: 'user',
        content: '',
        thumbnail: thumbUrl,
        timestamp: new Date(),
      })
      sendImageMessage?.(b64)
    }
    reader.readAsDataURL(file)
    e.target.value = ''
  }, [connected, aiStateBusy, addMsg, sendImageMessage])

  const btnStyle = (enabled: boolean) => ({
    width: 34, height: 34, borderRadius: 8, border: 'none',
    background: 'var(--color-krirk-surface)',
    color: enabled ? 'var(--color-krirk-text)' : 'var(--color-krirk-muted)',
    cursor: enabled ? 'pointer' : 'not-allowed',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    flexShrink: 0, transition: 'background 0.15s',
  } as React.CSSProperties)

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

        {/* Screenshot */}
        <button
          onClick={handleScreenshot}
          disabled={!connected || aiStateBusy}
          title="Analisar tela"
          style={btnStyle(connected && !aiStateBusy)}
          onMouseEnter={e => { if (connected && !aiStateBusy) (e.currentTarget as HTMLButtonElement).style.background = 'rgba(124,58,237,0.2)' }}
          onMouseLeave={e => (e.currentTarget as HTMLButtonElement).style.background = 'var(--color-krirk-surface)'}
        >
          <Camera size={15} />
        </button>

        {/* Upload de imagem */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          hidden
          onChange={handleImageUpload}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={!connected || aiStateBusy || !sendImageMessage}
          title="Enviar imagem"
          style={btnStyle(connected && !aiStateBusy && !!sendImageMessage)}
          onMouseEnter={e => { if (connected && !aiStateBusy) (e.currentTarget as HTMLButtonElement).style.background = 'rgba(124,58,237,0.2)' }}
          onMouseLeave={e => (e.currentTarget as HTMLButtonElement).style.background = 'var(--color-krirk-surface)'}
        >
          <Paperclip size={15} />
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
          title="Enviar"
          style={{
            ...btnStyle(!!input.trim() && connected && !aiStateBusy),
            background: input.trim() && connected && !aiStateBusy
              ? 'var(--color-krirk-accent)' : 'var(--color-krirk-surface)',
          }}
        >
          <Send size={15} />
        </button>
      </div>
    </div>
  )
}
