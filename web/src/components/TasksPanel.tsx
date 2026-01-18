import { useEffect, useMemo, useState } from 'react'
import { buildApiUrl, buildAuthHeaders } from '../api'

interface TaskInfo {
  id: string
  type: string
  phase_id?: string | null
  step: string
  lifecycle: string
  status: string
  branch?: string | null
  last_error?: string | null
  last_run_id?: string | null
  worker_attempts: number
}

interface Props {
  projectDir?: string
  currentTaskId?: string
}

const normalizeTasks = (value: unknown): TaskInfo[] => {
  if (!Array.isArray(value)) return []
  const out: TaskInfo[] = []
  for (const item of value) {
    if (!item || typeof item !== 'object') continue
    const raw = item as Record<string, unknown>
    const id = typeof raw.id === 'string' ? raw.id : ''
    if (!id) continue
    out.push({
      id,
      type: typeof raw.type === 'string' ? raw.type : '',
      phase_id: typeof raw.phase_id === 'string' ? raw.phase_id : null,
      step: typeof raw.step === 'string' ? raw.step : '',
      lifecycle: typeof raw.lifecycle === 'string' ? raw.lifecycle : '',
      status: typeof raw.status === 'string' ? raw.status : '',
      branch: typeof raw.branch === 'string' ? raw.branch : null,
      last_error: typeof raw.last_error === 'string' ? raw.last_error : null,
      last_run_id: typeof raw.last_run_id === 'string' ? raw.last_run_id : null,
      worker_attempts:
        typeof raw.worker_attempts === 'number' && Number.isFinite(raw.worker_attempts)
          ? raw.worker_attempts
          : 0,
    })
  }
  return out
}

export default function TasksPanel({ projectDir, currentTaskId }: Props) {
  const [tasks, setTasks] = useState<TaskInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')

  useEffect(() => {
    fetchTasks()
    const interval = setInterval(fetchTasks, 5000)
    return () => clearInterval(interval)
  }, [projectDir])

  const fetchTasks = async () => {
    try {
      const response = await fetch(buildApiUrl('/api/tasks', projectDir), {
        headers: buildAuthHeaders(),
      })
      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`)
      }
      const data = await response.json()
      setTasks(normalizeTasks(data))
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch tasks')
    } finally {
      setLoading(false)
    }
  }

  const filteredTasks = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return tasks
    return tasks.filter((t) => {
      return (
        t.id.toLowerCase().includes(q) ||
        (t.phase_id || '').toLowerCase().includes(q) ||
        t.step.toLowerCase().includes(q) ||
        t.lifecycle.toLowerCase().includes(q) ||
        t.status.toLowerCase().includes(q)
      )
    })
  }, [tasks, query])

  const counts = useMemo(() => {
    const byLifecycle: Record<string, number> = {}
    for (const t of tasks) {
      byLifecycle[t.lifecycle] = (byLifecycle[t.lifecycle] || 0) + 1
    }
    return byLifecycle
  }, [tasks])

  return (
    <div className="card">
      <h2>Tasks</h2>

      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <input
          type="text"
          placeholder="Filter tasks..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{
            flex: 1,
            minWidth: '200px',
            padding: '0.5rem',
            border: '1px solid #ddd',
            borderRadius: '4px',
            fontSize: '0.875rem',
          }}
        />
        <button
          onClick={fetchTasks}
          style={{
            padding: '0.5rem 0.75rem',
            border: '1px solid #ddd',
            borderRadius: '4px',
            fontSize: '0.875rem',
            background: '#f5f5f5',
            cursor: 'pointer',
          }}
        >
          Refresh
        </button>
      </div>

      {loading ? (
        <div className="empty-state">
          <p>Loading tasks...</p>
        </div>
      ) : error ? (
        <div className="empty-state">
          <p style={{ color: '#c62828' }}>Error: {error}</p>
        </div>
      ) : tasks.length === 0 ? (
        <div className="empty-state">
          <p>No tasks found</p>
          <p style={{ fontSize: '0.875rem', marginTop: '0.5rem' }}>
            Generate phases to create a task queue.
          </p>
        </div>
      ) : (
        <>
          <div style={{ fontSize: '0.75rem', color: '#666', marginBottom: '0.75rem' }}>
            Total: {tasks.length}
            {Object.keys(counts).length > 0 && (
              <>
                {' • '}
                {Object.entries(counts)
                  .map(([k, v]) => `${k}: ${v}`)
                  .join(' • ')}
              </>
            )}
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
              <thead>
                <tr style={{ textAlign: 'left', borderBottom: '1px solid #eee' }}>
                  <th style={{ padding: '0.5rem' }}>Task</th>
                  <th style={{ padding: '0.5rem' }}>Phase</th>
                  <th style={{ padding: '0.5rem' }}>Step</th>
                  <th style={{ padding: '0.5rem' }}>Lifecycle</th>
                  <th style={{ padding: '0.5rem' }}>Attempts</th>
                </tr>
              </thead>
              <tbody>
                {filteredTasks.map((task) => (
                  <tr
                    key={task.id}
                    style={{
                      borderBottom: '1px solid #f5f5f5',
                      background: task.id === currentTaskId ? '#f0f7ff' : undefined,
                    }}
                  >
                    <td style={{ padding: '0.5rem', fontWeight: 600 }}>
                      {task.id}
                      {task.last_error && (
                        <div style={{ fontSize: '0.75rem', color: '#c62828', marginTop: '0.25rem' }}>
                          {task.last_error}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '0.5rem', color: '#666' }}>{task.phase_id || '-'}</td>
                    <td style={{ padding: '0.5rem', color: '#666' }}>{task.step || '-'}</td>
                    <td style={{ padding: '0.5rem', color: '#666' }}>{task.lifecycle || '-'}</td>
                    <td style={{ padding: '0.5rem', color: '#666' }}>{task.worker_attempts}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

