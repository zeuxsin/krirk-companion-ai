import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Bot, Sparkles, Brain, Moon, Palette, Cpu,
  MessageSquare, Pin, Link2, Heart,
  Scale, Fingerprint, Laugh, Lightbulb, BookOpen,
  Target, Smile, Shuffle, AlertTriangle, X,
} from 'lucide-react'

type SettingsTab = 'models' | 'personality' | 'memory' | 'interior' | 'appearance' | 'hardware'

// ── Tipos de memória ──────────────────────────────────────────────────────────

interface KGRelation {
  entity_from: string
  relation: string
  entity_to: string
  confidence: number
}

interface UserProfile {
  nome: string
  idade: string
  profissao: string
  cidade: string
  interesses: string[]
  projetos: string[]
  ferramentas: string[]
  objetivos: string[]
  notas: string
}

interface MemoryStats {
  total_messages: number
  facts_stored: number
  intimacy_level: number
  first_seen: string | null
  semantic_memories: number
  kg_entities: number
  kg_relations: number
}

interface MemoryData {
  stats: MemoryStats
  profile: UserProfile
  facts: string[]
  kg_relations: KGRelation[]
}

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
    <OfflineNotice />
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

// ── Aba Memória ───────────────────────────────────────────────────────────────

const LIST_STYLE: React.CSSProperties = {
  fontSize: 11, color: 'var(--color-krirk-text)',
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  padding: '5px 0', borderBottom: '1px solid rgba(255,255,255,0.04)',
  gap: 8,
}

const X_BTN: React.CSSProperties = {
  flexShrink: 0, background: 'none', border: 'none', cursor: 'pointer',
  color: 'rgba(255,255,255,0.25)', fontSize: 14, lineHeight: 1,
  padding: '0 2px',
  transition: 'color 0.15s',
}

function SectionHeader({ title, count, icon }: { title: string; count?: number; icon?: React.ReactNode }) {
  return (
    <div style={{
      fontSize: 11, fontWeight: 700, color: 'var(--color-krirk-muted)',
      textTransform: 'uppercase', letterSpacing: '0.08em',
      marginTop: 20, marginBottom: 10,
      display: 'flex', alignItems: 'center', gap: 6,
    }}>
      {icon}
      <span>{title}{count !== undefined ? ` (${count})` : ''}</span>
    </div>
  )
}

function OfflineNotice() {
  return (
    <div style={{
      fontSize: 12, color: 'var(--color-krirk-muted)', padding: 12,
      display: 'flex', alignItems: 'center', gap: 6,
    }}>
      <AlertTriangle size={13} style={{ flexShrink: 0, color: '#f59e0b' }} />
      Backend offline — inicie o servidor Python
    </div>
  )
}

