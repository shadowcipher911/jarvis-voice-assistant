import React, { useState, useEffect } from 'react'

const s = {
  container: { padding: '24px', height: '100%', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '720px' },
  heading: { fontSize: '16px', fontWeight: 600, color: '#4fc3f7', letterSpacing: '1px' },
  card: {
    background: '#0d1529', border: '1px solid #1e3a5f',
    borderRadius: '10px', padding: '20px',
    display: 'flex', flexDirection: 'column', gap: '12px',
  },
  label: { fontSize: '12px', color: '#546e7a', letterSpacing: '1px', marginBottom: '4px' },
  input: {
    width: '100%', padding: '10px 14px',
    background: '#060c18', border: '1px solid #1e3a5f',
    borderRadius: '6px', color: '#c8d8f0', fontSize: '13px', outline: 'none',
    fontFamily: 'Consolas, monospace',
  },
  row: { display: 'flex', gap: '8px' },
  btn: (variant) => ({
    padding: '10px 20px',
    background: variant === 'primary' ? '#1565c0' : variant === 'danger' ? '#b71c1c' : '#0d1529',
    border: `1px solid ${variant === 'primary' ? '#1e88e5' : variant === 'danger' ? '#e53935' : '#1e3a5f'}`,
    borderRadius: '8px', color: '#fff', cursor: 'pointer', fontSize: '13px',
  }),
  note: { fontSize: '12px', color: '#546e7a', lineHeight: 1.5 },
  badge: (ok) => ({
    padding: '4px 10px', borderRadius: '4px', fontSize: '11px', fontWeight: 600,
    background: ok ? '#2e7d32' : '#b71c1c', color: '#fff',
  }),
  alert: (type) => ({
    padding: '10px 14px', borderRadius: '6px', fontSize: '13px',
    background: type === 'success' ? '#1b5e2030' : '#b71c1c20',
    border: `1px solid ${type === 'success' ? '#2e7d32' : '#e53935'}`,
    color: type === 'success' ? '#a5d6a7' : '#ef9a9a',
  }),
}

const API = window.location.port === '3000' ? 'http://localhost:8000' : ''

export default function Settings() {
  const [config, setConfig] = useState('')
  const [original, setOriginal] = useState('')
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetch(`${API}/api/config`)
      .then(r => r.json())
      .then(d => { setConfig(d.content || ''); setOriginal(d.content || '') })
      .catch(() => setStatus({ type: 'error', message: 'Could not load config. Is JARVIS running?' }))
  }, [])

  const save = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API}/api/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: config }),
      })
      const data = await res.json()
      if (res.ok) {
        setOriginal(config)
        setStatus({ type: 'success', message: 'Configuration saved. Restart JARVIS to apply changes.' })
      } else {
        setStatus({ type: 'error', message: data.detail || 'Save failed.' })
      }
    } catch (e) {
      setStatus({ type: 'error', message: String(e) })
    } finally {
      setLoading(false)
    }
  }

  const hasChanges = config !== original

  return (
    <div style={s.container}>
      <div style={s.heading}>Settings</div>

      {status && (
        <div style={s.alert(status.type)}>{status.message}</div>
      )}

      <div style={s.card}>
        <div>
          <div style={s.label}>config.yaml</div>
          <div style={s.note}>
            Edit JARVIS configuration below. Changes require a restart to take full effect.
            API keys should be set in <code>.env</code>, not here.
          </div>
        </div>
        <textarea
          style={{ ...s.input, minHeight: '400px', resize: 'vertical' }}
          value={config}
          onChange={e => setConfig(e.target.value)}
          spellCheck={false}
          aria-label="JARVIS configuration YAML"
        />
        <div style={s.row}>
          <button style={s.btn('primary')} onClick={save} disabled={loading || !hasChanges}>
            {loading ? 'Saving…' : hasChanges ? '💾 Save Changes' : 'No Changes'}
          </button>
          <button style={s.btn('')} onClick={() => setConfig(original)} disabled={!hasChanges}>
            ↩ Reset
          </button>
        </div>
      </div>

      <div style={s.card}>
        <div style={s.label}>QUICK ACTIONS</div>
        <div style={s.row}>
          <button style={s.btn('')} onClick={() => fetch(`${API}/api/restart`, { method: 'POST' })}>
            🔄 Restart JARVIS
          </button>
          <button style={s.btn('')} onClick={() => fetch(`${API}/api/memory/clear`, { method: 'POST' })}>
            🗑 Clear Session
          </button>
        </div>
        <div style={s.note}>
          Restart reloads config and reconnects all services.
          Clear Session removes only the current session's conversation (memories are kept).
        </div>
      </div>
    </div>
  )
}
