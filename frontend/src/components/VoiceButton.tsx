import React, { useState, useRef, useCallback } from 'react'

interface Props {
  onTranscript: (text: string) => void
  onError?: (msg: string) => void
  disabled?: boolean
}

declare global {
  interface Window {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    webkitSpeechRecognition: any
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    SpeechRecognition: any
  }
}

const ERROR_MESSAGES: Record<string, string> = {
  'not-allowed':
    '🎙️ Permissão de microfone negada. Clique no ícone de cadeado na barra do navegador e permita o microfone.',
  'service-not-allowed':
    '🚫 Seu navegador bloqueou o serviço de voz. Se usar Brave: vá em Configurações → Privacidade → desative "Block fingerprinting". Se usar outro navegador, tente Chrome ou Edge.',
  'network':
    '🌐 Erro de rede na API de voz. Verifique sua conexão — a Web Speech API precisa de internet.',
  'audio-capture':
    '🎙️ Microfone não encontrado ou ocupado por outro app.',
  'no-speech':
    '🔇 Nenhuma fala detectada. Tente falar mais perto do microfone.',
  'language-not-supported':
    '🌍 Idioma pt-BR não suportado neste navegador.',
  'aborted': '', // silencioso — usuário cancelou
}

export function VoiceButton({ onTranscript, onError, disabled }: Props) {
  const [listening, setListening] = useState(false)
  const recognitionRef = useRef<InstanceType<typeof window.SpeechRecognition> | null>(null)

  const stop = useCallback(() => {
    recognitionRef.current?.stop()
    setListening(false)
  }, [])

  const toggle = useCallback(() => {
    if (listening) {
      stop()
      return
    }

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) {
      onError?.(
        '❌ Web Speech API não disponível neste navegador. Use Google Chrome ou Microsoft Edge para usar voz.'
      )
      return
    }

    const recognition = new SR()
    recognition.lang = 'pt-BR'
    recognition.continuous = false
    recognition.interimResults = false
    recognition.maxAlternatives = 1

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const transcript = event.results[0][0].transcript.trim()
      if (transcript) onTranscript(transcript)
    }

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      const msg = ERROR_MESSAGES[event.error]
      // string vazia = silencioso (aborted), undefined = erro desconhecido
      if (msg === undefined) {
        onError?.(`⚠️ Erro de voz: ${event.error}`)
      } else if (msg) {
        onError?.(msg)
      }
      setListening(false)
    }

    recognition.onend = () => setListening(false)

    recognitionRef.current = recognition
    try {
      recognition.start()
      setListening(true)
    } catch (e) {
      onError?.(`⚠️ Não foi possível iniciar o reconhecimento de voz: ${e}`)
    }
  }, [listening, stop, onTranscript, onError])

  return (
    <button
      onClick={toggle}
      disabled={disabled}
      title={listening ? 'Clique para parar' : 'Clique para falar (pt-BR)'}
      style={{
        width: 40,
        height: 40,
        borderRadius: '50%',
        border: 'none',
        background: listening ? '#ef4444' : '#3f3f46',
        color: '#e4e4e7',
        cursor: disabled ? 'not-allowed' : 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: '18px',
        transition: 'background 0.15s',
        flexShrink: 0,
        boxShadow: listening ? '0 0 0 4px rgba(239,68,68,0.3)' : 'none',
        opacity: disabled ? 0.5 : 1,
      }}
    >
      {listening ? '⏹' : '🎙️'}
    </button>
  )
}
