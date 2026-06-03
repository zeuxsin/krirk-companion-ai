import React, { useState, useEffect, useRef, useCallback } from 'react'
import { EmotionType, AIState, Message, WSEvent } from '../types'

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
  onEvent: (handler: (e: WSEvent) => void) => () => void
}

export function AvatarMode({ emotion, aiState, onEvent }: Props) {
  const [imgSrc, setImgSrc] = useState(`/avatar/${EMOTION_TO_IMG[emotion]}.png`)
  const [imgOpacity, setImgOpacity] = useState(1)
  const [lastMessages, setLastMessages] = useState<Message[]>([])
  const prevEmotion = useRef(emotion)

  // Troca de imagem com fade
  useEffect(() => {
    if (emotion === prevEmotion.current) return
    prevEmotion.current = emotion
    setImgOpacity(0)
    const t = setTimeout(() => {
      setImgSrc(`/avatar/${EMOTION_TO_IMG[emotion]}.png`)
      setImgOpacity(1)
    }, 150)
    return () => clearTimeout(t)
  }, [emotion])

  const handleImgError = useCallback(() => {
    setImgSrc(src => src.endsWith('.png') ? `/avatar/${EMOTION_TO_IMG[emotion]}.svg` : src)
  }, [emotion])

  // Captura as últimas mensagens para o speech bubble
  useEffect(() => {
    const unsub = onEvent((ev: WSEvent) => {
      if (ev.type === 'response_complete' && ev.content) {
        setLastMessages(prev => [...prev.slice(-2), {
          id: `ai-${Date.now()}`,
          role: 'assistant',
          content: ev.content ?? '',
          timestamp: new Date(),
        }])
      }
    })
    return unsub
  }, [onEvent])

  const lastMsg = lastMessages[lastMessages.length - 1]

  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      background: 'var(--color-krirk-bg)',
      padding: 24, gap: 16, position: 'relative',
    }}>
      {/* Speech bubble da última mensagem */}
      {lastMsg && (
        <div style={{
          maxWidth: 280, padding: '10px 14px',
          background: 'rgba(255,255,255,0.06)',
          border: '1px solid var(--color-krirk-border)',
          borderRadius: '12px 12px 12px 4px',
          fontSize: 12, lineHeight: 1.6,
          color: 'var(--color-krirk-text)',
          marginBottom: -8,
        }}
          className="anim-fadein"
        >
          {lastMsg.content.slice(0, 140)}{lastMsg.content.length > 140 ? '...' : ''}
        </div>
      )}

      {/* Avatar */}
      <img
        src={imgSrc}
        alt={`Krirk — ${emotion}`}
        onError={handleImgError}
        className={ANIM_BY_STATE[aiState]}
        style={{
          width: 220,
          opacity: imgOpacity,
          transition: 'opacity 0.15s',
          pointerEvents: 'none',
          filter: aiState === 'speaking' ? 'drop-shadow(0 0 12px rgba(124,58,237,0.5))' : 'none',
        }}
      />

      {/* Label da emoção */}
      <div style={{
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: '0.15em',
        textTransform: 'uppercase',
        color: 'var(--color-krirk-muted)',
        marginTop: -8,
      }}>
        {emotion}
      </div>
    </div>
  )
}
