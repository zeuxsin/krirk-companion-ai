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
}

export interface WSEvent {
  type: string
  content?: string
  emotion?: EmotionType
  state?: AIState
  message?: string
  audio?: string
  status?: {
    state: AIState
    emotion: EmotionType
    model: string
    tts_enabled: boolean
    stt_enabled: boolean
  }
}
