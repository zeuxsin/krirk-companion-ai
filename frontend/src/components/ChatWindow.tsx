import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Message, WSEvent } from '../types'
import { MessageBubble } from './MessageBubble'
import { VoiceButton } from './VoiceButton'

interface Props {
  sendMessage: (content: string) => void
  onEvent: (handler: (e: WSEvent) => void) => () => void
  connected: boolean
  aiStateBusy: boolean
}

// Reproduz áudio MP3 base64 usando AudioContext — mais confiável que new Audio()
async function playAudioBase64(b64: string): Promise<void> {
  try {
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))
    const ctx = new AudioContext()
    // Resume o contexto caso esteja suspenso pela política de autoplay
    if (ctx.state === 'suspended') await ctx.resume()
    const buffer = await ctx.decodeAudioData(bytes.buffer)
    const source = ctx.createBufferSource()
    source.buffer = buffer
    source.connect(ctx.destination)
    source.start(0)
    source.onended = () => ctx.close()
  } catch (e) {
    console.warn('[TTS] Playback failed:', e)
  }
}

export function ChatWindow({ sendMessage, onEvent, connected, aiStateBusy }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Ref em vez de state — evita stale closure dentro do useEffect
  const streamingIdRef = useRef<string | null>(null)

  const addMessage = useCallback((msg: Message) => {
    setMessages((prev) => [...prev, msg])
  }, [])

  const appendToken = useCallback((id: string, token: string) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, content: m.content + token } : m))
    )
  }, [])

  const finalizeMessage = useCallback((id: string, emotion?: string) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.id === id ? { ...m, isStreaming: false, emotion: emotion as never } : m
      )
    )
  }, [])

  // Efeito registrado UMA vez — lê streamingIdRef (sempre fresco) sem precisar de deps
  useEffect(() => {
    const unsub = onEvent((event: WSEvent) => {
      // Mensagem de boas-vindas ao conectar
      if (event.type === 'connected' && event.message) {
        addMessage({
          id: `ai-${Date.now()}`,
          role: 'assistant',
          content: event.message,
          timestamp: new Date(),
        })
        return
      }

      // Transcrição de voz chegou (fallback de STT no backend)
      if (event.type === 'transcription' && event.content) {
        addMessage({
          id: `user-${Date.now()}`,
          role: 'user',
          content: event.content,
          timestamp: new Date(),
        })
        return
      }

      // Token de streaming
      if (event.type === 'token' && event.content) {
        if (!streamingIdRef.current) {
          const newId = `ai-${Date.now()}`
          streamingIdRef.current = newId
          addMessage({
            id: newId,
            role: 'assistant',
            content: event.content,
            timestamp: new Date(),
            isStreaming: true,
          })
        } else {
          appendToken(streamingIdRef.current, event.content)
        }
        return
      }

      // Resposta completa — finaliza streaming e toca áudio
      if (event.type === 'response_complete') {
        if (streamingIdRef.current) {
          finalizeMessage(streamingIdRef.current, event.emotion)
          streamingIdRef.current = null
        }
        if (event.audio) {
          playAudioBase64(event.audio)
        }
        return
      }

      // Erro do backend — mostra como mensagem do sistema
      if (event.type === 'error' && event.message) {
        // Finaliza streaming pendente se houver
        if (streamingIdRef.current) {
          finalizeMessage(streamingIdRef.current)
          streamingIdRef.current = null
        }
        addMessage({
          id: `err-${Date.now()}`,
          role: 'assistant',
          content: `⚠️ ${event.message}`,
          timestamp: new Date(),
        })
      }
    })

    return unsub
    // Deps estáveis — onEvent/addMessage/appendToken/finalizeMessage não mudam
  }, [onEvent, addMessage, appendToken, finalizeMessage])

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const submit = useCallback(() => {
    const text = input.trim()
    if (!text || !connected || aiStateBusy) return
    addMessage({
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date(),
    })
    sendMessage(text)
    setInput('')
    inputRef.current?.focus()
  }, [input, connected, aiStateBusy, addMessage, sendMessage])

  // Voz: transcrição já chega como texto, envia direto
  const handleTranscript = useCallback((text: string) => {
    addMessage({
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date(),
    })
    sendMessage(text)
  }, [addMessage, sendMessage])

  // Erros do VoiceButton exibidos como mensagem de sistema
  const handleVoiceError = useCallback((msg: string) => {
    addMessage({
      id: `err-${Date.now()}`,
      role: 'assistant',
      content: msg,
      timestamp: new Date(),
    })
  }, [addMessage])

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
      {/* Messages */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
      }}>
        {messages.length === 0 && (
          <div style={{
            margin: 'auto',
            textAlign: 'center',
            color: '#52525b',
            fontSize: '14px',
          }}>
            <div style={{ fontSize: '48px', marginBottom: '12px' }}>✨</div>
            <div>Conectando à Krirk...</div>
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{
        padding: '12px 16px',
        borderTop: '1px solid #27272a',
        display: 'flex',
        gap: '8px',
        alignItems: 'center',
        background: '#18181b',
      }}>
        <VoiceButton
          onTranscript={handleTranscript}
          onError={handleVoiceError}
          disabled={!connected || aiStateBusy}
        />
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={connected ? 'Escreva para a Krirk...' : 'Reconectando...'}
          disabled={!connected || aiStateBusy}
          style={{
            flex: 1,
            padding: '10px 14px',
            borderRadius: '20px',
            border: '1px solid #3f3f46',
            background: '#27272a',
            color: '#e4e4e7',
            fontSize: '14px',
            outline: 'none',
          }}
        />
        <button
          onClick={submit}
          disabled={!connected || aiStateBusy || !input.trim()}
          style={{
            width: 40,
            height: 40,
            borderRadius: '50%',
            border: 'none',
            background: input.trim() && connected && !aiStateBusy ? '#7c3aed' : '#3f3f46',
            color: '#e4e4e7',
            cursor: 'pointer',
            fontSize: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            transition: 'background 0.15s',
          }}
        >
          ↑
        </button>
      </div>
    </div>
  )
}
