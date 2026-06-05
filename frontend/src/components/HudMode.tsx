import React, { useState, useEffect, useRef, useCallback } from 'react'
import { EmotionType, AIState, Message } from '../types'
import { VoiceButton } from './VoiceButton'
import { EMOTION_COLOR, avatarAnimClass, avatarSrc, avatarFallback } from '../utils/emotions'

interface Props {
  messages: Message[]
  addMsg: (msg: Message) => void
  emotion: EmotionType
  aiState: AIState
  connected: boolean
  aiStateBusy: boolean
  sendMessage: (text: string) => void
}

export function HudMode({ messages, addMsg, emotion, aiState, connected, aiStateBusy, sendMessage }: Props) {
  const [imgSrc, setImgSrc] = useState(avatarSrc(emotion))
  const [imgOpacity, setImgOpacity] = useState(1)
  const [input, setInput] = useState('')
  const prevEmotion = useRef(emotion)

  // Fade na troca de emoção
  useEffect(() => {
    if (emotion === prevEmotion.current) return
    prevEmotion.current = emotion
    setImgOpacity(0)
    const t = setTimeout(() => {
      setImgSrc(avatarSrc(emotion))
      setImgOpacity(1)
    }, 150)
    return () => clearTimeout(t)
  }, [emotion])

  const handleImgError = useCallback(() => {
    setImgSrc(src => src.endsWith('.png') ? avatarFallback(emotion) : src)
  }, [emotion])

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

  // Mostra só as últimas 4 mensagens no modo compacto
  const lastMsgs = messages.slice(-4)

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

      {/* Avatar centralizado + emoção */}
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        padding: '12px 8px 8px',
        background: 'var(--color-krirk-bg)',
        borderBottom: '1px solid var(--color-krirk-border)',
      }}>
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {/* Anel de brilho */}
          <div style={{
            position: 'absolute',
            width: 130, height: 130,
            borderRadius: '50%',
            background: `radial-gradient(circle, ${EMOTION_COLOR[emotion]}18 0%, transparent 65%)`,
            boxShadow: `0 0 30px 6px ${EMOTION_COLOR[emotion]}28`,
            transition: 'background 0.6s ease, box-shadow 0.6s ease',
            pointerEvents: 'none',
          }} />
          <img
            src={imgSrc}
            onError={handleImgError}
            className={avatarAnimClass(aiState, emotion)}
            alt={emotion}
            style={{
              width: 120,
              position: 'relative', zIndex: 1,
              opacity: imgOpacity,
              transition: 'opacity 0.15s',
              pointerEvents: 'none',
              filter: aiState === 'speaking'
                ? `drop-shadow(0 0 10px ${EMOTION_COLOR[emotion]}88)` : 'none',
            }}
          />
        </div>
        <div style={{
          marginTop: 4, fontSize: 9, fontWeight: 700,
          letterSpacing: '0.14em', textTransform: 'uppercase',
          color: EMOTION_COLOR[emotion],
          transition: 'color 0.4s ease',
        }}>
          {emotion}
        </div>
      </div>

      {/* Últimas 4 mensagens */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '8px 10px',
        display: 'flex', flexDirection: 'column', gap: 6,
      }}>
        {lastMsgs.length === 0 ? (
          <div style={{
            color: 'var(--color-krirk-muted)', fontSize: 11,
            textAlign: 'center', margin: 'auto',
          }}>
            Diz alguma coisa...
          </div>
        ) : lastMsgs.map(m => (
          <div key={m.id} style={{
            display: 'flex',
            justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start',
          }}>
            <div style={{
              maxWidth: '85%', padding: '5px 9px', fontSize: 11,
              borderRadius: m.role === 'user' ? '11px 11px 3px 11px' : '11px 11px 11px 3px',
              background: m.role === 'user'
                ? 'var(--color-krirk-accent)'
                : 'rgba(255,255,255,0.06)',
              border: m.role !== 'user' ? '1px solid var(--color-krirk-border)' : 'none',
              color: 'var(--color-krirk-text)',
              lineHeight: 1.5,
            }}>
              {m.content || (m.thumbnail ? '[screenshot]' : '')}
              {m.isStreaming && (
                <span style={{
                  display: 'inline-block', width: 5, height: 10,
                  background: '#a78bfa', marginLeft: 2, borderRadius: 2,
                  animation: 'blink 0.7s infinite', verticalAlign: 'text-bottom',
                }} />
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Input compacto */}
      <div style={{
        padding: '7px 8px',
        borderTop: '1px solid var(--color-krirk-border)',
        display: 'flex', gap: 5, alignItems: 'center',
        background: 'var(--color-krirk-sidebar)',
      }}>
        <VoiceButton onTranscript={handleTranscript} disabled={!connected || aiStateBusy} />
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), submit())}
          placeholder="Digite uma mensagem..."
          disabled={!connected || aiStateBusy}
          style={{
            flex: 1, padding: '6px 9px', borderRadius: 7,
            border: '1px solid var(--color-krirk-border)',
            background: 'var(--color-krirk-surface)',
            color: 'var(--color-krirk-text)',
            fontSize: 11, outline: 'none',
          }}
        />
        <button
          onClick={submit}
          disabled={!connected || aiStateBusy || !input.trim()}
          style={{
            width: 28, height: 28, borderRadius: 7, border: 'none',
            background: input.trim() && connected && !aiStateBusy
              ? 'var(--color-krirk-accent)' : 'var(--color-krirk-surface)',
            color: '#fff', cursor: 'pointer', fontSize: 11,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'background 0.15s', flexShrink: 0,
          }}
        >▶</button>
      </div>
    </div>
  )
}
