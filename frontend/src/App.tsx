import React, { useState, useCallback, useEffect } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { Sidebar, AppMode } from './components/Sidebar'
import { ChatMode } from './components/ChatMode'
import { AvatarMode } from './components/AvatarMode'
import { HudMode } from './components/HudMode'
import { CompactHeader } from './components/CompactHeader'

// Tamanhos de janela
const NORMAL_W  = 560
const NORMAL_H  = 420
const COMPACT_W = 230
const COMPACT_H = 400
const TASKBAR_H = 48  // altura padrão da taskbar do Windows

async function adjustWindow(compact: boolean) {
  try {
    const { getCurrentWindow } = await import('@tauri-apps/api/window')
    const { LogicalSize, LogicalPosition } = await import('@tauri-apps/api/dpi')
    const win = getCurrentWindow()

    if (compact) {
      const monitor = await win.currentMonitor()
      const sf = monitor?.scaleFactor ?? 1
      const sw = (monitor?.size.width  ?? 1920) / sf
      const sh = (monitor?.size.height ?? 1080) / sf
      await win.setSize(new LogicalSize(COMPACT_W, COMPACT_H))
      await win.setPosition(new LogicalPosition(
        sw - COMPACT_W - 16,
        sh - COMPACT_H - TASKBAR_H,
      ))
      await win.setAlwaysOnTop(true)
    } else {
      await win.setSize(new LogicalSize(NORMAL_W, NORMAL_H))
      await win.center()
      await win.setAlwaysOnTop(false)
    }
  } catch {
    // Browser dev mode — sem Tauri, ignora
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
