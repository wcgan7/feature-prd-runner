import { useEffect, useMemo, useState } from 'react'
import { buildApiUrl, buildAuthHeaders } from '../api'

interface RunInfo {
  run_id: string
  task_id: string
  phase: string
  step: string
  status: string
  started_at: string
  updated_at: string
}

interface RunDetail extends RunInfo {
  current_task_id?: string | null
  current_phase_id?: string | null
  last_error?: string | null
}

interface Props {
  projectDir?: string
  currentRunId?: string
}

const normalizeRuns = (value: unknown): RunInfo[] => {
  if (!Array.isArray(value)) return []
  const out: RunInfo[] = []
  for (const item of value) {
    if (!item || typeof item !== 'object') continue
    const raw = item as Record<string, unknown>
    const run_id = typeof raw.run_id === 'string' ? raw.run_id : ''
    if (!run_id) continue
    out.push({
      run_id,
      task_id: typeof raw.task_id === 'string' ? raw.task_id : '',
      phase: typeof raw.phase === 'string' ? raw.phase : '',
      step: typeof raw.step === 'string' ? raw.step : '',
      status: typeof raw.status === 'string' ? raw.status : '',
      started_at: typeof raw.started_at === 'string' ? raw.started_at : '',
      updated_at: typeof raw.updated_at === 'string' ? raw.updated_at : '',
    })
  }
  return out
}

const normalizeRunDetail = (value: unknown): RunDetail | null => {
  if (!value || typeof value !== 'object') return null
  const raw = value as Record<string, unknown>
  const run_id = typeof raw.run_id === 'string' ? raw.run_id : ''
  if (!run_id) return null
  return {
    run_id,
    task_id: typeof raw.task_id === 'string' ? raw.task_id : '',
    phase: typeof raw.phase === 'string' ? raw.phase : '',
    step: typeof raw.step === 'string' ? raw.step : '',
    status: typeof raw.status === 'string' ? raw.status : '',
    started_at: typeof raw.started_at === 'string' ? raw.started_at : '',
    updated_at: typeof raw.updated_at === 'string' ? raw.updated_at : '',
    current_task_id: typeof raw.current_task_id === 'string' ? raw.current_task_id : null,
    current_phase_id: typeof raw.current_phase_id === 'string' ? raw.current_phase_id : null,
    last_error: typeof raw.last_error === 'string' ? raw.last_error : null,
  }
}

export default function RunsPanel({ projectDir, currentRunId }: Props) {
  const [runs, setRuns] = useState<RunInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [runDetail, setRunDetail] = useState<RunDetail | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)

  useEffect(() => {
    fetchRuns()
    const interval = setInterval(fetchRuns, 10000)
    return () => clearInterval(interval)
  }, [projectDir])

  const fetchRuns = async () => {
    try {
      const response = await fetch(buildApiUrl('/api/runs', projectDir, { limit: 25 }), {
        headers: buildAuthHeaders(),
      })
      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`)
      }
      const data = await response.json()
      setRuns(normalizeRuns(data))
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch runs')
    } finally {
      setLoading(false)
    }
  }

  const fetchRunDetail = async (runId: string) => {
    setDetailError(null)
    try {
      const response = await fetch(buildApiUrl(`/api/runs/${runId}`, projectDir), {
        headers: buildAuthHeaders(),
      })
      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`)
      }
      const data = await response.json()
      setRunDetail(normalizeRunDetail(data))
    } catch (err) {
      setDetailError(err instanceof Error ? err.message : 'Failed to fetch run details')
      setRunDetail(null)
    }
  }

  const sortedRuns = useMemo(() => {
    return [...runs].sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || ''))
  }, [runs])

  return (
    <div className="card">
      <h2>Recent Runs</h2>

      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <button
          onClick={fetchRuns}
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
        {currentRunId && (
          <div style={{ fontSize: '0.75rem', color: '#666' }}>
            Active run: <span style={{ fontFamily: 'monospace' }}>{currentRunId}</span>
          </div>
        )}
      </div>

      {loading ? (
        <div className="empty-state">
          <p>Loading runs...</p>
        </div>
      ) : error ? (
        <div className="empty-state">
          <p style={{ color: '#c62828' }}>Error: {error}</p>
        </div>
      ) : sortedRuns.length === 0 ? (
        <div className="empty-state">
          <p>No runs found</p>
          <p style={{ fontSize: '0.875rem', marginTop: '0.5rem' }}>
            Runs will appear after the first execution.
          </p>
        </div>
      ) : (
        <>
          <div style={{ overflowX: 'auto', marginTop: '1rem' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
              <thead>
                <tr style={{ textAlign: 'left', borderBottom: '1px solid #eee' }}>
                  <th style={{ padding: '0.5rem' }}>Run</th>
                  <th style={{ padding: '0.5rem' }}>Task</th>
                  <th style={{ padding: '0.5rem' }}>Phase</th>
                  <th style={{ padding: '0.5rem' }}>Step</th>
                  <th style={{ padding: '0.5rem' }}>Status</th>
                  <th style={{ padding: '0.5rem' }} />
                </tr>
              </thead>
              <tbody>
                {sortedRuns.map((run) => (
                  <tr
                    key={run.run_id}
                    style={{
                      borderBottom: '1px solid #f5f5f5',
                      background: run.run_id === currentRunId ? '#f1f8f4' : undefined,
                    }}
                  >
                    <td style={{ padding: '0.5rem', fontFamily: 'monospace', fontSize: '0.75rem' }}>
                      {run.run_id}
                    </td>
                    <td style={{ padding: '0.5rem', color: '#666' }}>{run.task_id || '-'}</td>
                    <td style={{ padding: '0.5rem', color: '#666' }}>{run.phase || '-'}</td>
                    <td style={{ padding: '0.5rem', color: '#666' }}>{run.step || '-'}</td>
                    <td style={{ padding: '0.5rem', color: '#666' }}>{run.status || '-'}</td>
                    <td style={{ padding: '0.5rem' }}>
                      <button
                        onClick={() => {
                          setSelectedRunId(run.run_id)
                          void fetchRunDetail(run.run_id)
                        }}
                        style={{
                          padding: '0.25rem 0.5rem',
                          border: '1px solid #ddd',
                          borderRadius: '4px',
                          fontSize: '0.75rem',
                          background: '#fff',
                          cursor: 'pointer',
                        }}
                      >
                        Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {selectedRunId && (
            <div style={{ marginTop: '1rem', padding: '0.75rem', background: '#f5f5f5', borderRadius: '6px' }}>
              <div style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                Run Details
              </div>
              {detailError ? (
                <div style={{ color: '#c62828', fontSize: '0.875rem' }}>Error: {detailError}</div>
              ) : runDetail ? (
                <>
                  <div style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: '#333' }}>
                    {runDetail.run_id}
                  </div>
                  <div style={{ fontSize: '0.875rem', color: '#666', marginTop: '0.25rem' }}>
                    Status: <strong>{runDetail.status}</strong>
                  </div>
                  {runDetail.last_error && (
                    <div style={{ fontSize: '0.875rem', color: '#c62828', marginTop: '0.5rem' }}>
                      Last error: {runDetail.last_error}
                    </div>
                  )}
                  <div style={{ fontSize: '0.75rem', color: '#666', marginTop: '0.5rem' }}>
                    Current task: {runDetail.current_task_id || '-'} • Current phase: {runDetail.current_phase_id || '-'}
                  </div>
                </>
              ) : (
                <div style={{ fontSize: '0.875rem', color: '#666' }}>Loading...</div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

