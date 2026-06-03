export type EmotionType =
  | 'neutral'
  | 'happy'
  | 'curious'
  | 'thoughtful'
  | 'excited'
  | 'concerned'
  | 'playful'
  | 'angry'
  | 'confused'

export type AIState = 'idle' | 'thinking' | 'speaking' | 'listening' | 'executing'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  emotion?: EmotionType
  timestamp: Date
  isStreaming?: boolean
  thumbnail?: string  // base64 JPEG de screenshot para exibir no chat
}

export interface WSEvent {
  type: string
  content?: string
  emotion?: EmotionType
  state?: AIState
  message?: string
  audio?: string
  thumbnail?: string  // base64 JPEG (evento screenshot_taken)
  history?: { role: string; content: string }[]  // histórico de mensagens ao conectar
  status?: {
    state: AIState
    emotion: EmotionType
    model: string
    tts_enabled: boolean
    stt_enabled: boolean
  }
}
