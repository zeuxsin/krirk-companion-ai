import { useState, useEffect, useRef, useCallback } from 'react'
import type { CSSProperties } from 'react'
import { ArrowLeft, Pin, PinOff, X } from 'lucide-react'
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
  onBack: () => void
}

const BUBBLE_BG = 'rgba(20,20,30,0.93)'

async function tauriWin() {
  const { getCurrentWindow } = await import('@tauri-apps/api/window')
  return getCurrentWindow()
}

export function AvatarMode({ emotion, aiState, onEvent, onBack }: Props) {
  const [imgSrc, setImgSrc]       = useState(avatarSrc(emotion))
  const [imgOpacity, setImgOpacity] = useState(1)
  const [visibleMsg, setVisibleMsg] = useState<Message | null>(null)
  const [pinned, setPinned]         = useState(true)
  const prevEmotion = useRef(emotion)

  // Troca de imagem com fade suave
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

  // Captura a última resposta para o speech bubble
  useEffect(() => {
    const unsub = onEvent((ev: WSEvent) => {
      if (ev.type === 'response_complete' && ev.content) {
        setVisibleMsg({
          id: `ai-${Date.now()}`,
          role: 'assistant',
          content: ev.content ?? '',
          timestamp: new Date(),
        })
      }
    })
    return unsub
  }, [onEvent])

  // Auto-dismiss após 8s
  useEffect(() => {
    if (!visibleMsg) return
    const t = setTimeout(() => setVisibleMsg(null), 8000)
    return () => clearTimeout(t)
  }, [visibleMsg])

  const togglePin = useCallback(async () => {
    const next = !pinned
    setPinned(next)
    try {
      const win = await tauriWin()
      await win.setAlwaysOnTop(next)
    } catch { /* browser dev */ }
  }, [pinned])

  const handleBack = useCallback(() => {
    onBack()
  }, [onBack])

  const handleClose = useCallback(async () => {
    try {
      const win = await tauriWin()
      await win.hide()
    } catch { /* browser dev */ }
  }, [])

  const emotionColor = EMOTION_COLOR[emotion]
  const animClass = avatarAnimClass(aiState, emotion)

  return (
    <div style={{
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      background: 'transparent',
      overflow: 'hidden',
      position: 'relative',
    }}>

      {/* Barra de controles — sempre visível no topo */}
      <div
        data-tauri-drag-region
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          padding: '6px 8px',
          gap: 4,
          background: 'rgba(10,10,16,0.55)',
          flexShrink: 0,
          userSelect: 'none',
        }}
      >
        {/* Voltar ao chat */}
        <button
          onClick={handleBack}
          title="Voltar ao chat"
          style={ctrlBtn('rgba(255,255,255,0.5)')}
          onMouseEnter={e => (e.currentTarget.style.background = 'rgba(124,58,237,0.5)')}
          onMouseLeave={e => (e.currentTarget.style.background = 'rgba(0,0,0,0.35)')}
        >
          <ArrowLeft size={11} />
        </button>

        {/* Emoção atual — pequeno badge */}
        <span style={{
          fontSize: 9, fontWeight: 700,
          letterSpacing: '0.12em', textTransform: 'uppercase',
          color: emotionColor,
          flex: 1,
          paddingLeft: 4,
          pointerEvents: 'none',
        }}>
          {emotion}
        </span>

        {/* Pin */}
        <button
          onClick={togglePin}
          title={pinned ? 'Desafixar' : 'Fixar sempre no topo'}
          style={ctrlBtn(pinned ? emotionColor : 'rgba(255,255,255,0.4)')}
        >
          {pinned ? <Pin size={11} /> : <PinOff size={11} />}
        </button>

        {/* Fechar / voltar ao chat */}
        <button
          onClick={handleClose}
          title="Fechar avatar (volta ao chat)"
          style={ctrlBtn('rgba(255,255,255,0.4)')}
          onMouseEnter={e => (e.currentTarget.style.background = 'rgba(239,68,68,0.7)')}
          onMouseLeave={e => (e.currentTarget.style.background = 'rgba(0,0,0,0.35)')}
        >
          <X size={11} />
        </button>
      </div>

      {/* Área do avatar — drag region + glow */}
      <div
        data-tauri-drag-region
        style={{
          flex: 1,
          width: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'flex-end',
          position: 'relative',
          minHeight: 0,
          cursor: 'move',
          paddingBottom: 4,
        }}
      >
        {/* Glow radial sob o avatar */}
        <div style={{
          position: 'absolute',
          bottom: 0,
          left: '50%',
          transform: 'translateX(-50%)',
          width: '80%',
          height: '60%',
          background: `radial-gradient(ellipse at bottom, ${emotionColor}22 0%, transparent 70%)`,
          pointerEvents: 'none',
          transition: 'background 0.6s ease',
        }} />

        {/* Speech bubble acima do avatar */}
        {visibleMsg && (
          <div
            className="anim-fadein"
            style={{
              position: 'absolute',
              bottom: '60%',
              left: '50%',
              transform: 'translateX(-50%)',
              zIndex: 10,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              pointerEvents: 'none',
              width: '85%',
              maxWidth: 240,
            }}
          >
            <div style={{
              background: BUBBLE_BG,
              border: `1px solid ${emotionColor}55`,
              borderRadius: 10,
              padding: '8px 12px',
              fontSize: 11,
              lineHeight: 1.6,
              color: '#e4e4e7',
              textAlign: 'center',
              boxShadow: `0 4px 16px rgba(0,0,0,0.6)`,
              width: '100%',
            }}>
              {visibleMsg.content.slice(0, 160)}{visibleMsg.content.length > 160 ? '…' : ''}
            </div>
            {/* Triângulo apontando para baixo */}
            <div style={{
              width: 0, height: 0,
              borderLeft: '7px solid transparent',
              borderRight: '7px solid transparent',
              borderTop: `8px solid ${BUBBLE_BG}`,
            }} />
          </div>
        )}

        {/* Avatar */}
        <img
          src={imgSrc}
          alt={`Krirk — ${emotion}`}
          onError={handleImgError}
          className={animClass}
          style={{
            maxHeight: '100%',
            maxWidth: '100%',
            width: 'auto',
            height: 'auto',
            objectFit: 'contain',
            position: 'relative',
            zIndex: 1,
            opacity: imgOpacity,
            transition: 'opacity 0.15s',
            pointerEvents: 'none',
            filter: aiState === 'speaking'
              ? `drop-shadow(0 0 20px ${emotionColor}aa)`
              : `drop-shadow(0 4px 12px rgba(0,0,0,0.5))`,
          }}
        />
      </div>
    </div>
  )
}

function ctrlBtn(color: string): CSSProperties {
  return {
    width: 22, height: 22, borderRadius: 5,
    border: 'none',
    background: 'rgba(0,0,0,0.35)',
    color,
    cursor: 'pointer',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    padding: 0,
    transition: 'background 0.15s, color 0.15s',
    flexShrink: 0,
  }
}

