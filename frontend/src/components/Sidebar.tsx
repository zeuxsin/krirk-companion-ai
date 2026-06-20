import React from 'react'
import { MessageSquare, LayoutGrid, Sparkles, Terminal, Settings } from 'lucide-react'
import { EmotionType, AIState } from '../types'
import { EMOTION_COLOR } from '../utils/emotions'

export type AppMode = 'chat' | 'sidebar' | 'avatar' | 'code' | 'settings'

const MODE_ITEMS: { id: AppMode; label: string; Icon: React.ElementType }[] = [
  { id: 'chat',     label: 'Chat',          Icon: MessageSquare },
  { id: 'sidebar',  label: 'Sidebar',       Icon: LayoutGrid },
  { id: 'avatar',   label: 'Avatar',        Icon: Sparkles },
  { id: 'code',     label: 'Coder',         Icon: Terminal },
  { id: 'settings', label: 'Configurações', Icon: Settings },
]

interface Props {
  mode: AppMode
  setMode: (m: AppMode) => void
  emotion: EmotionType
  aiState: AIState
  connected: boolean
  messageCount: number
  onOpenSettings: () => void
}

export function Sidebar({
  mode, setMode, emotion, aiState, connected, messageCount, onOpenSettings,
}: Props) {
  const stateLabel: Record<AIState, string> = {
    idle:      'em espera',
    thinking:  'pensando...',
    speaking:  'respondendo',
    listening: 'ouvindo',
    executing: 'executando',
  }

  return (
    <aside style={{
      width: 130,
      minWidth: 130,
      background: 'var(--color-krirk-sidebar)',
      borderRight: '1px solid var(--color-krirk-border)',
      display: 'flex',
      flexDirection: 'column',
      padding: '16px 10px',
      gap: 0,
      flexShrink: 0,
    }}>
      {/* Logo */}
      <div style={{
        fontSize: 22,
        fontWeight: 800,
        letterSpacing: '0.12em',
        background: 'linear-gradient(135deg, #7c3aed, #a855f7)',
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        marginBottom: 20,
        paddingLeft: 4,
      }}>
        KRIRK
      </div>

      {/* Status */}
      <div style={{ marginBottom: 12 }}>
        <div style={{
          fontSize: 9,
          fontWeight: 700,
          letterSpacing: '0.12em',
          color: 'var(--color-krirk-muted)',
          textTransform: 'uppercase',
          marginBottom: 6,
          paddingLeft: 4,
        }}>
          Status
        </div>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          paddingLeft: 4,
        }}>
          <span style={{
            width: 7,
            height: 7,
            borderRadius: '50%',
            background: EMOTION_COLOR[emotion],
            flexShrink: 0,
            boxShadow: `0 0 6px ${EMOTION_COLOR[emotion]}`,
          }} />
          <span style={{ fontSize: 11, color: 'var(--color-krirk-text)', fontWeight: 500 }}>
            {emotion}
          </span>
        </div>
        <div style={{
          paddingLeft: 4,
          marginTop: 3,
          fontSize: 9,
          color: 'var(--color-krirk-muted)',
        }}>
          {stateLabel[aiState]}
        </div>
      </div>

      <div style={{
        height: 1,
        background: 'var(--color-krirk-border)',
        margin: '4px 0 12px',
      }} />

      {/* Modos */}
      <div style={{ marginBottom: 8 }}>
        <div style={{
          fontSize: 9,
          fontWeight: 700,
          letterSpacing: '0.12em',
          color: 'var(--color-krirk-muted)',
          textTransform: 'uppercase',
          marginBottom: 6,
          paddingLeft: 4,
        }}>
          Modo
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {MODE_ITEMS.map(({ id, label, Icon }) => {
            const isActive = mode === id && id !== 'settings'
            return (
              <button
                key={id}
                onClick={() => id === 'settings' ? onOpenSettings() : setMode(id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 7,
                  padding: '7px 8px',
                  borderRadius: 6,
                  border: 'none',
                  background: isActive ? 'var(--color-krirk-accent)' : 'transparent',
                  color: isActive ? '#fff' : 'rgba(255,255,255,0.55)',
                  fontSize: 12,
                  fontWeight: isActive ? 600 : 400,
                  cursor: 'pointer',
                  textAlign: 'left',
                  width: '100%',
                  transition: 'background 0.15s, color 0.15s',
                }}
                onMouseEnter={e => {
                  if (!isActive) (e.currentTarget as HTMLButtonElement).style.background = 'rgba(124,58,237,0.15)'
                }}
                onMouseLeave={e => {
                  if (!isActive) (e.currentTarget as HTMLButtonElement).style.background = 'transparent'
                }}
              >
                <Icon size={14} />
                <span>{label}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Rodapé */}
      <div style={{
        borderTop: '1px solid var(--color-krirk-border)',
        paddingTop: 8,
        display: 'flex',
        flexDirection: 'column',
        gap: 3,
      }}>
        <div style={{ fontSize: 9, color: 'var(--color-krirk-muted)' }}>
          {messageCount} {messageCount === 1 ? 'mensagem' : 'mensagens'}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%',
            background: connected ? 'var(--color-krirk-online)' : 'var(--color-krirk-offline)',
          }} />
          <span style={{ fontSize: 9, color: 'var(--color-krirk-muted)' }}>
            {connected ? 'online' : 'offline'}
          </span>
        </div>
      </div>
    </aside>
  )
}

