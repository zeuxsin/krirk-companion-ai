import React, { useState, useRef, useCallback } from 'react'

interface Props {
  onAudio: (base64: string) => void
  disabled?: boolean
}

export function VoiceButton({ onAudio, disabled }: Props) {
  const [recording, setRecording] = useState(false)
  const mediaRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  const start = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      mediaRef.current = recorder
      chunksRef.current = []

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        const buffer = await blob.arrayBuffer()
        const b64 = btoa(String.fromCharCode(...new Uint8Array(buffer)))
        onAudio(b64)
        stream.getTracks().forEach((t) => t.stop())
      }

      recorder.start()
      setRecording(true)
    } catch (err) {
      alert('Microfone não disponível: ' + err)
    }
  }, [onAudio])

  const stop = useCallback(() => {
    mediaRef.current?.stop()
    setRecording(false)
  }, [])

  return (
    <button
      onMouseDown={start}
      onMouseUp={stop}
      onMouseLeave={stop}
      onTouchStart={start}
      onTouchEnd={stop}
      disabled={disabled}
      title="Segure para falar"
      style={{
        width: 40,
        height: 40,
        borderRadius: '50%',
        border: 'none',
        background: recording ? '#ef4444' : '#3f3f46',
        color: '#e4e4e7',
        cursor: disabled ? 'not-allowed' : 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: '18px',
        transition: 'background 0.15s',
        flexShrink: 0,
        boxShadow: recording ? '0 0 0 4px rgba(239,68,68,0.3)' : 'none',
      }}
    >
      {recording ? '⏹' : '🎙️'}
    </button>
  )
}
