import React, { useState, useRef, useCallback } from 'react'

interface Props {
  onTranscript: (text: string) => void
  disabled?: boolean
}

// Tipagem da Web Speech API (não está no lib padrão do TS)
declare global {
  interface Window {
    SpeechRecognition: typeof SpeechRecognition
    webkitSpeechRecognition: typeof SpeechRecognition
  }
}

export function VoiceButton({ onTranscript, disabled }: Props) {
  const [listening, setListening] = useState(false)
  const recognitionRef = useRef<SpeechRecognition | null>(null)

  const toggle = useCallback(() => {
    if (listening) {
      recognitionRef.current?.stop()
      setListening(false)
      return
    }

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) {
      alert('Reconhecimento de voz não suportado.\nUse Chrome ou Edge para esta função.')
      return
    }

    const recognition = new SR()
    recognition.lang = 'pt-BR'
    recognition.continuous = false
    recognition.interimResults = false
    recognition.maxAlternatives = 1

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript.trim()
      if (transcript) onTranscript(transcript)
    }

    recognition.onerror = (event) => {
      console.warn('[STT]', event.error)
      setListening(false)
    }

    recognition.onend = () => setListening(false)

    recognitionRef.current = recognition
    recognition.start()
    setListening(true)
  }, [listening, onTranscript])

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
