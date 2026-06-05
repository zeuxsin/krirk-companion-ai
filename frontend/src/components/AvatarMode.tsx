import React, { useState, useEffect, useRef, useCallback } from 'react'
import { EmotionType, AIState, Message, WSEvent } from '../types'
import {
  EMOTION_COLOR,
  avatarAnimClass,
  avatarSrc,
  avatarFallback,
} from '../utils/emotions'

interface Props {
  emotion: EmotionType
  aiState: AIState
  onEvent: (handler: (e: WSEvent) => void) => () => void
}

export function AvatarMode({ emotion, aiState, onEvent }: Props) {
  const [imgSrc, setImgSrc]       = useState(avatarSrc(emotion))
  const [imgOpacity, setImgOpacity] = useState(1)
  const [lastMessages, setLastMessages] = useState<Message[]>([])
  const prevEmotion = useRef(emotion)

  // Troca de imagem com fade suave ao mudar emoção
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

  // Captura as últimas respostas da Krirk para o speech bubble
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
  const emotionColor = EMOTION_COLOR[emotion]
  const animClass = avatarAnimClass(aiState, emotion)

  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      background: 'var(--color-krirk-bg)',
      padding: 24, gap: 16, position: 'relative',
    }}>

      {/* Speech bubble da última mensagem */}
      {lastMsg && (
        <div
          className="anim-fadein"
          style={{
            maxWidth: 280, padding: '10px 14px',
            background: 'rgba(255,255,255,0.06)',
            border: '1px solid var(--color-krirk-border)',
            borderLeft: `3px solid ${emotionColor}`,
            borderRadius: '12px 12px 12px 4px',
            fontSize: 12, lineHeight: 1.6,
            color: 'var(--color-krirk-text)',
            marginBottom: -8,
            transition: 'border-color 0.4s ease',
          }}
        >
          {lastMsg.content.slice(0, 140)}{lastMsg.content.length > 140 ? '...' : ''}
        </div>
      )}

      {/* Container do avatar com anel de brilho */}
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {/* Anel de brilho colorido por emoção */}
        <div style={{
          position: 'absolute',
          width: 250, height: 250,
          borderRadius: '50%',
          background: `radial-gradient(circle, ${emotionColor}18 0%, transparent 65%)`,
          boxShadow: `0 0 50px 10px ${emotionColor}30`,
          transition: 'background 0.6s ease, box-shadow 0.6s ease',
          pointerEvents: 'none',
        }} />

        {/* Avatar */}
        <img
          src={imgSrc}
          alt={`Krirk — ${emotion}`}
          onError={handleImgError}
          className={animClass}
          style={{
            width: 220,
            position: 'relative', zIndex: 1,
            opacity: imgOpacity,
            transition: 'opacity 0.15s',
            pointerEvents: 'none',
            filter: aiState === 'speaking'
              ? `drop-shadow(0 0 14px ${emotionColor}88)`
              : 'none',
          }}
        />
      </div>

      {/* Label da emoção */}
      <div style={{
        fontSize: 10, fontWeight: 700,
        letterSpacing: '0.15em',
        textTransform: 'uppercase',
        color: emotionColor,
        marginTop: -8,
        transition: 'color 0.4s ease',
      }}>
        {emotion}
      </div>
    </div>
  )
}
