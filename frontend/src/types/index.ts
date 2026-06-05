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
  role: 'user' | 'assistant' | 'tool'
  content: string
  emotion?: EmotionType
  timestamp: Date
  isStreaming?: boolean
  thumbnail?: string    // base64 JPEG de screenshot para exibir no chat
  toolName?: string     // nome da ferramenta (role === 'tool')
  toolResult?: string   // resultado da execução (colapsável)
  isRunning?: boolean   // true enquanto a ferramenta está sendo executada
  isProactive?: boolean // true para comentários espontâneos da Krirk
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
  tool?: string       // nome da ferramenta (eventos tool_call / tool_result)
  raw?: string        // JSON bruto do tool_call
  result?: string     // resultado da execução (tool_result)
  status?: {
    state: AIState
    emotion: EmotionType
    model: string
    tts_enabled: boolean
    stt_enabled: boolean
  }
}
