import { useState, useCallback } from 'react'
import { EmotionType, AIState } from '../types'
import { EMOTION_COLOR } from '../utils/emotions'

async function tauriSetAlwaysOnTop(value: boolean) {
  try {
    const { invoke } = await import('@tauri-apps/api/core')
    await invoke('set_always_on_top', { value })
  } catch { /* browser dev mode */ }
}

const STATE_LABEL: Record<AIState, string> = {
  idle: 'Esperando',
  thinking: 'Pensando...',
  speaking: 'Respondendo...',
  listening: 'Ouvindo...',
  executing: 'Executando...',
}

const STATE_COLOR: Record<AIState, string> = {
  idle: '#52525b',
  thinking: '#a78bfa',
  speaking: '#34d399',
  listening: '#60a5fa',
  executing: '#fb923c',
}

interface Props {
  emotion: EmotionType
  state: AIState
  connected: boolean
}

export function EmotionIndicator({ emotion, state, connected }: Props) {
  const [pinned, setPinned] = useState(false)

  const togglePin = useCallback(() => {
    const next = !pinned
    setPinned(next)
    tauriSetAlwaysOnTop(next)
  }, [pinned])

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      padding: '8px 14px',
      background: '#18181b',
      borderBottom: '1px solid #27272a',
      fontSize: '13px',
    }}>
      <span style={{
        width: 14, height: 14, borderRadius: '50%',
        background: EMOTION_COLOR[emotion] ?? '#71717a',
        display: 'inline-block',
        boxShadow: `0 0 6px ${EMOTION_COLOR[emotion] ?? '#71717a'}`,
      }} title={emotion} />
      <span style={{ color: '#a1a1aa' }}>Krirk</span>
      <span style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        color: STATE_COLOR[state],
        marginLeft: 'auto',
      }}>
        {state !== 'idle' && (
          <span style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: STATE_COLOR[state],
            animation: 'pulse 1s infinite',
            display: 'inline-block',
          }} />
        )}
        {STATE_LABEL[state]}
      </span>
      {/* Botão sempre-no-topo (só visível quando rodando via Tauri) */}
      <button
        onClick={togglePin}
        title={pinned ? 'Desafixar janela' : 'Fixar janela sempre no topo'}
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          fontSize: '14px',
          opacity: pinned ? 1 : 0.4,
          marginLeft: '4px',
          padding: '0 2px',
          color: pinned ? '#a78bfa' : '#a1a1aa',
        }}
      >
        📌
      </button>
      <span style={{
        width: 8,
        height: 8,
        borderRadius: '50%',
        background: connected ? '#22c55e' : '#ef4444',
        marginLeft: '4px',
      }} title={connected ? 'Conectado' : 'Desconectado'} />
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  )
}
