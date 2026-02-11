import { useState, useEffect } from 'react'
import { fetchWorkers, testWorker } from '../api'

const WORKERS_PANEL_STYLES = `
.workers-panel { margin-top: 1rem; }
.workers-panel h2 { margin: 0 0 1rem; }
.workers-default { font-size: 0.85rem; color: var(--text-secondary, #6b7280); margin-bottom: 1rem; }
.workers-default strong { color: var(--text-primary, #1f2937); }
.workers-routing { margin-bottom: 1rem; }
.workers-routing h4 { margin: 0 0 0.5rem; font-size: 0.9rem; }
.workers-routing-table { display: grid; grid-template-columns: auto 1fr; gap: 0.25rem 1rem; font-size: 0.85rem; }
.workers-routing-step { font-family: var(--font-mono, monospace); font-weight: 500; }
.workers-routing-provider { color: var(--text-secondary, #6b7280); }
.workers-list h4 { margin: 0 0 0.5rem; font-size: 0.9rem; }
.workers-provider { display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem; border: 1px solid var(--border-color, #e5e7eb); border-radius: 6px; margin-bottom: 0.5rem; background: var(--bg-secondary, #f9fafb); }
.workers-provider-info { flex: 1; }
.workers-provider-name { font-weight: 600; font-size: 0.9rem; }
.workers-provider-type { font-size: 0.75rem; padding: 0.1rem 0.4rem; border-radius: 3px; background: var(--bg-primary, #fff); border: 1px solid var(--border-color, #e5e7eb); margin-left: 0.5rem; }
.workers-provider-detail { font-size: 0.8rem; color: var(--text-secondary, #6b7280); font-family: var(--font-mono, monospace); }
.workers-test-btn { padding: 0.35rem 0.75rem; font-size: 0.8rem; border: 1px solid var(--border-color, #e5e7eb); border-radius: 4px; cursor: pointer; background: var(--bg-primary, #fff); }
.workers-test-result { font-size: 0.8rem; padding: 0.25rem 0.5rem; border-radius: 4px; }
.workers-test-result.success { background: #dcfce7; color: #166534; }
.workers-test-result.fail { background: #fee2e2; color: #991b1b; }
.workers-error { color: #dc2626; font-size: 0.85rem; }
`

interface Props {
  projectDir?: string
}

interface WorkerInfo {
  name: string
  type: string
  detail: string
  model?: string
  endpoint?: string
  command?: string
}

interface WorkersData {
  default_worker: string
  routing: Record<string, string>
  providers: WorkerInfo[]
  config_error?: string
}

interface TestResult {
  success: boolean
  message: string
}

export default function WorkersPanel({ projectDir }: Props) {
  const [data, setData] = useState<WorkersData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [testResults, setTestResults] = useState<Record<string, TestResult>>({})
  const [testing, setTesting] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    fetchWorkers(projectDir)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [projectDir])

  const handleTest = async (workerName: string) => {
    setTesting(workerName)
    try {
      const result = await testWorker(workerName, projectDir)
      setTestResults((prev) => ({ ...prev, [workerName]: result }))
    } catch (err: any) {
      setTestResults((prev) => ({
        ...prev,
        [workerName]: { success: false, message: err.message },
      }))
    } finally {
      setTesting(null)
    }
  }

  if (loading) return <div className="card workers-panel"><style>{WORKERS_PANEL_STYLES}</style><h2>Workers</h2><p>Loading...</p></div>
  if (error) return <div className="card workers-panel"><style>{WORKERS_PANEL_STYLES}</style><h2>Workers</h2><p className="workers-error">{error}</p></div>
  if (!data) return null

  return (
    <div className="card workers-panel">
      <style>{WORKERS_PANEL_STYLES}</style>
      <h2>Workers</h2>

      {data.config_error && (
        <p className="workers-error">Config error: {data.config_error}</p>
      )}

      <div className="workers-default">
        Default worker: <strong>{data.default_worker}</strong>
      </div>

      {Object.keys(data.routing).length > 0 && (
        <div className="workers-routing">
          <h4>Routing</h4>
          <div className="workers-routing-table">
            {Object.entries(data.routing).map(([step, provider]) => (
              <div key={step} style={{ display: 'contents' }}>
                <span className="workers-routing-step">{step}</span>
                <span className="workers-routing-provider">{provider}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="workers-list">
        <h4>Providers</h4>
        {data.providers.map((p) => (
          <div className="workers-provider" key={p.name}>
            <div className="workers-provider-info">
              <div>
                <span className="workers-provider-name">{p.name}</span>
                <span className="workers-provider-type">{p.type}</span>
              </div>
              {p.detail && <div className="workers-provider-detail">{p.detail}</div>}
            </div>
            <button
              className="workers-test-btn"
              onClick={() => handleTest(p.name)}
              disabled={testing === p.name}
            >
              {testing === p.name ? 'Testing...' : 'Test'}
            </button>
            {testResults[p.name] && (
              <span className={`workers-test-result ${testResults[p.name].success ? 'success' : 'fail'}`}>
                {testResults[p.name].success ? '\u2713' : '\u2717'} {testResults[p.name].message}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
