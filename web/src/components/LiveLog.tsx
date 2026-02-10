import { useState, useEffect, useRef, useMemo } from 'react'
import { buildApiUrl, buildAuthHeaders, buildWsUrl } from '../api'
import './LiveLog.css'

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
            <span key={i} className="live-log-highlight">
              {part}
            </span>
          ) : (
            part
          )
        )}
      </>
    )
  }

  const getLineClass = (line: string): string => {
    const upperLine = line.toUpperCase()
    if (upperLine.includes('ERROR') || upperLine.includes('FAIL')) {
      return 'live-log-line-error'
    }
    if (upperLine.includes('WARN')) {
      return 'live-log-line-warning'
    }
    return ''
  }

  return (
    <div className="card">
      <div className="live-log-header">
        <h2>Live Logs</h2>
        <div className="live-log-status">
          <div className={`live-log-status-dot ${connected ? 'connected' : 'disconnected'}`} />
          <span className="live-log-status-text">
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Search and Filter Controls */}
      <div className="live-log-controls">
        <input
          type="text"
          placeholder="Search logs..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="live-log-search"
        />

        <select
          value={logLevel}
          onChange={(e) => setLogLevel(e.target.value as LogLevel)}
          className="live-log-select"
        >
          <option value="ALL">All Levels</option>
          <option value="ERROR">Errors</option>
          <option value="WARN">Warnings</option>
          <option value="INFO">Info</option>
          <option value="DEBUG">Debug</option>
        </select>

        {searchTerm && (
          <button onClick={() => setSearchTerm('')} className="live-log-btn">
            Clear
          </button>
        )}

        <button
          onClick={() => setAutoScroll(!autoScroll)}
          className={`live-log-btn live-log-btn-autoscroll ${autoScroll ? 'active' : ''}`}
        >
          Auto-scroll {autoScroll ? 'ON' : 'OFF'}
        </button>
      </div>

      {/* Results count */}
      {(searchTerm || logLevel !== 'ALL') && (
        <div className="live-log-count">
          Showing {filteredLogs.length} of {logs.length} logs
        </div>
      )}

      <div
        ref={logContainerRef}
        className="log-container live-log-container"
        onScroll={handleScroll}
      >
        {filteredLogs.length === 0 ? (
          <div className="live-log-empty">
            {logs.length === 0
              ? 'No logs available'
              : 'No logs match the current filters'}
          </div>
        ) : (
          <>
            {filteredLogs.map((line, index) => (
              <div key={index} className={`log-line ${getLineClass(line)}`}>
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
