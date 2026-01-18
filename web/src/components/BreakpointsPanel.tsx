import { useEffect, useMemo, useState } from 'react'
import { buildApiUrl, buildAuthHeaders } from '../api'

interface BreakpointInfo {
  id: string
  trigger: string
  target: string
  task_id?: string | null
  condition?: string | null
  action: string
  enabled: boolean
  hit_count: number
  created_at?: string | null
}

interface Props {
  projectDir?: string
}

const normalizeBreakpoints = (value: unknown): BreakpointInfo[] => {
  if (!Array.isArray(value)) return []
  const out: BreakpointInfo[] = []
  for (const item of value) {
    if (!item || typeof item !== 'object') continue
    const raw = item as Record<string, unknown>
    const id = typeof raw.id === 'string' ? raw.id : ''
    if (!id) continue
    out.push({
      id,
      trigger: typeof raw.trigger === 'string' ? raw.trigger : '',
      target: typeof raw.target === 'string' ? raw.target : '',
      task_id: typeof raw.task_id === 'string' ? raw.task_id : null,
      condition: typeof raw.condition === 'string' ? raw.condition : null,
      action: typeof raw.action === 'string' ? raw.action : 'pause',
      enabled: typeof raw.enabled === 'boolean' ? raw.enabled : true,
      hit_count:
        typeof raw.hit_count === 'number' && Number.isFinite(raw.hit_count)
          ? raw.hit_count
          : 0,
      created_at: typeof raw.created_at === 'string' ? raw.created_at : null,
    })
  }
  return out
}

const stepTargets = ['plan_impl', 'implement', 'verify', 'review', 'commit']
const triggerOptions = [
  { value: 'before_step', label: 'Before Step' },
  { value: 'after_step', label: 'After Step' },
]

