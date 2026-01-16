import { useState, useEffect, useRef } from 'react'

interface Props {
  runId: string
}

export default function LiveLog({ runId }: Props) {
  const [logs, setLogs] = useState<string[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const logEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Fetch initial logs
    fetchLogs()

    // Connect to WebSocket for live updates
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/logs/${runId}`

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
    }

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        if (message.type === 'log_content') {
          const lines = message.data.content.split('\n')
          setLogs(lines)
        } else if (message.type === 'log_append') {
          const newLines = message.data.content.split('\n')
          setLogs((prev) => [...prev, ...newLines])
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setConnected(false)
    }

    ws.onclose = () => {
      setConnected(false)
    }

    return () => {
      if (ws) {
        ws.close()
      }
    }
  }, [runId])

  useEffect(() => {
    // Auto-scroll to bottom when new logs arrive
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const fetchLogs = async () => {
    try {
      const response = await fetch(`/api/logs/${runId}?lines=100`)
      if (response.ok) {
        const data = await response.json()
        if (data.logs && Array.isArray(data.logs)) {
          setLogs(data.logs)
        }
      }
    } catch (err) {
      console.error('Failed to fetch logs:', err)
    }
  }

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2>Live Logs</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: connected ? '#4caf50' : '#999',
            }}
          />
          <span style={{ fontSize: '0.875rem', color: '#666' }}>
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      <div className="log-container">
        {logs.length === 0 ? (
          <div style={{ color: '#999', textAlign: 'center', padding: '2rem' }}>
            No logs available
          </div>
        ) : (
          <>
            {logs.map((line, index) => (
              <div key={index} className="log-line">
                {line}
              </div>
            ))}
            <div ref={logEndRef} />
          </>
        )}
      </div>
    </div>
  )
}
