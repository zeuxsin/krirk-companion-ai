import React, { useState, useCallback } from 'react'
import { EmotionType } from '../types'

const EMOTION_COLOR: Record<EmotionType, string> = {
  neutral:    '#71717a',
  happy:      '#a78bfa',
  excited:    '#f59e0b',
  thoughtful: '#60a5fa',
  curious:    '#34d399',
  concerned:  '#f87171',
  playful:    '#fb923c',
  angry:      '#ef4444',
  confused:   '#c084fc',
}

interface Props {
  emotion: EmotionType
  connected: boolean
  onBack: () => void
}

async function tauriInvoke(cmd: string, args?: Record<string, unknown>) {
  try {
    const { invoke } = await import('@tauri-apps/api/core')
    await invoke(cmd, args)
  } catch { /* browser dev — silencia */ }
}

async function hideWindow() {
  try {
    const { getCurrentWindow } = await import('@tauri-apps/api/window')
    await getCurrentWindow().hide()
  } catch { /* browser dev */ }
}

export function CompactHeader({ emotion, connected, onBack }: Props) {
  const [pinned, setPinned] = useState(true) // compacto começa always-on-top

  const togglePin = useCallback(async () => {
    const next = !pinned
    setPinned(next)
    await tauriInvoke('set_always_on_top', { value: next })
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
      }}>
        K
      </span>

      {/* Status */}
      <span style={{
        width: 6, height: 6, borderRadius: '50%',
        background: EMOTION_COLOR[emotion],
        boxShadow: `0 0 5px ${EMOTION_COLOR[emotion]}`,
        flexShrink: 0,
      }} />
      <span style={{
        fontSize: 9, color: 'var(--color-krirk-muted)',
        textTransform: 'uppercase', letterSpacing: '0.08em',
        flex: 1,
      }}>
        {emotion}
      </span>

      {/* Indicador de conexão */}
      <span style={{
        width: 5, height: 5, borderRadius: '50%',
        background: connected ? 'var(--color-krirk-online)' : 'var(--color-krirk-offline)',
        flexShrink: 0,
      }} title={connected ? 'online' : 'offline'} />

      {/* Botão pin */}
      <button
        onClick={togglePin}
        title={pinned ? 'Desafixar' : 'Fixar sempre no topo'}
        style={btnStyle(pinned ? '#a78bfa' : 'rgba(255,255,255,0.3)')}
      >
        📌
      </button>

      {/* Voltar para Chat */}
      <button
        onClick={onBack}
        title="Voltar ao modo Chat"
        style={btnStyle('rgba(255,255,255,0.5)')}
      >
        ⬡
      </button>

      {/* Fechar / ocultar janela */}
      <button
        onClick={hideWindow}
        title="Ocultar (reabre pelo ícone na bandeja)"
        style={btnStyle('rgba(255,255,255,0.3)')}
        onMouseEnter={e => (e.currentTarget.style.color = '#ef4444')}
        onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.3)')}
      >
        ×
      </button>
    </div>
  )
}

function btnStyle(color: string): React.CSSProperties {
  return {
    background: 'none',
    border: 'none',
    color,
    cursor: 'pointer',
    fontSize: 12,
    padding: '0 2px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    lineHeight: 1,
    transition: 'color 0.15s',
    flexShrink: 0,
  }
}
