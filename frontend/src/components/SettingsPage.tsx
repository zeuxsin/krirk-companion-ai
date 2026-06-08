import React, { useState, useEffect, useRef } from 'react'

type SettingsTab = 'models' | 'personality' | 'appearance' | 'hardware'

interface HardwareStats {
  cpu: number
  ram_used: number
  ram_total: number
  ram_percent: number
}

interface Settings {
  tts_enabled: boolean
  tts_voice: string
  stt_enabled: boolean
  ollama_model: string
  temperature: number
  proactive_enabled: boolean
  krirk_name: string
  personality_notes: string
}

const API = 'http://localhost:8000'

async function saveSettings(patch: Partial<Settings>): Promise<boolean> {
  try {
    const r = await fetch(`${API}/api/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    })
    return r.ok
  } catch {
    return false
  }
}

// ── Componentes base ──────────────────────────────────────────────────────────

function ProgressBar({ value, color = '#7c3aed' }: { value: number; color?: string }) {
  const clampedColor = value > 90 ? '#ef4444' : value > 70 ? '#f59e0b' : color
  return (
    <div style={{ position: 'relative', height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
      <div style={{
        position: 'absolute', left: 0, top: 0, height: '100%',
        width: `${Math.min(100, value)}%`,
        background: clampedColor,
        borderRadius: 3,
        transition: 'width 0.4s ease',
      }} />
    </div>
  )
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div
      onClick={() => onChange(!checked)}
      style={{
        width: 40, height: 22, borderRadius: 11, cursor: 'pointer', flexShrink: 0,
        background: checked ? 'var(--color-krirk-accent)' : 'rgba(255,255,255,0.12)',
        position: 'relative', transition: 'background 0.2s',
      }}
    >
      <div style={{
        position: 'absolute', top: 3, width: 16, height: 16, borderRadius: '50%',
        background: '#fff', transition: 'left 0.2s',
        left: checked ? 21 : 3,
        boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
      }} />
    </div>
  )
}

function SaveFeedback({ status }: { status: 'idle' | 'saving' | 'saved' | 'error' }) {
  if (status === 'idle') return null
  const map = {
    saving: { text: 'salvando…', color: 'var(--color-krirk-muted)' },
    saved:  { text: 'salvo ✓',   color: '#34d399' },
    error:  { text: 'erro ✗',    color: '#ef4444' },
  }
  const m = map[status]
  return <span style={{ fontSize: 10, color: m.color }}>{m.text}</span>
}

function ToggleRow({
  label,
  description,
  checked,
  onChange,
  status,
}: {
  label: string
  description: string
  checked: boolean
  onChange: (v: boolean) => void
  status?: 'idle' | 'saving' | 'saved' | 'error'
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
      <div style={{ flex: 1, minWidth: 0, paddingRight: 12 }}>
        <div style={{ fontSize: 12, color: 'var(--color-krirk-text)' }}>{label}</div>
        <div style={{ fontSize: 10, color: 'var(--color-krirk-muted)', marginTop: 2 }}>{description}</div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
        {status && <SaveFeedback status={status} />}
        <Toggle checked={checked} onChange={onChange} />
      </div>
    </div>
  )
}

// ── Aba Hardware ──────────────────────────────────────────────────────────────

function HardwareTab() {
  const [stats, setStats] = useState<HardwareStats | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const r = await fetch(`${API}/api/system`)
        if (r.ok) { setStats(await r.json()); setError(false) }
        else setError(true)
      } catch { setError(true) }
    }
    fetchStats()
    const id = setInterval(fetchStats, 2000)
    return () => clearInterval(id)
  }, [])

  if (error) return (
    <div style={{ color: 'var(--color-krirk-muted)', fontSize: 12, padding: 12 }}>
      ⚠️ Backend offline — inicie o servidor Python
    </div>
  )

  return (
    <div>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--color-krirk-text)' }}>
        Monitor de Hardware
      </h3>
      <p style={{ fontSize: 10, color: 'var(--color-krirk-muted)', marginBottom: 16 }}>
        Atualiza a cada 2 segundos
      </p>

      <div style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-krirk-text)' }}>CPU</span>
          <span style={{ fontSize: 12, color: 'var(--color-krirk-muted)' }}>
            {stats ? `${stats.cpu.toFixed(1)}%` : '—'}
          </span>
        </div>
        <ProgressBar value={stats?.cpu ?? 0} />
      </div>

      <div style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-krirk-text)' }}>RAM</span>
          <span style={{ fontSize: 12, color: 'var(--color-krirk-muted)' }}>
            {stats ? `${stats.ram_used.toFixed(1)} GB / ${stats.ram_total.toFixed(0)} GB` : '—'}
          </span>
        </div>
        <ProgressBar value={stats?.ram_percent ?? 0} color='#34d399' />
      </div>

      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-krirk-text)' }}>GPU</span>
          <span style={{ fontSize: 12, color: 'var(--color-krirk-muted)' }}>via Ollama</span>
        </div>
        <p style={{ fontSize: 10, color: 'var(--color-krirk-muted)' }}>
          Monitoramento de GPU VRAM virá em versão futura.
        </p>
      </div>
    </div>
  )
}

// ── Aba Modelos ───────────────────────────────────────────────────────────────

function ModelsTab() {
  const [model, setModel]                   = useState('gemma3:4b')
  const [temp, setTemp]                     = useState(0.85)
  const [ttsEnabled, setTtsEnabled]         = useState(true)
  const [sttEnabled, setSttEnabled]         = useState(false)
  const [proactiveEnabled, setProactive]    = useState(true)

  const [modelStatus, setModelStatus]       = useState<'idle'|'saving'|'saved'|'error'>('idle')
  const [tempStatus, setTempStatus]         = useState<'idle'|'saving'|'saved'|'error'>('idle')
  const [ttsStatus, setTtsStatus]           = useState<'idle'|'saving'|'saved'|'error'>('idle')
  const [sttStatus, setSttStatus]           = useState<'idle'|'saving'|'saved'|'error'>('idle')
  const [proactiveStatus, setProactiveStatus] = useState<'idle'|'saving'|'saved'|'error'>('idle')

  const tempDebounce = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Carregar todos os valores do backend ao montar
  useEffect(() => {
    fetch(`${API}/api/settings`)
      .then(r => r.json())
      .then((d: Settings) => {
        setModel(d.ollama_model ?? 'gemma3:4b')
        setTemp(d.temperature ?? 0.85)
        setTtsEnabled(d.tts_enabled ?? true)
        setSttEnabled(d.stt_enabled ?? false)
        setProactive(d.proactive_enabled ?? true)
      })
      .catch(() => {})
  }, [])

  // Helpers de feedback
  const feedback = (setter: (s: 'idle'|'saving'|'saved'|'error') => void, ok: boolean) => {
    setter(ok ? 'saved' : 'error')
    setTimeout(() => setter('idle'), 1500)
  }

  // Salvar modelo
  const handleSaveModel = async () => {
    setModelStatus('saving')
    const ok = await saveSettings({ ollama_model: model.trim() })
    feedback(setModelStatus, ok)
  }

  // Salvar temperatura com debounce
  const handleTempChange = (value: number) => {
    setTemp(value)
    if (tempDebounce.current) clearTimeout(tempDebounce.current)
    tempDebounce.current = setTimeout(async () => {
      setTempStatus('saving')
      const ok = await saveSettings({ temperature: value })
      feedback(setTempStatus, ok)
    }, 400)
  }

  // Toggles — salvam imediatamente
  const handleTts = async (value: boolean) => {
    setTtsEnabled(value)
    setTtsStatus('saving')
    const ok = await saveSettings({ tts_enabled: value })
    feedback(setTtsStatus, ok)
  }

  const handleStt = async (value: boolean) => {
    setSttEnabled(value)
    setSttStatus('saving')
    const ok = await saveSettings({ stt_enabled: value })
    feedback(setSttStatus, ok)
  }

  const handleProactive = async (value: boolean) => {
    setProactive(value)
    setProactiveStatus('saving')
    const ok = await saveSettings({ proactive_enabled: value })
    feedback(setProactiveStatus, ok)
  }

  const inputStyle: React.CSSProperties = {
    flex: 1, padding: '7px 10px', borderRadius: 6,
    border: '1px solid var(--color-krirk-border)',
    background: 'var(--color-krirk-surface)',
    color: 'var(--color-krirk-text)', fontSize: 12, outline: 'none',
  }

  const btnStyle: React.CSSProperties = {
    padding: '7px 14px', borderRadius: 6, border: 'none',
    background: 'rgba(99,102,241,0.3)',
    color: '#818cf8', fontSize: 11, fontWeight: 600,
    cursor: 'pointer', flexShrink: 0, whiteSpace: 'nowrap',
  }

  const divider: React.CSSProperties = {
    borderTop: '1px solid var(--color-krirk-border)',
    marginTop: 16, paddingTop: 16,
  }

  return (
    <div>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--color-krirk-text)' }}>
        Modelos
      </h3>

      {/* Modelo Ollama */}
      <div style={{ marginBottom: 4 }}>
        <span style={{ fontSize: 11, color: 'var(--color-krirk-muted)', display: 'block', marginBottom: 6 }}>
          Modelo Ollama
        </span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            value={model}
            onChange={e => setModel(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSaveModel()}
            placeholder="gemma3:4b"
            style={inputStyle}
          />
          <SaveFeedback status={modelStatus} />
          <button onClick={handleSaveModel} style={btnStyle}>
            Salvar
          </button>
        </div>
        <p style={{ fontSize: 10, color: 'var(--color-krirk-muted)', marginTop: 4 }}>
          Ex: gemma3:4b, llama3.2:3b, phi4-mini. Deve estar instalado no Ollama.
        </p>
      </div>

      {/* Temperatura */}
      <div style={{ marginBottom: 4, marginTop: 14 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <span style={{ fontSize: 11, color: 'var(--color-krirk-muted)' }}>
            Temperatura — {temp.toFixed(2)}
          </span>
          <SaveFeedback status={tempStatus} />
        </div>
        <input
          type="range" min="0" max="1" step="0.05"
          value={temp}
          onChange={e => handleTempChange(parseFloat(e.target.value))}
          style={{ width: '100%' }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2 }}>
          <span style={{ fontSize: 9, color: 'var(--color-krirk-muted)' }}>Preciso</span>
          <span style={{ fontSize: 9, color: 'var(--color-krirk-muted)' }}>Criativo</span>
        </div>
      </div>

      {/* Separador — Voz */}
      <div style={divider}>
        <h4 style={{ fontSize: 11, fontWeight: 700, marginBottom: 12, color: 'var(--color-krirk-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Voz
        </h4>

        <ToggleRow
          label="Fala em voz alta (TTS)"
          description={ttsEnabled ? 'Ativado — KRIRK lê as respostas' : 'Desativado — apenas texto'}
          checked={ttsEnabled}
          onChange={handleTts}
          status={ttsStatus}
        />

        <ToggleRow
          label="Reconhecimento de voz (STT)"
          description={sttEnabled ? 'Ativado — Whisper local escuta o microfone' : 'Desativado — apenas texto'}
          checked={sttEnabled}
          onChange={handleStt}
          status={sttStatus}
        />
      </div>

      {/* Separador — Comportamento */}
      <div style={divider}>
        <h4 style={{ fontSize: 11, fontWeight: 700, marginBottom: 12, color: 'var(--color-krirk-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Comportamento
        </h4>

        <ToggleRow
          label="Comentários espontâneos"
          description={proactiveEnabled ? 'Ativado — KRIRK comenta o que vê na tela' : 'Desativado — fala apenas quando acionada'}
          checked={proactiveEnabled}
          onChange={handleProactive}
          status={proactiveStatus}
        />
      </div>
    </div>
  )
}

// ── Aba Personalidade ─────────────────────────────────────────────────────────

function PersonalityTab() {
  const [name, setName]   = useState('Krirk')
  const [notes, setNotes] = useState('')
  const [status, setStatus] = useState<'idle'|'saving'|'saved'|'error'>('idle')

  useEffect(() => {
    fetch(`${API}/api/settings`)
      .then(r => r.json())
      .then((d: Settings) => {
        setName(d.krirk_name ?? 'Krirk')
        setNotes(d.personality_notes ?? '')
      })
      .catch(() => {})
  }, [])

  const handleSave = async () => {
    setStatus('saving')
    const ok = await saveSettings({
      krirk_name: name.trim() || 'Krirk',
      personality_notes: notes.trim(),
    })
    setStatus(ok ? 'saved' : 'error')
    setTimeout(() => setStatus('idle'), 1500)
  }

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '7px 10px', borderRadius: 6,
    border: '1px solid var(--color-krirk-border)',
    background: 'var(--color-krirk-surface)',
    color: 'var(--color-krirk-text)', fontSize: 12, outline: 'none',
    boxSizing: 'border-box',
  }

  return (
    <div>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--color-krirk-text)' }}>
        Personalidade
      </h3>

      {/* Nome */}
      <label style={{ display: 'block', marginBottom: 16 }}>
        <span style={{ fontSize: 11, color: 'var(--color-krirk-muted)', display: 'block', marginBottom: 6 }}>
          Nome da companion
        </span>
        <input
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="Krirk"
          style={inputStyle}
        />
      </label>

      {/* Notas */}
      <label style={{ display: 'block', marginBottom: 12 }}>
        <span style={{ fontSize: 11, color: 'var(--color-krirk-muted)', display: 'block', marginBottom: 6 }}>
          Instruções de comportamento
        </span>
        <textarea
          value={notes}
          onChange={e => setNotes(e.target.value)}
          placeholder={'Ex: Seja mais formal e técnica.\nEvite humor durante o trabalho.\nChame-me de senhor.'}
          rows={5}
          style={{
            ...inputStyle,
            resize: 'vertical', lineHeight: 1.5,
            fontFamily: 'inherit',
          }}
        />
        <p style={{ fontSize: 10, color: 'var(--color-krirk-muted)', marginTop: 4 }}>
          Injetado no system prompt. Persiste entre sessões. Deixe vazio para comportamento padrão.
        </p>
      </label>

      {/* Botão salvar */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 10 }}>
        <SaveFeedback status={status} />
        <button
          onClick={handleSave}
          style={{
            padding: '8px 18px', borderRadius: 6, border: 'none',
            background: status === 'saving'
              ? 'rgba(99,102,241,0.15)'
              : 'rgba(99,102,241,0.3)',
            color: '#818cf8', fontSize: 12, fontWeight: 600,
            cursor: status === 'saving' ? 'not-allowed' : 'pointer',
          }}
          disabled={status === 'saving'}
        >
          {status === 'saving' ? 'Salvando…' : 'Salvar'}
        </button>
      </div>
    </div>
  )
}

// ── Aba Aparência (placeholder) ───────────────────────────────────────────────

function AppearanceTab() {
  return (
    <div>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: 'var(--color-krirk-text)' }}>
        Aparência
      </h3>
      <p style={{ fontSize: 12, color: 'var(--color-krirk-muted)' }}>Em desenvolvimento…</p>
      <p style={{ fontSize: 10, color: 'var(--color-krirk-muted)', marginTop: 8 }}>
        Temas de cores, opacidade da janela e tamanho do avatar virão em versão futura.
      </p>
    </div>
  )
}

// ── Shell principal ───────────────────────────────────────────────────────────

const TABS: { id: SettingsTab; label: string; icon: string }[] = [
  { id: 'models',      label: 'Modelos',       icon: '🤖' },
  { id: 'personality', label: 'Personalidade', icon: '✨' },
  { id: 'appearance',  label: 'Aparência',     icon: '🎨' },
  { id: 'hardware',    label: 'Hardware',      icon: '💻' },
]

export function SettingsPage() {
  const [tab, setTab] = useState<SettingsTab>('models')

  return (
    <div style={{
      display: 'flex', height: '100vh',
      background: 'var(--color-krirk-bg)',
      color: 'var(--color-krirk-text)',
    }}>
      {/* Nav lateral */}
      <nav style={{
        width: 108, background: 'var(--color-krirk-sidebar)',
        borderRight: '1px solid var(--color-krirk-border)',
        padding: '12px 8px', display: 'flex', flexDirection: 'column', gap: 4,
        flexShrink: 0,
      }}>
        <div style={{
          fontSize: 9, fontWeight: 700, letterSpacing: '0.1em',
          color: 'var(--color-krirk-muted)', textTransform: 'uppercase',
          paddingLeft: 4, marginBottom: 6,
        }}>
          KRIRK
        </div>
        {TABS.map(({ id, label, icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '8px 8px', borderRadius: 6, border: 'none',
              background: tab === id ? 'rgba(99,102,241,0.25)' : 'transparent',
              color: tab === id ? '#818cf8' : 'rgba(255,255,255,0.45)',
              fontSize: 11, fontWeight: tab === id ? 600 : 400,
              cursor: 'pointer', textAlign: 'left', width: '100%',
              transition: 'background 0.15s, color 0.15s',
              borderLeft: tab === id ? '2px solid #818cf8' : '2px solid transparent',
            }}
          >
            <span style={{ fontSize: 14 }}>{icon}</span>
            <span>{label}</span>
          </button>
        ))}
      </nav>

      {/* Conteúdo */}
      <main style={{ flex: 1, padding: 20, overflowY: 'auto' }}>
        {tab === 'models'      && <ModelsTab />}
        {tab === 'personality' && <PersonalityTab />}
        {tab === 'appearance'  && <AppearanceTab />}
        {tab === 'hardware'    && <HardwareTab />}
      </main>
    </div>
  )
}
