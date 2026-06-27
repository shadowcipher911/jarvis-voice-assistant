import React, { useEffect, useRef, useState } from 'react'

const s = {
  container: {
    display: 'flex', flexDirection: 'column', height: '100%',
    padding: '16px 24px', gap: '12px',
  },
  toolbar: { display: 'flex', gap: '8px', alignItems: 'center' },
  logBox: {
    flex: 1, overflowY: 'auto',
    background: '#060c18', border: '1px solid #1e3a5f',
    borderRadius: '8px', padding: '12px 16px',
    fontFamily: 'Consolas, "Courier New", monospace',
    fontSize: '12px', lineHeight: '1.6',
  },
  line: (level) => ({
    color: level === 'ERROR' ? '#ef5350'
      : level === 'WARNING' ? '#ffa726'
      : level === 'INFO' ? '#4fc3f7'
      : '#78909c',
    marginBottom: '2px',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-all',
  }),
  btn: (active) => ({
    padding: '6px 14px',
    background: active ? '#1565c0' : '#0d1529',
    border: '1px solid #1e3a5f',
    borderRadius: '6px', color: '#c8d8f0',
    cursor: 'pointer', fontSize: '12px',
  }),
  label: { fontSize: '13px', color: '#546e7a' },
}

const LEVEL_RE = /\b(ERROR|WARNING|INFO|DEBUG)\b/

function getLevel(line) {
  const m = line.match(LEVEL_RE)
  return m ? m[1] : 'DEBUG'
}

export default function LiveLog() {
  const [lines, setLines] = useState([])
  const [paused, setPaused] = useState(false)
  const [filter, setFilter] = useState('')
  const bottomRef = useRef(null)
  const wsRef = useRef(null)

  useEffect(() => {
    const wsPort = window.location.port === '3000' ? '8000' : window.location.port
    const connect = () => {
      const ws = new WebSocket(`ws://localhost:${wsPort}/ws/logs`)
      wsRef.current = ws

      ws.onmessage = (e) => {
        if (paused) return
        setLines(prev => {
          const next = [...prev, e.data]
          return next.slice(-500) // keep last 500 lines
        })
      }
      ws.onclose = () => setTimeout(connect, 2000)
      ws.onerror = () => ws.close()
    }
    connect()
    return () => wsRef.current?.close()
  }, [])

  useEffect(() => {
    if (!paused) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines, paused])

  const displayed = filter
    ? lines.filter(l => l.toLowerCase().includes(filter.toLowerCase()))
    : lines

  return (
    <div style={s.container}>
      <div style={s.toolbar}>
        <span style={s.label}>Live Log Stream</span>
        <input
          placeholder="Filter…"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          style={{ ...s.btn(false), width: 180 }}
          aria-label="Filter logs"
        />
        <button style={s.btn(paused)} onClick={() => setPaused(p => !p)}>
          {paused ? '▶ Resume' : '⏸ Pause'}
        </button>
        <button style={s.btn(false)} onClick={() => setLines([])}>
          Clear
        </button>
        <span style={{ marginLeft: 'auto', ...s.label }}>{displayed.length} lines</span>
      </div>

      <div style={s.logBox} role="log" aria-live="polite" aria-label="Log output">
        {displayed.length === 0 && (
          <div style={{ color: '#37474f', fontStyle: 'italic' }}>
            Waiting for log events… (ensure main.py is running)
          </div>
        )}
        {displayed.map((line, i) => (
          <div key={i} style={s.line(getLevel(line))}>{line}</div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
