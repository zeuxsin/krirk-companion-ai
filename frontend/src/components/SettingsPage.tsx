import React, { useState, useEffect } from 'react'

type SettingsTab = 'models' | 'shortcuts' | 'appearance' | 'hardware'

interface HardwareStats {
  cpu: number
  ram_used: number
  ram_total: number
  ram_percent: number
}

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

function HardwareTab() {
  const [stats, setStats] = useState<HardwareStats | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const r = await fetch('http://localhost:8000/api/system')
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

      {/* CPU */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-krirk-text)' }}>CPU</span>
          <span style={{ fontSize: 12, color: 'var(--color-krirk-muted)' }}>
            {stats ? `${stats.cpu.toFixed(1)}%` : '—'}
          </span>
        </div>
        <ProgressBar value={stats?.cpu ?? 0} />
      </div>

      {/* RAM */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-krirk-text)' }}>RAM</span>
          <span style={{ fontSize: 12, color: 'var(--color-krirk-muted)' }}>
            {stats ? `${stats.ram_used.toFixed(1)} GB / ${stats.ram_total.toFixed(0)} GB` : '—'}
          </span>
        </div>
        <ProgressBar value={stats?.ram_percent ?? 0} color='#34d399' />
      </div>

      {/* GPU */}
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

function ModelsTab() {
  const [model, setModel] = useState('gemma3:4b')
  const [temp, setTemp] = useState('0.85')

  return (
    <div>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--color-krirk-text)' }}>
        Modelos
      </h3>
      <label style={{ display: 'block', marginBottom: 12 }}>
        <span style={{ fontSize: 11, color: 'var(--color-krirk-muted)', display: 'block', marginBottom: 4 }}>
          Modelo Ollama
        </span>
        <input
          value={model}
          onChange={e => setModel(e.target.value)}
          style={{
            width: '100%', padding: '7px 10px', borderRadius: 6,
            border: '1px solid var(--color-krirk-border)',
            background: 'var(--color-krirk-surface)',
            color: 'var(--color-krirk-text)', fontSize: 12, outline: 'none',
          }}
        />
      </label>
      <label style={{ display: 'block' }}>
        <span style={{ fontSize: 11, color: 'var(--color-krirk-muted)', display: 'block', marginBottom: 4 }}>
          Temperatura ({temp})
        </span>
        <input
          type="range" min="0" max="1" step="0.05" value={temp}
          onChange={e => setTemp(e.target.value)}
          style={{ width: '100%' }}
        />
      </label>
    </div>
  )
}

function PlaceholderTab({ title }: { title: string }) {
  return (
    <div>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: 'var(--color-krirk-text)' }}>
        {title}
      </h3>
      <p style={{ fontSize: 12, color: 'var(--color-krirk-muted)' }}>Em desenvolvimento...</p>
    </div>
  )
}

const TABS: { id: SettingsTab; label: string; icon: string }[] = [
  { id: 'models',     label: 'Modelos',   icon: '🤖' },
  { id: 'shortcuts',  label: 'Atalhos',   icon: '⌨️' },
  { id: 'appearance', label: 'Aparência', icon: '🎨' },
  { id: 'hardware',   label: 'Hardware',  icon: '💻' },
]

export function SettingsPage() {
  const [tab, setTab] = useState<SettingsTab>('hardware')

  return (
    <div style={{
      display: 'flex', height: '100vh',
      background: 'var(--color-krirk-bg)',
      color: 'var(--color-krirk-text)',
    }}>
      {/* Nav lateral */}
      <nav style={{
        width: 100, background: 'var(--color-krirk-sidebar)',
        borderRight: '1px solid var(--color-krirk-border)',
        padding: '12px 8px', display: 'flex', flexDirection: 'column', gap: 4,
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
        {tab === 'hardware'   && <HardwareTab />}
        {tab === 'models'     && <ModelsTab />}
        {tab === 'shortcuts'  && <PlaceholderTab title="Atalhos de teclado" />}
        {tab === 'appearance' && <PlaceholderTab title="Aparência" />}
      </main>
    </div>
  )
}