function MemoryTab() {
  const [data, setData] = useState<MemoryData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  // Perfil local para edição
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [profileStatus, setProfileStatus] = useState<'idle'|'saving'|'saved'|'error'>('idle')

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/memory`)
      if (!r.ok) { setError(true); return }
      const d: MemoryData = await r.json()
      setData(d)
      setProfile(d.profile)
      setError(false)
    } catch { setError(true) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const deleteFact = async (fact: string) => {
    await fetch(`${API}/api/memory/fact`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fact }),
    })
    load()
  }

  const deleteRelation = async (r: KGRelation) => {
    await fetch(`${API}/api/memory/kg-relation`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        entity_from: r.entity_from,
        relation: r.relation,
        entity_to: r.entity_to,
      }),
    })
    load()
  }

  const saveProfile = async () => {
    if (!profile) return
    setProfileStatus('saving')
    try {
      const r = await fetch(`${API}/api/memory/profile`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile }),
      })
      setProfileStatus(r.ok ? 'saved' : 'error')
    } catch { setProfileStatus('error') }
    setTimeout(() => setProfileStatus('idle'), 1500)
  }

  const clearAll = async () => {
    if (!window.confirm('Apagar todos os fatos, relações e perfil? Esta ação não pode ser desfeita.')) return
    await fetch(`${API}/api/memory/all`, { method: 'DELETE' })
    load()
  }

  // Helper para campos CSV (interesses, ferramentas, etc.)
  const listToCSV = (arr: string[]) => arr.join(', ')
  const csvToList = (s: string) => s.split(',').map(x => x.trim()).filter(Boolean)

  const fieldStyle: React.CSSProperties = {
    width: '100%', padding: '5px 8px', borderRadius: 5,
    border: '1px solid var(--color-krirk-border)',
    background: 'var(--color-krirk-surface)',
    color: 'var(--color-krirk-text)', fontSize: 11, outline: 'none',
    boxSizing: 'border-box',
  }

  if (loading) return (
    <div style={{ fontSize: 12, color: 'var(--color-krirk-muted)', padding: 16 }}>
      Carregando memórias…
    </div>
  )

  if (error) return (
    <OfflineNotice />
  )

  const s = data!.stats

  const formatDate = (iso: string | null) => {
    if (!iso) return '—'
    try { return new Date(iso).toLocaleDateString('pt-BR') } catch { return iso }
  }

  return (
    <div>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--color-krirk-text)' }}>
        Memória
      </h3>

      {/* ── Stats ── */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8,
      }}>
        {[
          { label: 'Mensagens',   value: s.total_messages,               Icon: MessageSquare },
          { label: 'Fatos',       value: s.facts_stored,                 Icon: Pin },
          { label: 'Relações KG', value: s.kg_relations,                 Icon: Link2 },
          { label: 'Intimidade',  value: `${s.intimacy_level.toFixed(1)}`, Icon: Heart },
        ].map(({ label, value, Icon }) => (
          <div key={label} style={{
            background: 'var(--color-krirk-surface)',
            borderRadius: 8, padding: '8px 10px',
            border: '1px solid var(--color-krirk-border)',
          }}>
            <div style={{
              fontSize: 10, color: 'var(--color-krirk-muted)', marginBottom: 2,
              display: 'flex', alignItems: 'center', gap: 4,
            }}><Icon size={10} /> {label}</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--color-krirk-text)' }}>{value}</div>
          </div>
        ))}
      </div>
      <div style={{ fontSize: 10, color: 'var(--color-krirk-muted)', marginTop: 6 }}>
        📅 Desde: {formatDate(s.first_seen)}
      </div>

      {/* ── Perfil ── */}
      {profile && (
        <>
          <SectionHeader title="Perfil" />
          {([
            { key: 'nome',     label: 'Nome' },
            { key: 'profissao', label: 'Profissão' },
            { key: 'cidade',   label: 'Cidade' },
          ] as const).map(({ key, label }) => (
            <label key={key} style={{ display: 'block', marginBottom: 6 }}>
              <span style={{ fontSize: 10, color: 'var(--color-krirk-muted)', display: 'block', marginBottom: 3 }}>{label}</span>
              <input
                value={(profile as any)[key] as string}
                onChange={e => setProfile(p => p ? { ...p, [key]: e.target.value } : p)}
                style={fieldStyle}
              />
            </label>
          ))}
          {([
            { key: 'interesses',  label: 'Interesses (CSV)' },
            { key: 'ferramentas', label: 'Ferramentas (CSV)' },
            { key: 'projetos',    label: 'Projetos (CSV)' },
          ] as const).map(({ key, label }) => (
            <label key={key} style={{ display: 'block', marginBottom: 6 }}>
              <span style={{ fontSize: 10, color: 'var(--color-krirk-muted)', display: 'block', marginBottom: 3 }}>{label}</span>
              <input
                value={listToCSV((profile as any)[key] as string[])}
                onChange={e => setProfile(p => p ? { ...p, [key]: csvToList(e.target.value) } : p)}
                style={fieldStyle}
                placeholder="item1, item2, item3"
              />
            </label>
          ))}
          <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 8, marginTop: 8 }}>
            <SaveFeedback status={profileStatus} />
            <button
              onClick={saveProfile}
              disabled={profileStatus === 'saving'}
              style={{
                padding: '6px 14px', borderRadius: 6, border: 'none',
                background: 'rgba(99,102,241,0.3)', color: '#818cf8',
                fontSize: 11, fontWeight: 600, cursor: 'pointer',
              }}
            >
              Salvar perfil
            </button>
          </div>
        </>
      )}

      {/* ── Fatos ── */}
      <SectionHeader title="Fatos" count={data!.facts.length} />
      {data!.facts.length === 0
        ? <p style={{ fontSize: 11, color: 'var(--color-krirk-muted)' }}>Nenhum fato registrado ainda.</p>
        : data!.facts.map((fact, i) => (
          <div key={i} style={LIST_STYLE}>
            <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              • {fact}
            </span>
            <button style={X_BTN} title="Apagar" onClick={() => deleteFact(fact)}>×</button>
          </div>
        ))
      }

      {/* ── Knowledge Graph ── */}
      <SectionHeader title="Knowledge Graph" count={data!.kg_relations.length} />
      {data!.kg_relations.length === 0
        ? <p style={{ fontSize: 11, color: 'var(--color-krirk-muted)' }}>Nenhuma relação registrada ainda.</p>
        : data!.kg_relations.map((rel, i) => (
          <div key={i} style={LIST_STYLE}>
            <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {rel.entity_from} → {rel.relation} → {rel.entity_to}
            </span>
            <button style={X_BTN} title="Apagar" onClick={() => deleteRelation(rel)}>×</button>
          </div>
        ))
      }

      {/* ── Zona de perigo ── */}
      <div style={{
        marginTop: 24, paddingTop: 16,
        borderTop: '1px solid rgba(239,68,68,0.2)',
      }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: '#ef4444', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Zona de perigo
        </div>
        <button
          onClick={clearAll}
          style={{
            padding: '7px 14px', borderRadius: 6, border: '1px solid rgba(239,68,68,0.4)',
            background: 'rgba(239,68,68,0.1)', color: '#ef4444',
            fontSize: 11, fontWeight: 600, cursor: 'pointer',
          }}
        >
          Apagar toda a memória
        </button>
        <p style={{ fontSize: 10, color: 'var(--color-krirk-muted)', marginTop: 6 }}>
          Remove fatos, relações e perfil. O histórico de mensagens é mantido.
        </p>
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

// ── Aba Vida Interior — diário, reflexões, bordões, kernel, brain-state ──────

interface LexiconTerm { term: string; meaning: string; usage_count: number; pinned: number }
interface DiaryEntry { content: string; mood: string; created_at: string }
interface Reflection { content: string; category: string; created_at: string }
interface KernelVersion { id: number; note: string; active: number; created_at: string }
interface PendingProposal { id: number; kind: string; rationale: string; tier: number }

const BRAIN_MODES: { id: string; label: string; desc: string; Icon: React.ElementType }[] = [
  { id: 'focused',  label: 'Focada',    desc: 'precisa e direta',     Icon: Target },
  { id: 'chill',    label: 'Tranquila', desc: 'equilibrada (padrão)', Icon: Smile },
  { id: 'creative', label: 'Criativa',  desc: 'solta e inventiva',    Icon: Sparkles },
  { id: 'chaos',    label: 'Caos',      desc: 'imprevisível',         Icon: Shuffle },
]

const KIND_DESC: Record<string, string> = {
  sublation: 'reorganizar as próprias memórias',
  kernel: 'reescrever a própria identidade',
  wipe_memory: 'apagar toda a memória',
}

function InteriorTab() {
  const [lexicon, setLexicon] = useState<LexiconTerm[]>([])
  const [diary, setDiary] = useState<DiaryEntry[]>([])
  const [reflections, setReflections] = useState<Reflection[]>([])
  const [kernelActive, setKernelActive] = useState<string | null>(null)
  const [kernelVersions, setKernelVersions] = useState<KernelVersion[]>([])
  const [proposals, setProposals] = useState<PendingProposal[]>([])
  const [brainState, setBrainState] = useState<string>('chill')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [mem, kernel, props, settings] = await Promise.all([
        fetch(`${API}/api/memory`).then(r => r.json()),
        fetch(`${API}/api/kernel`).then(r => r.json()),
        fetch(`${API}/api/proposals`).then(r => r.json()),
        fetch(`${API}/api/settings`).then(r => r.json()),
      ])
      setLexicon(mem.lexicon ?? [])
      setDiary((mem.diary ?? []).slice().reverse())   // mais recente primeiro
      setReflections(mem.reflections ?? [])
      setKernelActive(kernel.active)
      setKernelVersions(kernel.versions ?? [])
      setProposals(props.proposals ?? [])
      setBrainState(settings.brain_state ?? 'chill')
      setError(false)
    } catch { setError(true) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const setBrain = async (mode: string) => {
    setBrainState(mode)
    try {
      await fetch(`${API}/api/brain_state`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      })
    } catch { /* offline */ }
  }

  const deleteTerm = async (term: string) => {
    await fetch(`${API}/api/memory/term`, {
      method: 'DELETE', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ term }),
    })
    load()
  }

  const respondProposal = async (id: number, approve: boolean) => {
    await fetch(`${API}/api/proposals/${id}/${approve ? 'approve' : 'reject'}`, { method: 'POST' })
    load()
  }

  const proposeKernel = async () => {
    setBusy('kernel')
    try { await fetch(`${API}/api/kernel/propose`, { method: 'POST' }) } catch { /* offline */ }
    setBusy(null)
    load()
  }

  const rollbackKernel = async (kernelId: number) => {
    await fetch(`${API}/api/kernel/rollback`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kernel_id: kernelId }),
    })
    load()
  }

  const forceDream = async () => {
    setBusy('dream')
    try { await fetch(`${API}/api/reflection/dream`, { method: 'POST' }) } catch { /* offline */ }
    setBusy(null)
    load()
  }

  const fmtDate = (iso: string) => {
    try { return new Date(iso).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) }
    catch { return iso }
  }

  const cardStyle: React.CSSProperties = {
    background: 'var(--color-krirk-surface)', borderRadius: 8,
    padding: '8px 10px', border: '1px solid var(--color-krirk-border)',
    fontSize: 11, marginBottom: 6, lineHeight: 1.5,
  }
  const smallBtn: React.CSSProperties = {
    padding: '3px 10px', borderRadius: 5, border: 'none', cursor: 'pointer',
    fontSize: 10, fontWeight: 600, background: 'rgba(124,58,237,0.25)', color: '#a78bfa',
  }

  if (loading) return <div style={{ fontSize: 12, color: 'var(--color-krirk-muted)', padding: 16 }}>Carregando vida interior…</div>
  if (error) return <OfflineNotice />

  return (
    <div>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 4, color: 'var(--color-krirk-text)' }}>
        Vida Interior
      </h3>
      <p style={{ fontSize: 10, color: 'var(--color-krirk-muted)', marginBottom: 12 }}>
        O que a Krirk pensa, sonha e aprende por conta própria.
      </p>

      {/* ── Propostas pendentes ── */}
      {proposals.length > 0 && (
        <>
          <SectionHeader title="Aguardando sua aprovação" count={proposals.length} icon={<Scale size={12} />} />
          {proposals.map(p => (
            <div key={p.id} style={{ ...cardStyle, border: '1px solid #7c3aed' }}>
              <div style={{ fontWeight: 700, color: '#a78bfa', marginBottom: 3 }}>
                Ela quer {KIND_DESC[p.kind] ?? p.kind}
              </div>
              <div style={{ color: 'var(--color-krirk-muted)', marginBottom: 6 }}>{p.rationale}</div>
              <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                <button onClick={() => respondProposal(p.id, false)} style={{ ...smallBtn, background: 'transparent', color: 'rgba(255,255,255,0.5)' }}>Recusar</button>
                <button onClick={() => respondProposal(p.id, true)} style={{ ...smallBtn, background: '#7c3aed', color: '#fff' }}>Aprovar</button>
              </div>
            </div>
          ))}
        </>
      )}

      {/* ── Brain-state ── */}
      <SectionHeader title="Estado mental (geração)" icon={<Brain size={12} />} />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
        {BRAIN_MODES.map(m => (
          <button key={m.id} onClick={() => setBrain(m.id)} style={{
            padding: '8px 10px', borderRadius: 8, cursor: 'pointer', textAlign: 'left',
            border: brainState === m.id ? '1px solid #7c3aed' : '1px solid var(--color-krirk-border)',
            background: brainState === m.id ? 'rgba(124,58,237,0.15)' : 'var(--color-krirk-surface)',
            color: 'var(--color-krirk-text)',
          }}>
            <div style={{ fontSize: 11, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 5 }}>
              <m.Icon size={12} style={{ color: brainState === m.id ? '#a78bfa' : 'var(--color-krirk-muted)' }} />
              {m.label}
            </div>
            <div style={{ fontSize: 9, color: 'var(--color-krirk-muted)' }}>{m.desc}</div>
          </button>
        ))}
      </div>

      {/* ── Identidade (kernel) ── */}
      <SectionHeader title="Identidade (kernel)" icon={<Fingerprint size={12} />} />
      <div style={cardStyle}>
        {kernelActive ? (
          <div style={{ fontStyle: 'italic', color: 'var(--color-krirk-text)' }}>{kernelActive}</div>
        ) : (
          <div style={{ color: 'var(--color-krirk-muted)' }}>Persona padrão (nenhum kernel auto-autorado ativo)</div>
        )}
        <div style={{ display: 'flex', gap: 6, marginTop: 8, justifyContent: 'flex-end' }}>
          {kernelActive && (
            <button onClick={() => rollbackKernel(0)} style={{ ...smallBtn, background: 'transparent', color: 'rgba(255,255,255,0.5)' }}>
              Voltar ao padrão
            </button>
          )}
          <button onClick={proposeKernel} disabled={busy === 'kernel'} style={smallBtn}>
            {busy === 'kernel' ? 'Redigindo…' : 'Pedir para ela redigir um novo'}
          </button>
        </div>
      </div>
      {kernelVersions.length > 0 && kernelVersions.map(k => (
        <div key={k.id} style={{ ...cardStyle, display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ flex: 1, color: 'var(--color-krirk-muted)' }}>
            v{k.id} · {fmtDate(k.created_at)} {k.active ? '· ATIVA' : ''} {k.note ? `· ${k.note.slice(0, 60)}` : ''}
          </span>
          {!k.active && <button onClick={() => rollbackKernel(k.id)} style={smallBtn}>Ativar</button>}
        </div>
      ))}

      {/* ── Bordões / memes internos ── */}
      <SectionHeader title="Bordões de vocês" count={lexicon.length} icon={<Laugh size={12} />} />
      {lexicon.length === 0 && <div style={{ fontSize: 11, color: 'var(--color-krirk-muted)' }}>Nenhum ainda — diga "esse é nosso bordão: ..." no chat.</div>}
      {lexicon.map(t => (
        <div key={t.term} style={{ ...cardStyle, display: 'flex', gap: 8, alignItems: 'flex-start' }}>
          <div style={{ flex: 1 }}>
            <span style={{ fontWeight: 700, color: '#a78bfa' }}>"{t.term}"</span>
            {t.pinned ? <Pin size={9} style={{ marginLeft: 6, verticalAlign: '-1px', color: '#a78bfa' }} /> : null}
            <span style={{ fontSize: 9, color: 'var(--color-krirk-muted)', marginLeft: 6 }}>usado {t.usage_count}×</span>
            <div style={{ color: 'var(--color-krirk-muted)', marginTop: 2 }}>{t.meaning}</div>
          </div>
          <button onClick={() => deleteTerm(t.term)} title="Esquecer este bordão"
            style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.3)', cursor: 'pointer', padding: 0, display: 'flex' }}>
            <X size={12} />
          </button>
        </div>
      ))}

      {/* ── Reflexões ── */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <SectionHeader title="O que ela percebe sobre você" count={reflections.length} icon={<Lightbulb size={12} />} />
        <button onClick={forceDream} disabled={busy === 'dream'} style={{ ...smallBtn, marginTop: 12 }}>
          {busy === 'dream' ? 'Sonhando…' : 'Refletir agora'}
        </button>
      </div>
      {reflections.length === 0 && <div style={{ fontSize: 11, color: 'var(--color-krirk-muted)' }}>Nenhuma reflexão ainda.</div>}
      {reflections.map((r, i) => (
        <div key={i} style={cardStyle}>
          <span style={{ fontSize: 9, color: r.category === 'humor' ? '#fbbf24' : '#38bdf8', textTransform: 'uppercase', fontWeight: 700 }}>{r.category}</span>
          <div style={{ marginTop: 2 }}>{r.content}</div>
        </div>
      ))}

      {/* ── Diário ── */}
      <SectionHeader title="Diário dela" count={diary.length} icon={<BookOpen size={12} />} />
      {diary.length === 0 && <div style={{ fontSize: 11, color: 'var(--color-krirk-muted)' }}>Nenhuma entrada ainda.</div>}
      {diary.map((d, i) => (
        <div key={i} style={{ ...cardStyle, fontStyle: 'italic' }}>
          <div style={{ fontSize: 9, color: 'var(--color-krirk-muted)', marginBottom: 3, fontStyle: 'normal' }}>
            {fmtDate(d.created_at)} · sentindo-se {d.mood}
          </div>
          {d.content}
        </div>
      ))}
    </div>
  )
}

// ── Shell principal ───────────────────────────────────────────────────────────

const TABS: { id: SettingsTab; label: string; Icon: React.ElementType }[] = [
  { id: 'models',      label: 'Modelos',       Icon: Bot },
  { id: 'personality', label: 'Personalidade', Icon: Sparkles },
  { id: 'memory',      label: 'Memória',       Icon: Brain },
  { id: 'interior',    label: 'Vida Interior', Icon: Moon },
  { id: 'appearance',  label: 'Aparência',     Icon: Palette },
  { id: 'hardware',    label: 'Hardware',      Icon: Cpu },
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
        {TABS.map(({ id, label, Icon }) => (
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
            <Icon size={14} style={{ flexShrink: 0 }} />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      {/* Conteúdo */}
      <main style={{ flex: 1, padding: 20, overflowY: 'auto' }}>
        {tab === 'models'      && <ModelsTab />}
        {tab === 'personality' && <PersonalityTab />}
        {tab === 'memory'      && <MemoryTab />}
        {tab === 'interior'    && <InteriorTab />}
        {tab === 'appearance'  && <AppearanceTab />}
        {tab === 'hardware'    && <HardwareTab />}
      </main>
    </div>
  )
}
