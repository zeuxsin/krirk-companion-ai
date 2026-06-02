import React, { useState, useEffect, useRef, useCallback } from 'react'
import { EmotionType, AIState, Message, WSEvent } from '../types'
import { VoiceButton } from './VoiceButton'

const EMOTION_TO_IMG: Record<EmotionType, string> = {
  neutral:    'neutro',
  happy:      'animada',
  excited:    'surpresa',
  thoughtful: 'pensando',
  curious:    'curiosa',
  concerned:  'cansada',
  playful:    'animada',
  angry:      'irritada',
  confused:   'confusa',
}

const ANIM_BY_STATE: Record<AIState, string> = {
  idle:      'anim-float',
  speaking:  'anim-float-fast',
  thinking:  'anim-sway',
  listening: 'anim-pulse',
  executing: '',
}

interface Props {
  emotion: EmotionType
  aiState: AIState
  connected: boolean
  aiStateBusy: boolean
  sendMessage: (text: string) => void
  onEvent: (handler: (e: WSEvent) => void) => () => void
}

export function HudMode({ emotion, aiState, connected, aiStateBusy, sendMessage, onEvent }: Props) {
  const [imgSrc, setImgSrc] = useState(`/avatar/${EMOTION_TO_IMG[emotion]}.png`)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const prevEmotion = useRef(emotion)
  const streamingIdRef = useRef<string | null>(null)

  // Fade na troca de emoção
  useEffect(() => {
    if (emotion === prevEmotion.current) return
    prevEmotion.current = emotion
    const t = setTimeout(() => setImgSrc(`/avatar/${EMOTION_TO_IMG[emotion]}.png`), 150)
    return () => clearTimeout(t)
  }, [emotion])

  const handleImgError = useCallback(() => {
    setImgSrc(src => src.endsWith('.png') ? `/avatar/${EMOTION_TO_IMG[emotion]}.svg` : src)
  }, [emotion])

  const addMsg = useCallback((msg: Message) => {
    setMessages(p => [...p.slice(-20), msg])
  }, [])

  useEffect(() => {
    const unsub = onEvent((ev: WSEvent) => {
      if (ev.type === 'connected' && ev.message) {
        addMsg({ id: `ai-${Date.now()}`, role: 'assistant', content: ev.message, timestamp: new Date() })
      }
      if (ev.type === 'token' && ev.content) {
        if (!streamingIdRef.current) {
          const id = `ai-${Date.now()}`
          streamingIdRef.current = id
          addMsg({ id, role: 'assistant', content: ev.content, timestamp: new Date(), isStreaming: true })
        } else {
          setMessages(p => p.map(m => m.id === streamingIdRef.current
            ? { ...m, content: m.content + ev.content } : m))
        }
      }
      if (ev.type === 'response_complete') {
        if (streamingIdRef.current) {
          setMessages(p => p.map(m => m.id === streamingIdRef.current
            ? { ...m, isStreaming: false } : m))
          streamingIdRef.current = null
        }
      }
      if (ev.type === 'error' && ev.message) {
        addMsg({ id: `err-${Date.now()}`, role: 'assistant', content: `⚠️ ${ev.message}`, timestamp: new Date() })
      }
    })
    return unsub
  }, [onEvent, addMsg])

  const submit = useCallback(() => {
    const text = input.trim()
    if (!text || !connected || aiStateBusy) return
    addMsg({ id: `user-${Date.now()}`, role: 'user', content: text, timestamp: new Date() })
    sendMessage(text)
    setInput('')
  }, [input, connected, aiStateBusy, addMsg, sendMessage])

  const handleTranscript = useCallback((text: string) => {
    addMsg({ id: `user-${Date.now()}`, role: 'user', content: text, timestamp: new Date() })
    sendMessage(text)
  }, [addMsg, sendMessage])

  const lastMsgs = messages.slice(-4)

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Avatar compacto + status */}
      <div style={{
        padding: '10px 12px',
        display: 'flex', alignItems: 'center', gap: 12,
        borderBottom: '1px solid var(--color-krirk-border)',
        background: 'var(--color-krirk-sidebar)',
      }}>
        <img
          src={imgSrc}
          onError={handleImgError}
          className={ANIM_BY_STATE[aiState]}
          alt={emotion}
          style={{ width: 56, pointerEvents: 'none' }}
        />
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-krirk-text)' }}>
            Krirk
          </div>
          <div style={{
            fontSize: 10, textTransform: 'uppercase',
            letterSpacing: '0.1em', color: 'var(--color-krirk-muted)',
          }}>
            {emotion}
          </div>
        </div>
      </div>

      {/* Mensagens compactas */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '10px 12px',
        display: 'flex', flexDirection: 'column', gap: 8,
      }}>
        {lastMsgs.length === 0 ? (
          <div style={{ color: 'var(--color-krirk-muted)', fontSize: 12, textAlign: 'center', margin: 'auto' }}>
            Diz alguma coisa...
          </div>
        ) : lastMsgs.map(m => (
          <div key={m.id} style={{
            display: 'flex',
            justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start',
          }}>
            <div style={{
              maxWidth: '80%', padding: '6px 10px', fontSize: 12,
              borderRadius: m.role === 'user' ? '12px 12px 4px 12px' : '12px 12px 12px 4px',
              background: m.role === 'user' ? 'var(--color-krirk-accent)' : 'rgba(255,255,255,0.06)',
              border: m.role !== 'user' ? '1px solid var(--color-krirk-border)' : 'none',
              color: 'var(--color-krirk-text)',
              lineHeight: 1.5,
            }}>
              {m.content}
              {m.isStreaming && <span style={{ display: 'inline-block', width: 6, height: 11, background: '#a78bfa', marginLeft: 2, borderRadius: 2, animation: 'blink 0.7s infinite', verticalAlign: 'text-bottom' }} />}
            </div>
          </div>
        ))}
      </div>

      {/* Input compacto */}
      <div style={{
        padding: '8px 10px',
        borderTop: '1px solid var(--color-krirk-border)',
        display: 'flex', gap: 6, alignItems: 'center',
        background: 'var(--color-krirk-sidebar)',
      }}>
        <VoiceButton onTranscript={handleTranscript} disabled={!connected || aiStateBusy} />
        <input
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), submit())}
          placeholder="Digite uma mensagem..."
          disabled={!connected || aiStateBusy}
          style={{
            flex: 1, padding: '7px 10px', borderRadius: 8,
            border: '1px solid var(--color-krirk-border)',
            background: 'var(--color-krirk-surface)',
            color: 'var(--color-krirk-text)',
            fontSize: 12, outline: 'none',
          }}
        />
        <button
          onClick={submit}
          disabled={!connected || aiStateBusy || !input.trim()}
          style={{
            width: 30, height: 30, borderRadius: 8, border: 'none',
            background: input.trim() && connected && !aiStateBusy
              ? 'var(--color-krirk-accent)' : 'var(--color-krirk-surface)',
            color: '#fff', cursor: 'pointer', fontSize: 12,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'background 0.15s', flexShrink: 0,
          }}
        >▶</button>
      </div>
    </div>
  )
}
