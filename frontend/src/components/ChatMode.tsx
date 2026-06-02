import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Message, WSEvent } from '../types'
import { VoiceButton } from './VoiceButton'

// ─── Audio ───────────────────────────────────────────────────────────────────
async function playAudioBase64(b64: string) {
  try {
    const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0))
    const ctx = new AudioContext()
    if (ctx.state === 'suspended') await ctx.resume()
    const buffer = await ctx.decodeAudioData(bytes.buffer)
    const src = ctx.createBufferSource()
    src.buffer = buffer
    src.connect(ctx.destination)
    src.start(0)
    src.onended = () => ctx.close()
  } catch (e) { console.warn('[TTS]', e) }
}

// ─── MessageBubble ────────────────────────────────────────────────────────────
function Bubble({ msg }: { msg: Message }) {
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
        padding: '9px 13px',
        borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
        background: isUser ? 'var(--color-krirk-accent)' : 'rgba(255,255,255,0.06)',
        border: isUser ? 'none' : '1px solid var(--color-krirk-border)',
        color: 'var(--color-krirk-text)',
        fontSize: 13,
        lineHeight: 1.6,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      }}>
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
  sendMessage: (text: string) => void
  onEvent: (handler: (e: WSEvent) => void) => () => void
  connected: boolean
  aiStateBusy: boolean
  onMessageCountChange?: (n: number) => void
}

// ─── ChatMode ─────────────────────────────────────────────────────────────────
export function ChatMode({ sendMessage, onEvent, connected, aiStateBusy, onMessageCountChange }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const streamingIdRef = useRef<string | null>(null)

  const addMsg = useCallback((msg: Message) => {
    setMessages(p => {
      const next = [...p, msg]
      onMessageCountChange?.(next.length)
      return next
    })
  }, [onMessageCountChange])

  const appendToken = useCallback((id: string, token: string) => {
    setMessages(p => p.map(m => m.id === id ? { ...m, content: m.content + token } : m))
  }, [])

  const finalizeMsg = useCallback((id: string, emotion?: string) => {
    setMessages(p => p.map(m => m.id === id ? { ...m, isStreaming: false, emotion: emotion as never } : m))
  }, [])

  useEffect(() => {
    const unsub = onEvent((ev: WSEvent) => {
      if (ev.type === 'connected' && ev.message) {
        addMsg({ id: `ai-${Date.now()}`, role: 'assistant', content: ev.message, timestamp: new Date() })
        return
      }
      if (ev.type === 'transcription' && ev.content) {
        addMsg({ id: `user-${Date.now()}`, role: 'user', content: ev.content, timestamp: new Date() })
        return
      }
      if (ev.type === 'token' && ev.content) {
        if (!streamingIdRef.current) {
          const id = `ai-${Date.now()}`
          streamingIdRef.current = id
          addMsg({ id, role: 'assistant', content: ev.content, timestamp: new Date(), isStreaming: true })
        } else {
          appendToken(streamingIdRef.current, ev.content)
        }
        return
      }
      if (ev.type === 'response_complete') {
        if (streamingIdRef.current) { finalizeMsg(streamingIdRef.current, ev.emotion); streamingIdRef.current = null }
        if (ev.audio) playAudioBase64(ev.audio)
        return
      }
      if (ev.type === 'error' && ev.message) {
        if (streamingIdRef.current) { finalizeMsg(streamingIdRef.current); streamingIdRef.current = null }
        addMsg({ id: `err-${Date.now()}`, role: 'assistant', content: `⚠️ ${ev.message}`, timestamp: new Date() })
      }
    })
    return unsub
  }, [onEvent, addMsg, appendToken, finalizeMsg])

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