export default function BreakpointsPanel({ projectDir }: Props) {
  const [breakpoints, setBreakpoints] = useState<BreakpointInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({
    trigger: 'before_step',
    target: 'verify',
    task_id: '',
    condition: '',
    action: 'pause',
  })

  useEffect(() => {
    fetchBreakpoints()
    const interval = setInterval(fetchBreakpoints, 5000)
    return () => clearInterval(interval)
  }, [projectDir])

  const fetchBreakpoints = async () => {
    try {
      const response = await fetch(buildApiUrl('/api/breakpoints', projectDir), {
        headers: buildAuthHeaders(),
      })
      if (!response.ok) throw new Error(`HTTP error ${response.status}`)
      const data = await response.json()
      setBreakpoints(normalizeBreakpoints(data))
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch breakpoints')
    } finally {
      setLoading(false)
    }
  }

  const createBreakpoint = async () => {
    if (creating) return
    setCreating(true)
    try {
      const response = await fetch(buildApiUrl('/api/breakpoints', projectDir), {
        method: 'POST',
        headers: buildAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          trigger: form.trigger,
          target: form.target,
          task_id: form.task_id.trim() || null,
          condition: form.condition.trim() || null,
          action: form.action,
        }),
      })
      const data = await response.json()
      if (!response.ok || !data?.success) {
        throw new Error(data?.message || `HTTP error ${response.status}`)
      }
      setForm((prev) => ({ ...prev, task_id: '', condition: '' }))
      await fetchBreakpoints()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create breakpoint')
    } finally {
      setCreating(false)
    }
  }

  const toggleBreakpoint = async (breakpointId: string) => {
    try {
      const response = await fetch(
        buildApiUrl(`/api/breakpoints/${breakpointId}/toggle`, projectDir),
        {
          method: 'POST',
          headers: buildAuthHeaders(),
        }
      )
      const data = await response.json()
      if (!response.ok || !data?.success) {
        throw new Error(data?.message || `HTTP error ${response.status}`)
      }
      await fetchBreakpoints()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to toggle breakpoint')
    }
  }

  const deleteBreakpoint = async (breakpointId: string) => {
    try {
      const response = await fetch(buildApiUrl(`/api/breakpoints/${breakpointId}`, projectDir), {
        method: 'DELETE',
        headers: buildAuthHeaders(),
      })
      const data = await response.json()
      if (!response.ok || !data?.success) {
        throw new Error(data?.message || `HTTP error ${response.status}`)
      }
      await fetchBreakpoints()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete breakpoint')
    }
  }

  const clearAll = async () => {
    try {
      const response = await fetch(buildApiUrl('/api/breakpoints', projectDir), {
        method: 'DELETE',
        headers: buildAuthHeaders(),
      })
      const data = await response.json()
      if (!response.ok || !data?.success) {
        throw new Error(data?.message || `HTTP error ${response.status}`)
      }
      await fetchBreakpoints()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to clear breakpoints')
    }
  }

  const sorted = useMemo(() => {
    return [...breakpoints].sort((a, b) => a.id.localeCompare(b.id))
  }, [breakpoints])

  return (
    <div className="card">
      <h2>Breakpoints</h2>

      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <button
          onClick={fetchBreakpoints}
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
        <button
          onClick={clearAll}
          disabled={breakpoints.length === 0}
          style={{
            padding: '0.5rem 0.75rem',
            border: '1px solid #ddd',
            borderRadius: '4px',
            fontSize: '0.875rem',
            background: breakpoints.length === 0 ? '#fafafa' : '#fff4f4',
            cursor: breakpoints.length === 0 ? 'not-allowed' : 'pointer',
            color: breakpoints.length === 0 ? '#999' : '#c62828',
          }}
        >
          Clear All
        </button>
      </div>

      {error && (
        <div style={{ marginTop: '0.75rem', color: '#c62828', fontSize: '0.875rem' }}>
          Error: {error}
        </div>
      )}

      <div style={{ marginTop: '1rem', padding: '0.75rem', background: '#f5f5f5', borderRadius: '6px' }}>
        <div style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.5rem' }}>
          Create Breakpoint
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <select
            value={form.trigger}
            onChange={(e) => setForm((prev) => ({ ...prev, trigger: e.target.value }))}
            style={{ padding: '0.5rem', border: '1px solid #ddd', borderRadius: '4px' }}
          >
            {triggerOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>

          <select
            value={form.target}
            onChange={(e) => setForm((prev) => ({ ...prev, target: e.target.value }))}
            style={{ padding: '0.5rem', border: '1px solid #ddd', borderRadius: '4px' }}
          >
            {stepTargets.map((step) => (
              <option key={step} value={step}>
                {step}
              </option>
            ))}
          </select>

          <input
            type="text"
            placeholder="Optional task_id"
            value={form.task_id}
            onChange={(e) => setForm((prev) => ({ ...prev, task_id: e.target.value }))}
            style={{
              minWidth: '180px',
              padding: '0.5rem',
              border: '1px solid #ddd',
              borderRadius: '4px',
              fontSize: '0.875rem',
            }}
          />

          <input
            type="text"
            placeholder="Optional condition (e.g. files_changed > 10)"
            value={form.condition}
            onChange={(e) => setForm((prev) => ({ ...prev, condition: e.target.value }))}
            style={{
              minWidth: '260px',
              flex: 1,
              padding: '0.5rem',
              border: '1px solid #ddd',
              borderRadius: '4px',
              fontSize: '0.875rem',
            }}
          />

          <button
            onClick={createBreakpoint}
            disabled={creating}
            style={{
              padding: '0.5rem 0.75rem',
              border: '1px solid #1976d2',
              borderRadius: '4px',
              fontSize: '0.875rem',
              background: '#1976d2',
              color: '#fff',
              cursor: creating ? 'not-allowed' : 'pointer',
              opacity: creating ? 0.7 : 1,
            }}
          >
            {creating ? 'Creating...' : 'Create'}
          </button>
        </div>

        <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: '#666' }}>
          Breakpoints pause the runner when hit. Use the Control Panel to resume the blocked task.
        </div>
      </div>

      {loading ? (
        <div className="empty-state">
          <p>Loading breakpoints...</p>
        </div>
      ) : sorted.length === 0 ? (
        <div className="empty-state">
          <p>No breakpoints set</p>
        </div>
      ) : (
        <div style={{ overflowX: 'auto', marginTop: '1rem' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
            <thead>
              <tr style={{ textAlign: 'left', borderBottom: '1px solid #eee' }}>
                <th style={{ padding: '0.5rem' }}>ID</th>
                <th style={{ padding: '0.5rem' }}>Trigger</th>
                <th style={{ padding: '0.5rem' }}>Target</th>
                <th style={{ padding: '0.5rem' }}>Task</th>
                <th style={{ padding: '0.5rem' }}>Condition</th>
                <th style={{ padding: '0.5rem' }}>Hits</th>
                <th style={{ padding: '0.5rem' }} />
              </tr>
            </thead>
            <tbody>
              {sorted.map((bp) => (
                <tr
                  key={bp.id}
                  style={{
                    borderBottom: '1px solid #f5f5f5',
                    opacity: bp.enabled ? 1 : 0.6,
                  }}
                >
                  <td style={{ padding: '0.5rem', fontFamily: 'monospace', fontSize: '0.75rem' }}>
                    {bp.id}
                  </td>
                  <td style={{ padding: '0.5rem', color: '#666' }}>{bp.trigger}</td>
                  <td style={{ padding: '0.5rem', color: '#666' }}>{bp.target}</td>
                  <td style={{ padding: '0.5rem', color: '#666' }}>{bp.task_id || '-'}</td>
                  <td style={{ padding: '0.5rem', color: '#666' }}>{bp.condition || '-'}</td>
                  <td style={{ padding: '0.5rem', color: '#666' }}>{bp.hit_count}</td>
                  <td style={{ padding: '0.5rem', whiteSpace: 'nowrap' }}>
                    <button
                      onClick={() => toggleBreakpoint(bp.id)}
                      style={{
                        padding: '0.25rem 0.5rem',
                        border: '1px solid #ddd',
                        borderRadius: '4px',
                        fontSize: '0.75rem',
                        background: '#fff',
                        cursor: 'pointer',
                        marginRight: '0.5rem',
                      }}
                    >
                      {bp.enabled ? 'Disable' : 'Enable'}
                    </button>
                    <button
                      onClick={() => deleteBreakpoint(bp.id)}
                      style={{
                        padding: '0.25rem 0.5rem',
                        border: '1px solid #ddd',
                        borderRadius: '4px',
                        fontSize: '0.75rem',
                        background: '#fff4f4',
                        cursor: 'pointer',
                        color: '#c62828',
                      }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

