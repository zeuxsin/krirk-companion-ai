import React, { useState, useEffect, useRef, useCallback } from 'react'
import { EmotionType, AIState } from '../types'

// Mapeamento: emoção do backend → nome do arquivo de imagem
const EMOTION_TO_IMAGE: Record<EmotionType, string> = {
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

const EMOTION_EMOJI: Record<EmotionType, string> = {
  neutral:    '😐',
  happy:      '😊',
  excited:    '🤩',
  thoughtful: '💭',
  curious:    '🤔',
  concerned:  '😟',
  playful:    '😄',
  angry:      '😠',
  confused:   '😵',
}

// Extensão preferida: tenta PNG, fallback para SVG
function buildSrc(emotion: EmotionType, ext: 'png' | 'svg'): string {
  return `/avatar/${EMOTION_TO_IMAGE[emotion]}.${ext}`
}

// Salvar/restaurar posição no localStorage
const STORAGE_KEY = 'krirk_avatar_pos'
function loadPos(): { x: number; y: number } | null {
  try {
    const s = localStorage.getItem(STORAGE_KEY)
    return s ? JSON.parse(s) : null
  } catch { return null }
}
function savePos(x: number, y: number) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ x, y }))
}

interface Props {
  emotion: EmotionType
  aiState: AIState
}

