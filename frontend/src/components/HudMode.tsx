import { useState, useEffect, useRef, useCallback } from 'react'
import { Camera, Paperclip, Send } from 'lucide-react'
import { EmotionType, AIState, Message } from '../types'
import { VoiceButton } from './VoiceButton'
import { EMOTION_COLOR, avatarAnimClass, avatarSrc, avatarFallback } from '../utils/emotions'

interface Props {
  messages: Message[]
  addMsg: (msg: Message) => void
  emotion: EmotionType
  aiState: AIState
  connected: boolean
  aiStateBusy: boolean
  sendMessage: (text: string) => void
  sendAudio?: (b64Wav: string) => void
  sendScreenshot?: (prompt: string) => void
  sendImageMessage?: (b64: string) => void
}

export function HudMode({
  messages, addMsg, emotion, aiState, connected, aiStateBusy,
  sendMessage, sendAudio, sendScreenshot, sendImageMessage,
}: Props) {
  const [imgSrc, setImgSrc] = useState(avatarSrc(emotion))
  const [imgOpacity, setImgOpacity] = useState(1)
  const [input, setInput] = useState('')
  const prevEmotion = useRef(emotion)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Fade na troca de emoção
  useEffect(() => {
    if (emotion === prevEmotion.current) return
    prevEmotion.current = emotion
    setImgOpacity(0)
    const t = setTimeout(() => {
      setImgSrc(avatarSrc(emotion))
      setImgOpacity(1)
    }, 150)
    return () => clearTimeout(t)
  }, [emotion])

  const handleImgError = useCallback(() => {
    setImgSrc(src => src.endsWith('.png') ? avatarFallback(emotion) : src)
  }, [emotion])

  const submit = useCallback(() => {
    const text = input.trim()
    if (!text || !connected || aiStateBusy) return
    addMsg({ id: `user-${Date.now()}`, role: 'user', content: text, timestamp: new Date() })
    sendMessage(text)
    setInput('')
  }, [input, connected, aiStateBusy, addMsg, sendMessage])

  const handleScreenshot = useCallback(() => {
    if (!connected || aiStateBusy || !sendScreenshot) return
    addMsg({ id: `user-${Date.now()}`, role: 'user', content: 'Analisando minha tela...', timestamp: new Date() })
    sendScreenshot('Descreva o que você vê na minha tela. Seja específica e útil.')
  }, [connected, aiStateBusy, addMsg, sendScreenshot])

  const handleImageUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !connected || aiStateBusy) return
    const reader = new FileReader()
    reader.onload = () => {
      const b64 = (reader.result as string).split(',')[1]
      const thumbUrl = reader.result as string
      addMsg({ id: `user-${Date.now()}`, role: 'user', content: '', thumbnail: thumbUrl, timestamp: new Date() })
      sendImageMessage?.(b64)
    }
    reader.readAsDataURL(file)
    e.target.value = ''
  }, [connected, aiStateBusy, addMsg, sendImageMessage])

  const iconBtn = (enabled: boolean) => ({
    width: 28, height: 28, borderRadius: 6, border: 'none',
    background: 'var(--color-krirk-surface)',
    color: enabled ? 'var(--color-krirk-text)' : 'var(--color-krirk-muted)',
    cursor: enabled ? 'pointer' : 'not-allowed',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    flexShrink: 0, transition: 'background 0.15s',
  } as React.CSSProperties)

  // Mostra só as últimas 4 mensagens no modo compacto
  const lastMsgs = messages.slice(-4)

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

      {/* Avatar centralizado */}
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        padding: '12px 8px 8px',
        background: 'var(--color-krirk-bg)',
        borderBottom: '1px solid var(--color-krirk-border)',
      }}>
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{
            position: 'absolute',
            width: 130, height: 130,
            borderRadius: '50%',
            background: `radial-gradient(circle, ${EMOTION_COLOR[emotion]}18 0%, transparent 65%)`,
            boxShadow: `0 0 30px 6px ${EMOTION_COLOR[emotion]}28`,
            transition: 'background 0.6s ease, box-shadow 0.6s ease',
            pointerEvents: 'none',
          }} />
          <img
            src={imgSrc}
            onError={handleImgError}
            className={avatarAnimClass(aiState, emotion)}
            alt={emotion}
            style={{
              width: 120,
              position: 'relative', zIndex: 1,
              opacity: imgOpacity,
              transition: 'opacity 0.15s',
              pointerEvents: 'none',
              filter: aiState === 'speaking'
                ? `drop-shadow(0 0 10px ${EMOTION_COLOR[emotion]}88)` : 'none',
            }}
          />
        </div>
        <div style={{
          marginTop: 4, fontSize: 9, fontWeight: 700,
          letterSpacing: '0.14em', textTransform: 'uppercase',
          color: EMOTION_COLOR[emotion],
          transition: 'color 0.4s ease',
        }}>
          {emotion}
        </div>
      </div>

      {/* Últimas 4 mensagens */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '8px 10px',
        display: 'flex', flexDirection: 'column', gap: 6,
      }}>
        {lastMsgs.length === 0 ? (
          <div style={{
            color: 'var(--color-krirk-muted)', fontSize: 11,
            textAlign: 'center', margin: 'auto',
          }}>
            Diz alguma coisa...
          </div>
        ) : lastMsgs.map(m => (
          <div key={m.id} style={{
            display: 'flex',
            justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start',
          }}>
            <div style={{
              maxWidth: '85%', padding: '5px 9px', fontSize: 11,
              borderRadius: m.role === 'user' ? '11px 11px 3px 11px' : '11px 11px 11px 3px',
              background: m.role === 'user'
                ? 'var(--color-krirk-accent)'
                : 'rgba(255,255,255,0.06)',
              border: m.role !== 'user' ? '1px solid var(--color-krirk-border)' : 'none',
              color: 'var(--color-krirk-text)',
              lineHeight: 1.5,
            }}>
              {m.content || (m.thumbnail ? '[imagem]' : '')}
              {m.isStreaming && (
                <span style={{
                  display: 'inline-block', width: 5, height: 10,
                  background: '#a78bfa', marginLeft: 2, borderRadius: 2,
                  animation: 'blink 0.7s infinite', verticalAlign: 'text-bottom',
                }} />
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Input em duas linhas */}
      <div style={{
        padding: '7px 8px 6px',
        borderTop: '1px solid var(--color-krirk-border)',
        background: 'var(--color-krirk-sidebar)',
        display: 'flex', flexDirection: 'column', gap: 5,
      }}>
        {/* Linha 1: ações */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          {sendAudio && (
            <VoiceButton
              sendAudio={sendAudio}
              onError={(msg) => addMsg({ id: `err-${Date.now()}`, role: 'assistant', content: msg, timestamp: new Date() })}
              disabled={!connected || aiStateBusy}
            />
          )}

          <button
            onClick={handleScreenshot}
            disabled={!connected || aiStateBusy || !sendScreenshot}
            title="Analisar tela"
            style={iconBtn(connected && !aiStateBusy && !!sendScreenshot)}
          >
            <Camera size={14} />
          </button>

          {/* Upload de imagem */}
          <input ref={fileInputRef} type="file" accept="image/*" hidden onChange={handleImageUpload} />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={!connected || aiStateBusy || !sendImageMessage}
            title="Enviar imagem"
            style={iconBtn(connected && !aiStateBusy && !!sendImageMessage)}
          >
            <Paperclip size={14} />
          </button>

          <div style={{ flex: 1 }} />

          <button
            onClick={submit}
            disabled={!connected || aiStateBusy || !input.trim()}
            title="Enviar"
            style={{
              ...iconBtn(!!input.trim() && connected && !aiStateBusy),
              background: input.trim() && connected && !aiStateBusy
                ? 'var(--color-krirk-accent)' : 'var(--color-krirk-surface)',
              color: '#fff',
            }}
          >
            <Send size={14} />
          </button>
        </div>

        {/* Linha 2: input de texto */}
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), submit())}
          placeholder="Digite uma mensagem..."
          disabled={!connected || aiStateBusy}
          style={{
            width: '100%', padding: '6px 9px', borderRadius: 7,
            border: '1px solid var(--color-krirk-border)',
            background: 'var(--color-krirk-surface)',
            color: 'var(--color-krirk-text)',
            fontSize: 11, outline: 'none', boxSizing: 'border-box',
          }}
        />
      </div>
    </div>
  )
}
