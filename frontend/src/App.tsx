import React, { useState, useCallback, useEffect } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { Sidebar, AppMode } from './components/Sidebar'
import { ChatMode } from './components/ChatMode'
import { AvatarMode } from './components/AvatarMode'
import { HudMode } from './components/HudMode'
import { CompactHeader } from './components/CompactHeader'


async function adjustWindow(compact: boolean) {
  try {
    const { invoke } = await import('@tauri-apps/api/core')
    await invoke('set_compact_mode', { compact })
  } catch (e) {
    console.error('[KRIRK] adjustWindow falhou:', e)
  }
}

async function openSettingsWindow() {
  try {
    const { invoke } = await import('@tauri-apps/api/core')
    await invoke('open_settings')
  } catch {
    window.open('/?window=settings', '_blank', 'width=420,height=340')
  }
}

export default function App() {
  const { connected, aiState, emotion, sendMessage, onEvent } = useWebSocket()
  const [mode, setMode] = useState<AppMode>('chat')
  const [messageCount, setMessageCount] = useState(0)

  const aiStateBusy = aiState !== 'idle'
  const isCompact = mode === 'sidebar' || mode === 'avatar'

  // Reposiciona/redimensiona a janela ao mudar de modo
  useEffect(() => {
    adjustWindow(isCompact)
  }, [isCompact])

  const handleSetMode = useCallback((m: AppMode) => {
    setMode(m)
  }, [])

  const handleOpenSettings = useCallback(() => {
    openSettingsWindow()
  }, [])

  const handleBackToChat = useCallback(() => {
    setMode('chat')
  }, [])

  // ── Modo compacto (Sidebar / Avatar) ──────────────────────────────────────
  if (isCompact) {
    return (
      <div style={{
        height: '100vh', display: 'flex', flexDirection: 'column',
        background: 'var(--color-krirk-bg)', overflow: 'hidden',
      }}>
        <CompactHeader
          emotion={emotion}
          connected={connected}
          onBack={handleBackToChat}
        />

        {mode === 'sidebar' && (
          <HudMode
            emotion={emotion}
            aiState={aiState}
            connected={connected}
            aiStateBusy={aiStateBusy}
            sendMessage={sendMessage}
            onEvent={onEvent}
          />
        )}

        {mode === 'avatar' && (
          <AvatarMode
            emotion={emotion}
            aiState={aiState}
            onEvent={onEvent}
          />
        )}
      </div>
    )
  }

  // ── Modo normal (Chat) ────────────────────────────────────────────────────
  return (
    <div style={{
      height: '100vh', display: 'flex', flexDirection: 'row',
      background: 'var(--color-krirk-bg)', overflow: 'hidden',
    }}>
      <Sidebar
        mode={mode}
        setMode={handleSetMode}
        emotion={emotion}
        aiState={aiState}
        connected={connected}
        messageCount={messageCount}
        onOpenSettings={handleOpenSettings}
      />

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <ChatMode
          sendMessage={sendMessage}
          onEvent={onEvent}
          connected={connected}
          aiStateBusy={aiStateBusy}
          onMessageCountChange={setMessageCount}
        />
      </main>
    </div>
  )
}
