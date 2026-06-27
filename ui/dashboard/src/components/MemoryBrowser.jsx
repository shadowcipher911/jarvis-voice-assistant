import React, { useState, useEffect } from 'react'

const s = {
  container: { padding: '24px', height: '100%', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px' },
  heading: { fontSize: '16px', fontWeight: 600, color: '#4fc3f7', letterSpacing: '1px' },
  searchRow: { display: 'flex', gap: '8px' },
  input: {
    flex: 1, padding: '10px 14px',
    background: '#0d1529', border: '1px solid #1e3a5f',
    borderRadius: '8px', color: '#c8d8f0', fontSize: '14px', outline: 'none',
  },
  btn: {
    padding: '10px 18px', background: '#1565c0', border: 'none',
    borderRadius: '8px', color: '#fff', cursor: 'pointer', fontSize: '13px',
  },
  section: { display: 'flex', flexDirection: 'column', gap: '8px' },
  sectionTitle: { fontSize: '13px', color: '#546e7a', letterSpacing: '1px', fontWeight: 600 },
  card: {
    background: '#0d1529', border: '1px solid #1e3a5f',
    borderRadius: '8px', padding: '12px 16px',
    fontSize: '13px', lineHeight: 1.5,
  },
  meta: { fontSize: '11px', color: '#37474f', marginTop: '4px' },
  relevance: (r) => ({
    display: 'inline-block', padding: '1px 6px', borderRadius: '4px',
    fontSize: '10px', fontWeight: 600, marginLeft: '8px',
    background: r > 0.7 ? '#2e7d32' : r > 0.4 ? '#e65100' : '#37474f',
    color: '#fff',
  }),
  factRow: { display: 'flex', gap: '8px', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid #1e3a5f' },
  factKey: { color: '#90caf9', fontWeight: 600, minWidth: '120px', fontSize: '13px' },
  factVal: { color: '#c8d8f0', fontSize: '13px' },
  empty: { color: '#37474f', fontStyle: 'italic', fontSize: 13 },
}

const API = window.location.port === '3000' ? 'http://localhost:8000' : ''

export default function MemoryBrowser() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [facts, setFacts] = useState({})
  const [pinned, setPinned] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetch(`${API}/api/memory/facts`).then(r => r.json()).then(d => setFacts(d.facts || {})).catch(() => {})
    fetch(`${API}/api/memory/pinned`).then(r => r.json()).then(d => setPinned(d.pinned || [])).catch(() => {})
  }, [])

  const search = async () => {
    if (!query.trim()) return
    setLoading(true)
    try {
      const res = await fetch(`${API}/api/memory/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      })
      const data = await res.json()
      setResults(data.results || [])
    } catch {
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={s.container}>
      <div style={s.heading}>Memory Browser</div>

      {/* Search */}
      <div style={s.searchRow}>
        <input
          style={s.input}
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && search()}
          placeholder="Search memories…"
          aria-label="Search memories"
        />
        <button style={s.btn} onClick={search} disabled={loading}>
          {loading ? '…' : 'Search'}
        </button>
      </div>

      {/* Search results */}
      {results.length > 0 && (
        <div style={s.section}>
          <div style={s.sectionTitle}>SEARCH RESULTS</div>
          {results.map((r, i) => (
            <div key={i} style={s.card}>
              {r.text}
              <span style={s.relevance(r.relevance)}>{Math.round(r.relevance * 100)}%</span>
              <div style={s.meta}>{r.timestamp?.slice(0, 10) || ''} · importance {r.importance}</div>
            </div>
          ))}
        </div>
      )}

      {/* Pinned memories */}
      {pinned.length > 0 && (
        <div style={s.section}>
          <div style={s.sectionTitle}>📌 PINNED MEMORIES</div>
          {pinned.map((p, i) => <div key={i} style={s.card}>{p}</div>)}
        </div>
      )}

      {/* Facts */}
      <div style={s.section}>
        <div style={s.sectionTitle}>KNOWN FACTS</div>
        {Object.entries(facts).length === 0
          ? <div style={s.empty}>No facts stored yet.</div>
          : Object.entries(facts).map(([k, v]) => (
            <div key={k} style={s.factRow}>
              <div style={s.factKey}>{k}</div>
              <div style={s.factVal}>{v}</div>
            </div>
          ))
        }
      </div>
    </div>
  )
}
