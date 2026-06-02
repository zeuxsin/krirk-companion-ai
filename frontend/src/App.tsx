import React, { useState, useCallback } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { Sidebar, AppMode } from './components/Sidebar'
import { ChatMode } from './components/ChatMode'
import { AvatarMode } from './components/AvatarMode'
import { HudMode } from './components/HudMode'

async function openSettingsWindow() {
  try {
    const { invoke } = await import('@tauri-apps/api/core')
    await invoke('open_settings')
  } catch {
    // Fora do Tauri (browser dev) — abre em nova aba
    window.open('/?window=settings', '_blank', 'width=420,height=340')
  }
}

export default function App() {
  const { connected, aiState, emotion, sendMessage, onEvent } = useWebSocket()
  const [mode, setMode] = useState<AppMode>('chat')
  const [messageCount, setMessageCount] = useState(0)

  const aiStateBusy = aiState !== 'idle'

  const handleOpenSettings = useCallback(() => {
    openSettingsWindow()
  }, [])

  return (
    <div style={{
      height: '100vh', display: 'flex', flexDirection: 'row',
      background: 'var(--color-krirk-bg)', overflow: 'hidden',
    }}>
      <Sidebar
        mode={mode}
        setMode={setMode}
        emotion={emotion}
        aiState={aiState}
        connected={connected}
        messageCount={messageCount}
        onOpenSettings={handleOpenSettings}
      />

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {mode === 'chat' && (
          <ChatMode
            sendMessage={sendMessage}
            onEvent={onEvent}
            connected={connected}
            aiStateBusy={aiStateBusy}
            onMessageCountChange={setMessageCount}
          />
        )}
        {mode === 'avatar' && (
          <AvatarMode
            emotion={emotion}
            aiState={aiState}
            onEvent={onEvent}
          />
        )}
        {mode === 'hud' && (
          <HudMode
            emotion={emotion}
            aiState={aiState}
            connected={connected}
            aiStateBusy={aiStateBusy}
            sendMessage={sendMessage}
            onEvent={onEvent}
          />
        )}
      </main>
    </div>
  )
}
