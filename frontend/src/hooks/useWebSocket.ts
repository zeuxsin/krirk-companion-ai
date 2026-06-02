import { useEffect, useRef, useCallback, useState } from 'react'
import { WSEvent, AIState, EmotionType } from '../types'

const WS_URL = `ws://${window.location.hostname}:8000/ws`

interface UseWebSocketReturn {
  connected: boolean
  aiState: AIState
  emotion: EmotionType
  sendMessage: (content: string) => void
  sendAudio: (base64: string) => void
  sendScreenshot: (prompt: string) => void
  onEvent: (handler: (event: WSEvent) => void) => () => void
}

export function useWebSocket(): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)
  const [aiState, setAiState] = useState<AIState>('idle')
  const [emotion, setEmotion] = useState<EmotionType>('neutral')
  const handlersRef = useRef<Set<(e: WSEvent) => void>>(new Set())
  const reconnectTimer = useRef<number | undefined>(undefined)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      clearTimeout(reconnectTimer.current)
    }

    ws.onclose = () => {
      setConnected(false)
      setAiState('idle')
      reconnectTimer.current = window.setTimeout(connect, 3000)
    }

    ws.onerror = () => ws.close()

    ws.onmessage = (e) => {
      try {
        const event: WSEvent = JSON.parse(e.data)

        if (event.type === 'status' && event.state) {
          setAiState(event.state)
        }

        // Erros sempre resetam para idle
        if (event.type === 'error') {
          setAiState('idle')
        }

        if (event.emotion) {
          setEmotion(event.emotion)
        }

        if (event.type === 'response_complete') {
          if (event.emotion) setEmotion(event.emotion)
          setAiState('idle')
        }

        handlersRef.current.forEach((h) => h(event))
      } catch {
        // ignore parse errors
      }
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  const sendMessage = useCallback((content: string) => {
    wsRef.current?.send(JSON.stringify({ type: 'chat', content }))
  }, [])

  const sendAudio = useCallback((base64: string) => {
    wsRef.current?.send(JSON.stringify({ type: 'audio', data: base64 }))
  }, [])

  const sendScreenshot = useCallback((prompt: string) => {
    wsRef.current?.send(JSON.stringify({ type: 'screenshot', prompt }))
  }, [])

  const onEvent = useCallback((handler: (e: WSEvent) => void) => {
    handlersRef.current.add(handler)
    return () => handlersRef.current.delete(handler)
  }, [])

  return { connected, aiState, emotion, sendMessage, sendAudio, sendScreenshot, onEvent }
}
