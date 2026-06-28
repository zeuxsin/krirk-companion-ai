import { useState, useCallback, useEffect, useRef } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { Sidebar, AppMode } from './components/Sidebar'
import { ChatMode } from './components/ChatMode'
import { CodeMode } from './components/CodeMode'
import { AvatarMode } from './components/AvatarMode'
import { HudMode } from './components/HudMode'
import { CompactHeader } from './components/CompactHeader'
import { Message, WSEvent } from './types'

// Tauri window API (lazy import — falha silenciosa no browser dev)
async function tauriWin() {
  const { getCurrentWindow } = await import('@tauri-apps/api/window')
  return getCurrentWindow()
}

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

async function adjustWindow(mode: AppMode) {
  try {
    const { invoke } = await import('@tauri-apps/api/core')
    const win = await tauriWin()

    const isCompact = mode === 'sidebar' || mode === 'avatar'
    const isAvatar  = mode === 'avatar'

    await invoke('set_compact_mode', { compact: isCompact })

    // Chat / Code → decorações nativas (barra de título do Windows)
    // Sidebar / Avatar → sem decoração (headers customizados)
    await win.setDecorations(!isCompact)

    // Avatar → fundo transparente para o personagem flutuar sobre o desktop
    document.body.style.background = isAvatar ? 'transparent' : ''
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
  const { connected, aiState, emotion, sendMessage: _sendMessage, sendCodeMessage: _sendCodeMessage, sendAudio, sendScreenshot, sendImageMessage, onEvent } = useWebSocket()

  // Wrappers que registram qual sessão está ativa antes de enviar
  const sendMessage = useCallback((content: string) => {
    activeSessionRef.current = 'chat'
    _sendMessage(content)
  }, [_sendMessage])

  const sendCodeMessage = useCallback((content: string) => {
    activeSessionRef.current = 'code'
    _sendCodeMessage(content)
  }, [_sendCodeMessage])
  const [mode, setMode] = useState<AppMode>('chat')

  // ── Estado de mensagens — chat e coder têm históricos separados ─────────
  const [messages,     setMessages]     = useState<Message[]>([])
  const [codeMessages, setCodeMessages] = useState<Message[]>([])
  // Qual sessão está recebendo tokens agora ('chat' | 'code')
  const activeSessionRef = useRef<'chat' | 'code'>('chat')
  const streamingIdRef   = useRef<string | null>(null)

  const addMsg = useCallback((msg: Message) => {
    if (activeSessionRef.current === 'code') {
      setCodeMessages(p => [...p, msg])
    } else {
      setMessages(p => [...p, msg])
    }
  }, [])

  const addChatMsg = useCallback((msg: Message) => {
    setMessages(p => [...p, msg])
  }, [])

  const addCodeMsg = useCallback((msg: Message) => {
    setCodeMessages(p => [...p, msg])
  }, [])

  const appendToken = useCallback((id: string, token: string) => {
    const setter = activeSessionRef.current === 'code' ? setCodeMessages : setMessages
    setter(p => p.map(m => m.id === id ? { ...m, content: m.content + token } : m))
  }, [])

  const finalizeMsg = useCallback((id: string, emotion?: string) => {
    const setter = activeSessionRef.current === 'code' ? setCodeMessages : setMessages
    setter(p => p.map(m =>
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
            isProactive: Boolean(m.is_proactive),
          })))
        }
        // Sem mensagem de saudação — histórico fala por si
        return
      }
      if (ev.type === 'transcription' && ev.content) {
        // Transcrições de voz sempre vão para o chat
        setMessages(p => [...p, { id: `user-${Date.now()}`, role: 'user', content: ev.content!, timestamp: new Date() }])
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
          const setter = activeSessionRef.current === 'code' ? setCodeMessages : setMessages
          setter(p => p.map(m =>
            m.id === id
              ? { ...m, content: ev.content ?? m.content, isStreaming: false, emotion: ev.emotion as never }
              : m
          ))
        }
        if (ev.audio) playAudioBase64(ev.audio)
        // Envia a mensagem para o speech bubble da janela float
        if (ev.content) {
          ;(async () => {
            try {
              const { emit } = await import('@tauri-apps/api/event')
              await emit('krirk-update', { message: ev.content })
            } catch { /* browser dev */ }
          })()
        }
        return
      }
      if (ev.type === 'proactive_comment' && ev.content) {
        // Comentários proativos sempre no chat
        addChatMsg({
          id: `proactive-${Date.now()}`,
          role: 'assistant',
          content: ev.content,
          emotion: ev.emotion,
          timestamp: new Date(),
          isProactive: true,
        })
        if (ev.audio) playAudioBase64(ev.audio)
        // Notificação nativa Windows quando janela está oculta na bandeja
        ;(async () => {
          try {
            const { invoke } = await import('@tauri-apps/api/core')
            const visible = await invoke<boolean>('is_window_visible')
            if (!visible) {
              const { sendNotification } = await import('@tauri-apps/plugin-notification')
              sendNotification({ title: 'Krirk', body: ev.content!.slice(0, 100) })
            }
          } catch { /* browser dev mode — ignora */ }
        })()
        return
      }
      if (ev.type === 'tool_call' && ev.tool) {
        // Tool calls seguem a sessão ativa
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
        const setter = activeSessionRef.current === 'code' ? setCodeMessages : setMessages
        setter(p => {
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
        // Screenshots sempre no chat
        setMessages(p => [...p, {
          id: `screenshot-${Date.now()}`,
          role: 'assistant',
          content: '',
          thumbnail: `data:image/jpeg;base64,${ev.thumbnail}`,
          timestamp: new Date(),
        }])
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

  // ── Sincroniza emoção/estado com a janela float independente ──────────────
  useEffect(() => {
    (async () => {
      try {
        const { emit } = await import('@tauri-apps/api/event')
        await emit('krirk-update', { emotion, aiState })
      } catch { /* browser dev */ }
    })()
  }, [emotion, aiState])

  // ── Modo & janela ──────────────────────────────────────────────────────────
  const aiStateBusy = aiState !== 'idle'

  useEffect(() => { adjustWindow(mode) }, [mode])

  const handleSetMode    = useCallback((m: AppMode) => setMode(m), [])
  const handleOpenSettings = useCallback(() => openSettingsWindow(), [])
  const handleBackToChat = useCallback(() => setMode('chat'), [])

  const handleDetachAvatar = useCallback(async () => {
    try {
      const { invoke } = await import('@tauri-apps/api/core')
      await invoke('open_avatar_float')
    } catch { /* browser dev */ }
    setMode('chat')
  }, [])

  // ── Modo Avatar — janela transparente, apenas a personagem ──────────────
  if (mode === 'avatar') {
    return (
      <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: 'transparent', overflow: 'hidden' }}>
        <AvatarMode
          emotion={emotion}
          aiState={aiState}
          onEvent={onEvent}
          onBack={handleBackToChat}
          onDetach={handleDetachAvatar}
        />
      </div>
    )
  }

  // ── Modo Sidebar (compacto) ───────────────────────────────────────────────
  if (mode === 'sidebar') {
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
        <HudMode
          messages={messages}
          addMsg={addMsg}
          emotion={emotion}
          aiState={aiState}
          connected={connected}
          aiStateBusy={aiStateBusy}
          sendMessage={sendMessage}
          sendAudio={sendAudio}
          sendScreenshot={sendScreenshot}
          sendImageMessage={sendImageMessage}
        />
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
        {mode === 'code' ? (
          <CodeMode
            messages={codeMessages}
            addMsg={addCodeMsg}
            sendCodeMessage={sendCodeMessage}
            connected={connected}
            aiStateBusy={aiStateBusy}
          />
        ) : (
          <ChatMode
            messages={messages}
            addMsg={addChatMsg}
            sendMessage={sendMessage}
            sendAudio={sendAudio}
            sendScreenshot={sendScreenshot}
            sendImageMessage={sendImageMessage}
            connected={connected}
            aiStateBusy={aiStateBusy}
          />
        )}
      </main>
    </div>
  )
}
