import React, { useState, useCallback } from 'react'
import { Pin, PinOff, ArrowLeft, X } from 'lucide-react'
import { EmotionType } from '../types'
import { EMOTION_COLOR } from '../utils/emotions'

interface Props {
  emotion: EmotionType
  connected: boolean
  onBack: () => void
}

async function hideWindow() {
  try {
    const { getCurrentWindow } = await import('@tauri-apps/api/window')
    await getCurrentWindow().hide()
  } catch { /* browser dev */ }
}

export function CompactHeader({ emotion, connected, onBack }: Props) {
  const [pinned, setPinned] = useState(true)

  const togglePin = useCallback(async () => {
    const next = !pinned
    setPinned(next)
    try {
      const { invoke } = await import('@tauri-apps/api/core')
      await invoke('set_always_on_top', { value: next })
    } catch { /* browser dev */ }
  }, [pinned])

  return (
    <div
      data-tauri-drag-region
      style={{
        height: 32,
        background: 'var(--color-krirk-sidebar)',
        borderBottom: '1px solid var(--color-krirk-border)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 8px',
        gap: 6,
        userSelect: 'none',
        flexShrink: 0,
      }}
    >
      {/* Logo */}
      <span style={{
        fontSize: 11,
        fontWeight: 800,
        letterSpacing: '0.1em',
        background: 'linear-gradient(135deg, #7c3aed, #a855f7)',
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        flexShrink: 0,
        pointerEvents: 'none',
      }}>
        K
      </span>

      {/* Status dot */}
      <span style={{
        width: 6, height: 6, borderRadius: '50%',
        background: EMOTION_COLOR[emotion],
        boxShadow: `0 0 5px ${EMOTION_COLOR[emotion]}`,
        flexShrink: 0,
        pointerEvents: 'none',
      }} />

      {/* Emoção */}
      <span style={{
        fontSize: 9, color: 'var(--color-krirk-muted)',
        textTransform: 'uppercase', letterSpacing: '0.08em',
        flex: 1,
        pointerEvents: 'none',
      }}>
        {emotion}
      </span>

      {/* Indicador de conexão */}
      <span
        title={connected ? 'online' : 'offline'}
        style={{
          width: 5, height: 5, borderRadius: '50%',
          background: connected ? 'var(--color-krirk-online)' : 'var(--color-krirk-offline)',
          flexShrink: 0,
        }}
      />

      {/* Fixar / desafixar */}
      <button
        onClick={togglePin}
        title={pinned ? 'Desafixar' : 'Fixar sempre no topo'}
        style={btn(pinned ? '#a78bfa' : 'rgba(255,255,255,0.35)')}
      >
        {pinned ? <Pin size={11} /> : <PinOff size={11} />}
      </button>

      {/* Voltar ao chat */}
      <button
        onClick={onBack}
        title="Voltar ao modo Chat"
        style={btn('rgba(255,255,255,0.5)')}
        onMouseEnter={e => (e.currentTarget.style.color = '#a78bfa')}
        onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.5)')}
      >
        <ArrowLeft size={11} />
      </button>

      {/* Ocultar para bandeja */}
      <button
        onClick={hideWindow}
        title="Ocultar (reabre pelo ícone na bandeja)"
        style={btn('rgba(255,255,255,0.35)')}
        onMouseEnter={e => (e.currentTarget.style.color = '#ef4444')}
        onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.35)')}
      >
        <X size={11} />
      </button>
    </div>
  )
}

function btn(color: string): React.CSSProperties {
  return {
    background: 'none',
    border: 'none',
    color,
    cursor: 'pointer',
    padding: '0 2px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    lineHeight: 1,
    transition: 'color 0.15s',
    flexShrink: 0,
  }
}
