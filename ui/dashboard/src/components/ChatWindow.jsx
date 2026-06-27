import React, { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'

const s = {
  container: {
    display: 'flex', flexDirection: 'column', height: '100%',
    padding: '16px 24px', gap: '12px',
  },
  messages: {
    flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column',
    gap: '12px', paddingRight: '4px',
  },
  bubble: (role) => ({
    maxWidth: '75%',
    alignSelf: role === 'user' ? 'flex-end' : 'flex-start',
    background: role === 'user' ? '#1e3a5f' : '#0d1e35',
    border: `1px solid ${role === 'user' ? '#2d5a8e' : '#1a3050'}`,
    borderRadius: role === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
    padding: '10px 14px',
    fontSize: '14px',
    lineHeight: '1.5',
  }),
  role: (role) => ({
    fontSize: '11px', fontWeight: 600, letterSpacing: '1px',
    color: role === 'user' ? '#90caf9' : '#4fc3f7',
    marginBottom: '4px',
  }),
  ts: { fontSize: '10px', color: '#37474f', marginTop: '4px', textAlign: 'right' },
  inputRow: {
    display: 'flex', gap: '8px',
  },
  input: {
    flex: 1, padding: '12px 16px',
    background: '#0d1529', border: '1px solid #1e3a5f',
    borderRadius: '10px', color: '#c8d8f0', fontSize: '14px', outline: 'none',
  },
  btn: {
    padding: '12px 20px', background: '#1565c0', border: 'none',
    borderRadius: '10px', color: '#fff', cursor: 'pointer', fontSize: '14px',
    fontWeight: 600,
  },
  thinking: {
    alignSelf: 'flex-start',
    color: '#546e7a', fontSize: '13px', fontStyle: 'italic',
    padding: '8px 14px',
  },
}

const API = window.location.port === '3000' ? 'http://localhost:8000' : ''

export default function ChatWindow() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Good day. I am JARVIS. How may I assist you?', ts: new Date().toISOString() }
  ])
  const [input, setInput] = useState('')
  const [thinking, setThinking] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, thinking])

  // Load history on mount
  useEffect(() => {
    fetch(`${API}/api/history`)
      .then(r => r.json())
      .then(data => {
        if (data.history?.length > 0) {
          setMessages(data.history.map(m => ({ ...m, ts: m.timestamp })))
        }
      })
      .catch(() => {})
  }, [])

  const send = async () => {
    const text = input.trim()
    if (!text || thinking) return
    setInput('')
    const userMsg = { role: 'user', content: text, ts: new Date().toISOString() }
    setMessages(prev => [...prev, userMsg])
    setThinking(true)

    try {
      const res = await fetch(`${API}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      })
      const data = await res.json()
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.response || 'No response.',
        ts: new Date().toISOString(),
      }])
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: Could not reach JARVIS API. Is \`python main.py\` running?`,
        ts: new Date().toISOString(),
      }])
    } finally {
      setThinking(false)
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  return (
    <div style={s.container}>
      <div style={s.messages}>
        {messages.map((m, i) => (
          <div key={i} style={s.bubble(m.role)}>
            <div style={s.role(m.role)}>{m.role === 'user' ? 'YOU' : 'JARVIS'}</div>
            <ReactMarkdown>{m.content}</ReactMarkdown>
            <div style={s.ts}>{m.ts ? new Date(m.ts).toLocaleTimeString() : ''}</div>
          </div>
        ))}
        {thinking && <div style={s.thinking}>JARVIS is thinking…</div>}
        <div ref={bottomRef} />
      </div>

      <div style={s.inputRow}>
        <input
          style={s.input}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Type a command or question…"
          disabled={thinking}
          aria-label="Message input"
        />
        <button style={s.btn} onClick={send} disabled={thinking} aria-label="Send">
          Send
        </button>
      </div>
    </div>
  )
}
