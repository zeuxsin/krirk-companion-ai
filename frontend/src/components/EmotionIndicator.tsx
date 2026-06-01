import React from 'react'
import { EmotionType, AIState } from '../types'

const EMOTION_EMOJI: Record<EmotionType, string> = {
  neutral: '😐',
  happy: '😊',
  curious: '🤔',
  thoughtful: '💭',
  excited: '🤩',
  concerned: '😟',
  playful: '😄',
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
      <span style={{ fontSize: '22px' }} title={emotion}>
        {EMOTION_EMOJI[emotion]}
      </span>
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
      <span style={{
        width: 8,
        height: 8,
        borderRadius: '50%',
        background: connected ? '#22c55e' : '#ef4444',
        marginLeft: '8px',
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
