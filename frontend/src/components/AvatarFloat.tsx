import { useState, useEffect, useRef, useCallback } from 'react'
import type { CSSProperties } from 'react'
import { Pin, PinOff, X } from 'lucide-react'
import type { EmotionType, AIState } from '../types'
import { EMOTION_COLOR, avatarAnimClass, avatarSrc, avatarFallback, normalizeEmotion } from '../utils/emotions'

interface KrirkUpdate {
  emotion?: string
  aiState?: AIState
  message?: string
}

const BUBBLE_BG = 'rgba(20,20,30,0.93)'

async function tauriWin() {
  const { getCurrentWindow } = await import('@tauri-apps/api/window')
  return getCurrentWindow()
}

export function AvatarFloat() {
  const [emotion, setEmotion]     = useState<EmotionType>('neutro')
  const [aiState, setAiState]     = useState<AIState>('idle')
  const [message, setMessage]     = useState<string | null>(null)
  const [imgSrc, setImgSrc]       = useState(() => avatarSrc('neutro'))
  const [imgOpacity, setImgOpacity] = useState(1)
  const [pinned, setPinned]         = useState(true)
  const prevEmotion = useRef<EmotionType>('neutro')
  const msgTimer    = useRef<number | undefined>(undefined)

  // Deixa o fundo transparente
  useEffect(() => {
    document.body.style.background = 'transparent'
    document.documentElement.style.background = 'transparent'
  }, [])

  // Escuta eventos krirk-update do App principal
  useEffect(() => {
    let unlisten: (() => void) | null = null
    import('@tauri-apps/api/event').then(({ listen }) => {
      listen<KrirkUpdate>('krirk-update', (ev) => {
        const { emotion: emo, aiState: state, message: msg } = ev.payload
        if (emo)   setEmotion(normalizeEmotion(emo))
        if (state) setAiState(state)
        if (msg) {
          setMessage(msg)
          clearTimeout(msgTimer.current)
          msgTimer.current = window.setTimeout(() => setMessage(null), 8000)
        }
      }).then(fn => { unlisten = fn })
    })
    return () => {
      unlisten?.()
      clearTimeout(msgTimer.current)
    }
  }, [])

  // Fade suave ao trocar emoção
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

  const togglePin = useCallback(async () => {
    const next = !pinned
    setPinned(next)
    try {
      const win = await tauriWin()
      await win.setAlwaysOnTop(next)
    } catch { /* browser dev */ }
  }, [pinned])

  const handleClose = useCallback(async () => {
    try {
      const { invoke } = await import('@tauri-apps/api/core')
      await invoke('close_avatar_float')
    } catch { /* browser dev */ }
  }, [])

  const emotionColor = EMOTION_COLOR[emotion]
  const animClass    = avatarAnimClass(aiState, emotion)

  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      background: 'transparent',
      overflow: 'hidden',
    }}>
      {/* Barra de controles */}
      <div
        data-tauri-drag-region
        style={{
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

        <button
          onClick={togglePin}
          title={pinned ? 'Desafixar' : 'Fixar sempre no topo'}
          style={ctrlBtn(pinned ? emotionColor : 'rgba(255,255,255,0.4)')}
        >
          {pinned ? <Pin size={11} /> : <PinOff size={11} />}
        </button>

        <button
          onClick={handleClose}
          title="Fechar avatar flutuante"
          style={ctrlBtn('rgba(255,255,255,0.4)')}
          onMouseEnter={e => (e.currentTarget.style.background = 'rgba(239,68,68,0.7)')}
          onMouseLeave={e => (e.currentTarget.style.background = 'rgba(0,0,0,0.35)')}
        >
          <X size={11} />
        </button>
      </div>

      {/* Área do avatar */}
      <div
        data-tauri-drag-region
        style={{
          flex: 1,
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
        {/* Glow */}
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

        {/* Speech bubble */}
        {message && (
          <div className="anim-fadein" style={{
            position: 'absolute',
            bottom: '60%',
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 10,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            pointerEvents: 'none',
            width: '90%',
            maxWidth: 200,
          }}>
            <div style={{
              background: BUBBLE_BG,
              border: `1px solid ${emotionColor}55`,
              borderRadius: 10,
              padding: '8px 12px',
              fontSize: 11,
              lineHeight: 1.6,
              color: '#e4e4e7',
              textAlign: 'center',
              boxShadow: '0 4px 16px rgba(0,0,0,0.6)',
              width: '100%',
            }}>
              {message.slice(0, 120)}{message.length > 120 ? '…' : ''}
            </div>
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
              : 'drop-shadow(0 4px 12px rgba(0,0,0,0.5))',
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
