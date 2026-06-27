import React, { useState } from 'react'
import ChatWindow from './components/ChatWindow'
import LiveLog from './components/LiveLog'
import ToolActivity from './components/ToolActivity'
import MemoryBrowser from './components/MemoryBrowser'
import Settings from './components/Settings'

const TABS = ['Chat', 'Logs', 'Tools', 'Memory', 'Settings']

const styles = {
  app: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    background: '#0a0f1e',
    color: '#c8d8f0',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
    padding: '12px 24px',
    background: '#0d1529',
    borderBottom: '1px solid #1e3a5f',
  },
  logo: {
    fontSize: '22px',
    fontWeight: 700,
    letterSpacing: '4px',
    color: '#4fc3f7',
    textShadow: '0 0 20px #4fc3f740',
  },
  subtitle: { fontSize: '12px', color: '#546e7a', letterSpacing: '2px' },
  tabs: {
    display: 'flex',
    gap: '4px',
    padding: '8px 24px 0',
    background: '#0d1529',
    borderBottom: '1px solid #1e3a5f',
  },
  tab: (active) => ({
    padding: '8px 20px',
    cursor: 'pointer',
    border: 'none',
    background: active ? '#1e3a5f' : 'transparent',
    color: active ? '#4fc3f7' : '#546e7a',
    borderRadius: '6px 6px 0 0',
    fontSize: '13px',
    fontWeight: active ? 600 : 400,
    transition: 'all 0.15s',
  }),
  content: { flex: 1, overflow: 'hidden' },
}

export default function App() {
  const [activeTab, setActiveTab] = useState('Chat')

  const renderTab = () => {
    switch (activeTab) {
      case 'Chat': return <ChatWindow />
      case 'Logs': return <LiveLog />
      case 'Tools': return <ToolActivity />
      case 'Memory': return <MemoryBrowser />
      case 'Settings': return <Settings />
      default: return <ChatWindow />
    }
  }

  return (
    <div style={styles.app}>
      <header style={styles.header}>
        <div>
          <div style={styles.logo}>J.A.R.V.I.S</div>
          <div style={styles.subtitle}>JUST A RATHER VERY INTELLIGENT SYSTEM</div>
        </div>
        <StatusBadge />
      </header>

      <nav style={styles.tabs}>
        {TABS.map(tab => (
          <button
            key={tab}
            style={styles.tab(activeTab === tab)}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </nav>

      <main style={styles.content}>
        {renderTab()}
      </main>
    </div>
  )
}

function StatusBadge() {
  const [online, setOnline] = React.useState(false)

  React.useEffect(() => {
    const apiBase = window.location.port === '3000'
      ? 'http://localhost:8000'
      : ''
    const check = () =>
      fetch(`${apiBase}/api/health`)
        .then(r => { if (r.ok) setOnline(true); else setOnline(false) })
        .catch(() => setOnline(false))
    check()
    const id = setInterval(check, 5000)
    return () => clearInterval(id)
  }, [])

  return (
    <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '8px' }}>
      <span style={{
        width: 8, height: 8, borderRadius: '50%',
        background: online ? '#4caf50' : '#ef5350',
        boxShadow: online ? '0 0 8px #4caf50' : 'none',
      }} />
      <span style={{ fontSize: 12, color: online ? '#4caf50' : '#ef5350' }}>
        {online ? 'ONLINE' : 'OFFLINE'}
      </span>
    </div>
  )
}
