import React, { useState, useRef, useCallback } from 'react'

interface Props {
  sendAudio: (b64Wav: string) => void
  onError?: (msg: string) => void
  disabled?: boolean
}

// ── WAV encoder ───────────────────────────────────────────────────────────────
// Converte Float32Array (PCM normalizado) em ArrayBuffer WAV 16-bit mono.
// Não requer ffmpeg nem dependências externas.

function writeString(view: DataView, offset: number, str: string) {
  for (let i = 0; i < str.length; i++) {
    view.setUint8(offset + i, str.charCodeAt(i))
  }
}

function encodeWav(samples: Float32Array, sampleRate: number): ArrayBuffer {
  const numSamples = samples.length
  const buffer = new ArrayBuffer(44 + numSamples * 2)
  const view = new DataView(buffer)

  // RIFF chunk
  writeString(view, 0, 'RIFF')
  view.setUint32(4, 36 + numSamples * 2, true)
  writeString(view, 8, 'WAVE')
  // fmt sub-chunk
  writeString(view, 12, 'fmt ')
  view.setUint32(16, 16, true)            // chunk size
  view.setUint16(20, 1, true)             // PCM format
  view.setUint16(22, 1, true)             // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true) // byte rate
  view.setUint16(32, 2, true)             // block align
  view.setUint16(34, 16, true)            // bits per sample
  // data sub-chunk
  writeString(view, 36, 'data')
  view.setUint32(40, numSamples * 2, true)

  // Float32 → Int16
  for (let i = 0; i < numSamples; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }
  return buffer
}

function arrayBufferToBase64(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf)
  let bin = ''
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i])
  return btoa(bin)
}

// ── Componente ─────────────────────────────────────────────────────────────────

type BtnState = 'idle' | 'recording' | 'processing'

export function VoiceButton({ sendAudio, onError, disabled }: Props) {
  const [btnState, setBtnState] = useState<BtnState>('idle')
  const audioCtxRef   = useRef<AudioContext | null>(null)
  const processorRef  = useRef<ScriptProcessorNode | null>(null)
  const streamRef     = useRef<MediaStream | null>(null)
  const chunksRef     = useRef<Float32Array[]>([])

  const stopRecording = useCallback(() => {
    processorRef.current?.disconnect()
    processorRef.current = null
    audioCtxRef.current?.close()
    audioCtxRef.current = null
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null
  }, [])

  const handleStop = useCallback(() => {
    const chunks = chunksRef.current
    chunksRef.current = []
    stopRecording()

    if (chunks.length === 0) {
      setBtnState('idle')
      return
    }

    setBtnState('processing')

    // Concatena todos os chunks em um único Float32Array
    const total = chunks.reduce((acc, c) => acc + c.length, 0)
    const merged = new Float32Array(total)
    let offset = 0
    for (const chunk of chunks) {
      merged.set(chunk, offset)
      offset += chunk.length
    }

    const SAMPLE_RATE = 16000
    const wav = encodeWav(merged, SAMPLE_RATE)
    const b64 = arrayBufferToBase64(wav)
    sendAudio(b64)

    // O backend sinaliza LISTENING via aiState → button fica disabled.
    // Resetamos para idle logo após enviar (disabled vai assumir o controle).
    setBtnState('idle')
  }, [sendAudio, stopRecording])

  const handleStart = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
      streamRef.current = stream

      // Whisper funciona bem a 16 kHz mono — pedimos direto ao AudioContext
      const ctx = new AudioContext({ sampleRate: 16000 })
      audioCtxRef.current = ctx

      const source = ctx.createMediaStreamSource(stream)
      // ScriptProcessor é deprecated mas funciona no WebView2/Chromium
      const processor = ctx.createScriptProcessor(4096, 1, 1)
      processorRef.current = processor

      chunksRef.current = []

      processor.onaudioprocess = (e) => {
        // Canal 0 (mono) — copia para preservar os dados
        const input = e.inputBuffer.getChannelData(0)
        chunksRef.current.push(new Float32Array(input))
      }

      source.connect(processor)
      processor.connect(ctx.destination) // precisa estar conectado para disparar onaudioprocess

      setBtnState('recording')
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg.includes('Permission denied') || msg.includes('NotAllowedError')) {
        onError?.('🎙️ Permissão de microfone negada. Autorize o microfone e tente novamente.')
      } else if (msg.includes('NotFoundError') || msg.includes('DevicesNotFoundError')) {
        onError?.('🎙️ Nenhum microfone encontrado.')
      } else {
        onError?.(`⚠️ Erro ao acessar microfone: ${msg}`)
      }
      setBtnState('idle')
    }
  }, [onError])

  const toggle = useCallback(() => {
    if (btnState === 'recording') {
      handleStop()
    } else if (btnState === 'idle') {
      handleStart()
    }
    // 'processing' → ignora clique
  }, [btnState, handleStop, handleStart])

  // ── Visual ────────────────────────────────────────────────────────────────

  const icon =
    btnState === 'recording'  ? '⏹' :
    btnState === 'processing' ? '⏳' :
    '🎙️'

  const bg =
    btnState === 'recording'  ? '#ef4444' :
    btnState === 'processing' ? '#7c3aed' :
    '#3f3f46'

  const glow =
    btnState === 'recording'  ? '0 0 0 4px rgba(239,68,68,0.3)'  :
    btnState === 'processing' ? '0 0 0 4px rgba(124,58,237,0.3)' :
    'none'

  const title =
    btnState === 'recording'  ? 'Clique para parar a gravação' :
    btnState === 'processing' ? 'Processando...' :
    'Clique para falar (pt-BR)'

  return (
    <button
      onClick={toggle}
      disabled={disabled || btnState === 'processing'}
      title={title}
      style={{
        width: 40,
        height: 40,
        borderRadius: '50%',
        border: 'none',
        background: bg,
        color: '#e4e4e7',
        cursor: (disabled || btnState === 'processing') ? 'not-allowed' : 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: '18px',
        transition: 'background 0.15s, box-shadow 0.15s',
        flexShrink: 0,
        boxShadow: glow,
        opacity: disabled ? 0.5 : 1,
        animation: btnState === 'recording' ? 'pulse 1.2s ease-in-out infinite' : 'none',
      }}
    >
      {icon}
    </button>
  )
}
