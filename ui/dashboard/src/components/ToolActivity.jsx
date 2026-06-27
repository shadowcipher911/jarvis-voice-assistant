import React, { useEffect, useState } from 'react'

const s = {
  container: {
    padding: '24px', height: '100%', overflowY: 'auto',
    display: 'flex', flexDirection: 'column', gap: '16px',
  },
  heading: { fontSize: '16px', fontWeight: 600, color: '#4fc3f7', letterSpacing: '1px' },
  card: {
    background: '#0d1529', border: '1px solid #1e3a5f',
    borderRadius: '10px', padding: '14px 18px',
  },
  activeCard: {
    background: '#0d2040', border: '1px solid #1565c0',
    borderRadius: '10px', padding: '14px 18px',
    boxShadow: '0 0 16px #1565c020',
  },
  toolName: { fontSize: '15px', fontWeight: 600, color: '#90caf9' },
  status: (s) => ({
    display: 'inline-block',
    marginLeft: '10px',
    padding: '2px 8px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 600,
    background: s === 'running' ? '#1565c0' : s === 'done' ? '#2e7d32' : '#37474f',
    color: '#fff',
  }),
  grid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '12px',
  },
  statCard: {
    background: '#0d1529', border: '1px solid #1e3a5f',
    borderRadius: '8px', padding: '14px',
    display: 'flex', flexDirection: 'column', gap: '4px',
  },
  statLabel: { fontSize: '11px', color: '#546e7a', letterSpacing: '1px' },
  statValue: { fontSize: '22px', fontWeight: 700, color: '#4fc3f7' },
  ts: { fontSize: '11px', color: '#37474f' },
}

const API = window.location.port === '3000' ? 'http://localhost:8000' : ''

export default function ToolActivity() {
  const [activity, setActivity] = useState({ active_tool: null, recent: [], stats: {} })

  useEffect(() => {
    const fetchActivity = () =>
      fetch(`${API}/api/activity`)
        .then(r => r.json())
        .then(setActivity)
        .catch(() => {})

    fetchActivity()
    const id = setInterval(fetchActivity, 1500)
    return () => clearInterval(id)
  }, [])

  const { active_tool, recent = [], stats = {} } = activity

  return (
    <div style={s.container}>
      <div style={s.heading}>Tool Activity</div>

      {/* Active tool */}
      <div style={active_tool ? s.activeCard : s.card}>
        {active_tool ? (
          <>
            <div style={s.toolName}>
              ⚡ {active_tool.name}
              <span style={s.status('running')}>RUNNING</span>
            </div>
            <div style={{ fontSize: '13px', color: '#78909c', marginTop: 4 }}>
              {active_tool.input || '—'}
            </div>
          </>
        ) : (
          <div style={{ color: '#37474f', fontStyle: 'italic', fontSize: 13 }}>
            No tool currently active. JARVIS is idle.
          </div>
        )}
      </div>

      {/* Stats */}
      {Object.keys(stats).length > 0 && (
        <>
          <div style={s.heading}>Session Stats</div>
          <div style={s.grid}>
            {Object.entries(stats).map(([k, v]) => (
              <div key={k} style={s.statCard}>
                <div style={s.statLabel}>{k.toUpperCase()}</div>
                <div style={s.statValue}>{v}</div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Recent tool calls */}
      {recent.length > 0 && (
        <>
          <div style={s.heading}>Recent Tool Calls</div>
          {recent.map((t, i) => (
            <div key={i} style={s.card}>
              <div style={s.toolName}>
                {t.name}
                <span style={s.status(t.status)}>{t.status?.toUpperCase()}</span>
              </div>
              {t.input && (
                <div style={{ fontSize: '12px', color: '#78909c', marginTop: 4, fontFamily: 'monospace' }}>
                  {String(t.input).slice(0, 120)}
                </div>
              )}
              <div style={s.ts}>{t.timestamp ? new Date(t.timestamp).toLocaleTimeString() : ''}</div>
            </div>
          ))}
        </>
      )}
    </div>
  )
}
