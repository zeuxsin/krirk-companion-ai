export type EmotionType =
  | 'neutro'
  | 'surpresa'
  | 'pensando'
  | 'curiosa'
  | 'cansada'
  | 'irritada'
  | 'confusa'
  | 'feliz'
  | 'empolgada'
  | 'triste'
  | 'zangada'
  | 'assustada'
  | 'envergonhada'
  | 'timida'
  | 'concentrada'
  | 'orgulhosa'
  | 'determinada'
  | 'codando'
  | 'jogando'
  | 'tranquila'

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
  history?: { role: string; content: string; is_proactive?: number }[]  // histórico do chat ao conectar
  code_history?: { role: string; content: string; is_proactive?: number }[]  // histórico do Modo Coder ao conectar
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
  proposal?: {          // evento consent_request — auto-modificação encenada
    id: number
    kind: string
    rationale: string
  }
}

export interface ConsentProposal {
  id: number
  kind: string
  rationale: string
}
