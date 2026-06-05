import React, { useState, useCallback, useEffect, useRef } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { Sidebar, AppMode } from './components/Sidebar'
import { ChatMode } from './components/ChatMode'
import { AvatarMode } from './components/AvatarMode'
import { HudMode } from './components/HudMode'
import { CompactHeader } from './components/CompactHeader'
import { Message, WSEvent } from './types'

// ── Audio ─────────────────────────────────────────────────────────────────────
async function playAudioBase64(b64: string) {
  try {
    const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0))
    const ctx = new AudioContext()
    if (ctx.state === 'suspended') await ctx.resume()
    const buffer = await ctx.decodeAudioData(bytes.buffer)
    const src = ctx.createBufferSource()
    src.buffer = buffer
    src.connect(ctx.destination)
    src.start(0)
    src.onended = () => ctx.close()
  } catch (e) { console.warn('[TTS]', e) }
}

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
  const { connected, aiState, emotion, sendMessage, sendScreenshot, onEvent } = useWebSocket()
  const [mode, setMode] = useState<AppMode>('chat')

  // ── Estado de mensagens compartilhado ─────────────────────────────────────
  // Fica no App para sobreviver a trocas de modo (Chat ↔ Sidebar ↔ Avatar)
  const [messages, setMessages] = useState<Message[]>([])
  const streamingIdRef = useRef<string | null>(null)

  const addMsg = useCallback((msg: Message) => {
    setMessages(p => [...p, msg])
  }, [])

  const appendToken = useCallback((id: string, token: string) => {
    setMessages(p => p.map(m => m.id === id ? { ...m, content: m.content + token } : m))
  }, [])

  const finalizeMsg = useCallback((id: string, emotion?: string) => {
    setMessages(p => p.map(m =>
      m.id === id ? { ...m, isStreaming: false, emotion: emotion as never } : m
    ))
  }, [])

  // Única subscrição de eventos WS — centralizada aqui
  useEffect(() => {
    const unsub = onEvent((ev: WSEvent) => {
      if (ev.type === 'connected') {
        if (ev.history && ev.history.length > 0) {
          // Restaura conversa anterior
          setMessages(ev.history.map((m, i) => ({
            id: `history-${i}`,
            role: m.role as 'user' | 'assistant',
            content: m.content,
            timestamp: new Date(),
          })))
        }
        // Sem mensagem de saudação — histórico fala por si
        return
      }
      if (ev.type === 'transcription' && ev.content) {
        addMsg({ id: `user-${Date.now()}`, role: 'user', content: ev.content, timestamp: new Date() })
        return
      }
      if (ev.type === 'token' && ev.content) {
        if (!streamingIdRef.current) {
          const id = `ai-${Date.now()}`
          streamingIdRef.current = id
          addMsg({ id, role: 'assistant', content: ev.content, timestamp: new Date(), isStreaming: true })
        } else {
          appendToken(streamingIdRef.current, ev.content)
        }
        return
      }
      if (ev.type === 'response_complete') {
        if (streamingIdRef.current) {
          const id = streamingIdRef.current
          streamingIdRef.current = null
          // Substitui conteúdo streamado pela versão limpa (sem reasoning tags)
          setMessages(p => p.map(m =>
            m.id === id
              ? { ...m, content: ev.content ?? m.content, isStreaming: false, emotion: ev.emotion as never }
              : m
          ))
        }
        if (ev.audio) playAudioBase64(ev.audio)
        return
      }
      if (ev.type === 'proactive_comment' && ev.content) {
        addMsg({
          id: `proactive-${Date.now()}`,
          role: 'assistant',
          content: ev.content,
          emotion: ev.emotion,
          timestamp: new Date(),
          isProactive: true,
        })
        if (ev.audio) playAudioBase64(ev.audio)
        return
      }
      if (ev.type === 'tool_call' && ev.tool) {
        addMsg({
          id: `tool-${Date.now()}`,
          role: 'tool',
          content: '',
          toolName: ev.tool,
          timestamp: new Date(),
          isRunning: true,
        })
        return
      }
      if (ev.type === 'tool_result') {
        setMessages(p => {
          // Encontra a última mensagem de tool em execução e atualiza
          const idx = [...p].reverse().findIndex(m => m.role === 'tool' && m.isRunning)
          if (idx === -1) return p
          const realIdx = p.length - 1 - idx
          return p.map((m, i) =>
            i === realIdx ? { ...m, isRunning: false, toolResult: ev.result } : m
          )
        })
        return
      }
      if (ev.type === 'screenshot_taken' && ev.thumbnail) {
        addMsg({
          id: `screenshot-${Date.now()}`,
          role: 'assistant',
          content: '',
          thumbnail: `data:image/jpeg;base64,${ev.thumbnail}`,
          timestamp: new Date(),
        })
        return
      }
      if (ev.type === 'error' && ev.message) {
        if (streamingIdRef.current) {
          finalizeMsg(streamingIdRef.current)
          streamingIdRef.current = null
        }
        addMsg({ id: `err-${Date.now()}`, role: 'assistant', content: `⚠️ ${ev.message}`, timestamp: new Date() })
      }
    })
    return unsub
  }, [onEvent, addMsg, appendToken, finalizeMsg])

  // ── Modo & janela ──────────────────────────────────────────────────────────
  const aiStateBusy = aiState !== 'idle'
  const isCompact = mode === 'sidebar' || mode === 'avatar'

  useEffect(() => { adjustWindow(isCompact) }, [isCompact])

  const handleSetMode    = useCallback((m: AppMode) => setMode(m), [])
  const handleOpenSettings = useCallback(() => openSettingsWindow(), [])
  const handleBackToChat = useCallback(() => setMode('chat'), [])

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
            messages={messages}
            addMsg={addMsg}
            emotion={emotion}
            aiState={aiState}
            connected={connected}
            aiStateBusy={aiStateBusy}
            sendMessage={sendMessage}
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
        messageCount={messages.length}
        onOpenSettings={handleOpenSettings}
      />

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <ChatMode
          messages={messages}
          addMsg={addMsg}
          sendMessage={sendMessage}
          sendScreenshot={sendScreenshot}
          connected={connected}
          aiStateBusy={aiStateBusy}
        />
      </main>
    </div>
  )
}