export function AvatarWidget({ emotion, aiState }: Props) {
  const [minimized, setMinimized] = useState(false)
  const [visible, setVisible] = useState(true)
  const [imgSrc, setImgSrc] = useState(buildSrc(emotion, 'png'))
  const [imgOpacity, setImgOpacity] = useState(1)

  // Posição draggável
  const [pos, setPos] = useState<{ x: number; y: number }>(() => {
    return loadPos() ?? { x: window.innerWidth - 200, y: window.innerHeight - 320 }
  })
  const dragging = useRef(false)
  const dragOffset = useRef({ x: 0, y: 0 })
  const widgetRef = useRef<HTMLDivElement>(null)

  // Trocar imagem com fade quando a emoção muda
  const prevEmotion = useRef(emotion)
  useEffect(() => {
    if (emotion === prevEmotion.current) return
    prevEmotion.current = emotion

    // Fade out
    setImgOpacity(0)
    const timer = setTimeout(() => {
      setImgSrc(buildSrc(emotion, 'png'))
      setImgOpacity(1)
    }, 150)
    return () => clearTimeout(timer)
  }, [emotion])

  // Fallback PNG → SVG
  const handleImgError = useCallback(() => {
    const current = imgSrc
    if (current.endsWith('.png')) {
      setImgSrc(buildSrc(emotion, 'svg'))
    }
  }, [imgSrc, emotion])

  // Drag handlers
  const onMouseDown = useCallback((e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('button')) return
    dragging.current = true
    dragOffset.current = { x: e.clientX - pos.x, y: e.clientY - pos.y }
    e.preventDefault()
  }, [pos])

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragging.current) return
      const nx = Math.max(0, Math.min(window.innerWidth - 180, e.clientX - dragOffset.current.x))
      const ny = Math.max(0, Math.min(window.innerHeight - 240, e.clientY - dragOffset.current.y))
      setPos({ x: nx, y: ny })
    }
    const onUp = () => {
      if (dragging.current) {
        dragging.current = false
        setPos(p => { savePos(p.x, p.y); return p })
      }
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [])

  if (!visible) {
    return (
      <button
        onClick={() => setVisible(true)}
        title="Mostrar Krirk"
        style={{
          position: 'fixed',
          bottom: 16,
          right: 16,
          width: 40,
          height: 40,
          borderRadius: '50%',
          border: '2px solid #7c3aed',
          background: '#18181b',
          fontSize: 20,
          cursor: 'pointer',
          zIndex: 1000,
        }}
      >
        ✨
      </button>
    )
  }

  if (minimized) {
    return (
      <div
        style={{
          position: 'fixed',
          left: pos.x,
          top: pos.y,
          zIndex: 1000,
          cursor: 'grab',
          userSelect: 'none',
        }}
        onMouseDown={onMouseDown}
      >
        <div style={{
          width: 56,
          height: 56,
          borderRadius: '50%',
          background: 'linear-gradient(135deg, #7c3aed, #4f46e5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 26,
          boxShadow: '0 4px 20px rgba(124,58,237,0.5)',
          border: '2px solid #a78bfa',
          animation: 'krirk-idle 3s ease-in-out infinite',
        }}>
          {EMOTION_EMOJI[emotion]}
        </div>
        <button
          onClick={() => setMinimized(false)}
          title="Expandir"
          style={{
            position: 'absolute',
            top: -6, right: -6,
            width: 18, height: 18,
            borderRadius: '50%',
            border: 'none',
            background: '#3f3f46',
            color: '#e4e4e7',
            fontSize: 10,
            cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            lineHeight: 1,
          }}
        >↑</button>
      </div>
    )
  }

  const animClass = {
    idle:      'krirk-idle',
    speaking:  'krirk-speaking',
    thinking:  'krirk-thinking',
    listening: 'krirk-listening',
    executing: '',
  }[aiState]

  return (
    <>
      <style>{`
        @keyframes krirk-idle {
          0%,100% { transform: translateY(0); }
          50%      { transform: translateY(-4px); }
        }
        @keyframes krirk-speaking {
          0%,100% { transform: translateY(0); }
          50%      { transform: translateY(-7px); }
        }
        @keyframes krirk-thinking {
          0%,100% { transform: rotate(0deg); }
          25%      { transform: rotate(-2deg); }
          75%      { transform: rotate(2deg); }
        }
        @keyframes krirk-listening {
          0%,100% { transform: scale(1); }
          50%      { transform: scale(1.04); }
        }
        .krirk-idle      { animation: krirk-idle      3s ease-in-out infinite; }
        .krirk-speaking  { animation: krirk-speaking  0.6s ease-in-out infinite; }
        .krirk-thinking  { animation: krirk-thinking  2s ease-in-out infinite; }
        .krirk-listening { animation: krirk-listening 0.8s ease-in-out infinite; }
      `}</style>

      <div
        ref={widgetRef}
        onMouseDown={onMouseDown}
        style={{
          position: 'fixed',
          left: pos.x,
          top: pos.y,
          zIndex: 1000,
          width: 160,
          userSelect: 'none',
          cursor: 'grab',
        }}
      >
        {/* Botões de controle */}
        <div style={{
          display: 'flex',
          justifyContent: 'flex-end',
          gap: 4,
          marginBottom: 4,
        }}>
          <button
            onClick={() => setMinimized(true)}
            title="Minimizar"
            style={btnStyle}
          >–</button>
          <button
            onClick={() => setVisible(false)}
            title="Fechar"
            style={btnStyle}
          >×</button>
        </div>

        {/* Imagem do avatar */}
        <div style={{
          borderRadius: 16,
          overflow: 'hidden',
          background: 'rgba(124,58,237,0.05)',
          border: aiState === 'speaking'
            ? '2px solid rgba(167,139,250,0.8)'
            : '2px solid rgba(124,58,237,0.2)',
          boxShadow: aiState === 'speaking'
            ? '0 0 20px rgba(124,58,237,0.4)'
            : '0 4px 20px rgba(0,0,0,0.3)',
          transition: 'box-shadow 0.3s, border-color 0.3s',
        }}>
          <img
            src={imgSrc}
            alt={`Krirk — ${emotion}`}
            onError={handleImgError}
            className={animClass}
            style={{
              width: '100%',
              display: 'block',
              opacity: imgOpacity,
              transition: 'opacity 0.15s ease',
              pointerEvents: 'none',
            }}
          />
        </div>

        {/* Badge de emoção */}
        <div style={{
          marginTop: 6,
          textAlign: 'center',
          fontSize: 11,
          color: '#a1a1aa',
          letterSpacing: '0.05em',
        }}>
          {EMOTION_EMOJI[emotion]} {EMOTION_TO_IMAGE[emotion]}
        </div>
      </div>
    </>
  )
}

const btnStyle: React.CSSProperties = {
  width: 20,
  height: 20,
  borderRadius: '50%',
  border: 'none',
  background: '#27272a',
  color: '#a1a1aa',
  fontSize: 13,
  lineHeight: 1,
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: 0,
}
