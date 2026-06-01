import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Message, WSEvent } from '../types'
import { MessageBubble } from './MessageBubble'
import { VoiceButton } from './VoiceButton'

interface Props {
  sendMessage: (content: string) => void
  sendAudio: (base64: string) => void
  onEvent: (handler: (e: WSEvent) => void) => () => void
  connected: boolean
  aiStateBusy: boolean
}

function playAudio(b64: string) {
  try {
    const binary = atob(b64)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
    const blob = new Blob([bytes], { type: 'audio/mpeg' })
    const url = URL.createObjectURL(blob)
    const audio = new Audio(url)
    audio.play().catch(() => {})
    audio.onended = () => URL.revokeObjectURL(url)
  } catch {
    // silence errors
  }
}

export function ChatWindow({ sendMessage, sendAudio, onEvent, connected, aiStateBusy }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [streamingId, setStreamingId] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const addMessage = useCallback((msg: Message) => {
    setMessages((prev) => [...prev, msg])
  }, [])

  const appendToken = useCallback((id: string, token: string) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.id === id ? { ...m, content: m.content + token } : m
      )
    )
  }, [])

  const finalizeStreaming = useCallback((id: string, emotion?: string) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.id === id ? { ...m, isStreaming: false, emotion: emotion as any } : m
      )
    )
    setStreamingId(null)
  }, [])

  useEffect(() => {
    const streamingMsgId = `ai-${Date.now()}`

    const unsub = onEvent((event: WSEvent) => {
      if (event.type === 'connected' && event.message) {
        addMessage({
          id: `ai-${Date.now()}`,
          role: 'assistant',
          content: event.message,
          timestamp: new Date(),
        })
        return
      }

      if (event.type === 'transcription' && event.content) {
        addMessage({
          id: `user-${Date.now()}`,
          role: 'user',
          content: event.content,
          timestamp: new Date(),
        })
        return
      }

      if (event.type === 'token' && event.content) {
        if (!streamingId) {
          const newId = `ai-${Date.now()}`
          setStreamingId(newId)
          addMessage({
            id: newId,
            role: 'assistant',
            content: event.content,
            timestamp: new Date(),
            isStreaming: true,
          })
        } else {
          appendToken(streamingId, event.content)
        }
      }

      if (event.type === 'response_complete') {
        if (streamingId) {
          finalizeStreaming(streamingId, event.emotion)
        }
        if (event.audio) {
          playAudio(event.audio)
        }
      }
    })

    return unsub
  }, [onEvent, addMessage, appendToken, finalizeStreaming, streamingId])

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
        <VoiceButton onAudio={sendAudio} disabled={!connected || aiStateBusy} />
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={connected ? 'Escreva para a Krirk...' : 'Conectando...'}
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
