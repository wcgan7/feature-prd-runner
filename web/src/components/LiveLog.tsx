import { useState, useEffect, useRef, useMemo } from 'react'
import { buildApiUrl, buildAuthHeaders, buildWsUrl } from '../api'

interface Props {
  runId: string
  projectDir?: string
}

type LogLevel = 'ALL' | 'ERROR' | 'WARN' | 'INFO' | 'DEBUG'

export default function LiveLog({ runId, projectDir }: Props) {
  const [logs, setLogs] = useState<string[]>([])
  const [connected, setConnected] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [logLevel, setLogLevel] = useState<LogLevel>('ALL')
  const [autoScroll, setAutoScroll] = useState(true)
  const wsRef = useRef<WebSocket | null>(null)
  const logEndRef = useRef<HTMLDivElement>(null)
  const logContainerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Fetch initial logs
    fetchLogs()

    // Connect to WebSocket for live updates
    const wsUrl = buildWsUrl(`/ws/logs/${runId}`, projectDir)

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
  }, [runId, projectDir])

  useEffect(() => {
    // Auto-scroll to bottom when new logs arrive (if enabled)
    if (autoScroll) {
      logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, autoScroll])

  // Detect manual scroll to disable auto-scroll
  const handleScroll = () => {
    if (!logContainerRef.current) return

    const container = logContainerRef.current
    const isAtBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight < 50

    if (isAtBottom !== autoScroll) {
      setAutoScroll(isAtBottom)
    }
  }

  const fetchLogs = async () => {
    try {
      const response = await fetch(buildApiUrl(`/api/logs/${runId}`, projectDir, { lines: 100 }), {
        headers: buildAuthHeaders(),
      })
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

  // Filter logs based on search term and log level
  const filteredLogs = useMemo(() => {
    return logs.filter((line) => {
      // Search filter
      if (searchTerm && !line.toLowerCase().includes(searchTerm.toLowerCase())) {
        return false
      }

      // Log level filter
      if (logLevel !== 'ALL') {
        const upperLine = line.toUpperCase()
        if (logLevel === 'ERROR' && !upperLine.includes('ERROR') && !upperLine.includes('FAIL')) {
          return false
        }
        if (logLevel === 'WARN' && !upperLine.includes('WARN')) {
          return false
        }
        if (logLevel === 'INFO' && !upperLine.includes('INFO')) {
          return false
        }
        if (logLevel === 'DEBUG' && !upperLine.includes('DEBUG')) {
          return false
        }
      }

      return true
    })
  }, [logs, searchTerm, logLevel])

  // Highlight search term in log line
  const highlightSearchTerm = (line: string): JSX.Element => {
    if (!searchTerm) {
      return <>{line}</>
    }

    const parts = line.split(new RegExp(`(${searchTerm})`, 'gi'))
    return (
      <>
        {parts.map((part, i) =>
          part.toLowerCase() === searchTerm.toLowerCase() ? (
            <span key={i} style={{ backgroundColor: '#ffeb3b', color: '#000' }}>
              {part}
            </span>
          ) : (
            part
          )
        )}
      </>
    )
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

      {/* Search and Filter Controls */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        <input
          type="text"
          placeholder="Search logs..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          style={{
            flex: '1',
            minWidth: '200px',
            padding: '0.5rem',
            border: '1px solid #ddd',
            borderRadius: '4px',
            fontSize: '0.875rem',
          }}
        />

        <select
          value={logLevel}
          onChange={(e) => setLogLevel(e.target.value as LogLevel)}
          style={{
            padding: '0.5rem',
            border: '1px solid #ddd',
            borderRadius: '4px',
            fontSize: '0.875rem',
            backgroundColor: '#fff',
            cursor: 'pointer',
          }}
        >
          <option value="ALL">All Levels</option>
          <option value="ERROR">Errors</option>
          <option value="WARN">Warnings</option>
          <option value="INFO">Info</option>
          <option value="DEBUG">Debug</option>
        </select>

        {searchTerm && (
          <button
            onClick={() => setSearchTerm('')}
            style={{
              padding: '0.5rem 1rem',
              border: '1px solid #ddd',
              borderRadius: '4px',
              fontSize: '0.875rem',
              backgroundColor: '#f5f5f5',
              cursor: 'pointer',
            }}
          >
            Clear
          </button>
        )}

        <button
          onClick={() => setAutoScroll(!autoScroll)}
          style={{
            padding: '0.5rem 1rem',
            border: '1px solid #ddd',
            borderRadius: '4px',
            fontSize: '0.875rem',
            backgroundColor: autoScroll ? '#4caf50' : '#f5f5f5',
            color: autoScroll ? '#fff' : '#333',
            cursor: 'pointer',
          }}
        >
          Auto-scroll {autoScroll ? 'ON' : 'OFF'}
        </button>
      </div>

      {/* Results count */}
      {(searchTerm || logLevel !== 'ALL') && (
        <div style={{ fontSize: '0.75rem', color: '#666', marginBottom: '0.5rem' }}>
          Showing {filteredLogs.length} of {logs.length} logs
        </div>
      )}

      <div
        ref={logContainerRef}
        className="log-container"
        onScroll={handleScroll}
        style={{ maxHeight: '500px', overflowY: 'auto' }}
      >
        {filteredLogs.length === 0 ? (
          <div style={{ color: '#999', textAlign: 'center', padding: '2rem' }}>
            {logs.length === 0
              ? 'No logs available'
              : 'No logs match the current filters'}
          </div>
        ) : (
          <>
            {filteredLogs.map((line, index) => (
              <div
                key={index}
                className="log-line"
                style={{
                  color: line.toUpperCase().includes('ERROR')
                    ? '#f44336'
                    : line.toUpperCase().includes('WARN')
                    ? '#ff9800'
                    : undefined,
                }}
              >
                {highlightSearchTerm(line)}
              </div>
            ))}
            <div ref={logEndRef} />
          </>
        )}
      </div>
    </div>
  )
}
