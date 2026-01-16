interface ProjectStatus {
  project_dir: string
  status: string
  current_task_id?: string
  current_phase_id?: string
  run_id?: string
  last_error?: string
  phases_completed: number
  phases_total: number
  tasks_ready: number
  tasks_running: number
  tasks_done: number
  tasks_blocked: number
}

interface Props {
  status: ProjectStatus | null
}

export default function RunDashboard({ status }: Props) {
  if (!status) {
    return (
      <div className="card">
        <h2>Project Overview</h2>
        <div className="empty-state">
          <p>No project data available</p>
        </div>
      </div>
    )
  }

  const progressPercent = status.phases_total > 0
    ? (status.phases_completed / status.phases_total) * 100
    : 0

  return (
    <div className="card">
      <h2>Project Overview</h2>

      <div className="stat-grid">
        <div className="stat">
          <div className="stat-value">{status.phases_completed}/{status.phases_total}</div>
          <div className="stat-label">Phases</div>
        </div>

        <div className="stat">
          <div className="stat-value" style={{ color: '#4caf50' }}>
            {status.tasks_done}
          </div>
          <div className="stat-label">Done</div>
        </div>

        <div className="stat">
          <div className="stat-value" style={{ color: '#2196f3' }}>
            {status.tasks_running}
          </div>
          <div className="stat-label">Running</div>
        </div>

        <div className="stat">
          <div className="stat-value" style={{ color: '#ff9800' }}>
            {status.tasks_ready}
          </div>
          <div className="stat-label">Ready</div>
        </div>

        <div className="stat">
          <div className="stat-value" style={{ color: '#f44336' }}>
            {status.tasks_blocked}
          </div>
          <div className="stat-label">Blocked</div>
        </div>
      </div>

      <div style={{ marginTop: '1.5rem' }}>
        <div style={{
          fontSize: '0.875rem',
          color: '#666',
          marginBottom: '0.5rem',
          display: 'flex',
          justifyContent: 'space-between'
        }}>
          <span>Overall Progress</span>
          <span>{Math.round(progressPercent)}%</span>
        </div>
        <div className="progress-bar">
          <div
            className="progress-fill"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {status.current_phase_id && (
        <div style={{ marginTop: '1.5rem', padding: '1rem', background: '#f5f5f5', borderRadius: '6px' }}>
          <div style={{ fontSize: '0.875rem', color: '#666', marginBottom: '0.25rem' }}>
            Current Phase
          </div>
          <div style={{ fontWeight: 600 }}>{status.current_phase_id}</div>
          {status.current_task_id && (
            <div style={{ fontSize: '0.875rem', color: '#666', marginTop: '0.5rem' }}>
              Task: {status.current_task_id}
            </div>
          )}
        </div>
      )}

      {status.last_error && (
        <div style={{
          marginTop: '1.5rem',
          padding: '1rem',
          background: '#fff4f4',
          borderRadius: '6px',
          borderLeft: '4px solid #f44336'
        }}>
          <div style={{ fontSize: '0.875rem', color: '#c62828', fontWeight: 600, marginBottom: '0.5rem' }}>
            Last Error
          </div>
          <div style={{ fontSize: '0.875rem', color: '#666' }}>
            {status.last_error}
          </div>
        </div>
      )}

      <div style={{ marginTop: '1.5rem', fontSize: '0.75rem', color: '#999' }}>
        Project: {status.project_dir}
      </div>
    </div>
  )
}
