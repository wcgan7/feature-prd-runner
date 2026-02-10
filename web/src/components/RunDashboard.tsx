import './RunDashboard.css'

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

        <div className="stat run-dashboard-stat-done">
          <div className="stat-value">{status.tasks_done}</div>
          <div className="stat-label">Done</div>
        </div>

        <div className="stat run-dashboard-stat-running">
          <div className="stat-value">{status.tasks_running}</div>
          <div className="stat-label">Running</div>
        </div>

        <div className="stat run-dashboard-stat-ready">
          <div className="stat-value">{status.tasks_ready}</div>
          <div className="stat-label">Ready</div>
        </div>

        <div className="stat run-dashboard-stat-blocked">
          <div className="stat-value">{status.tasks_blocked}</div>
          <div className="stat-label">Blocked</div>
        </div>
      </div>

      <div className="run-dashboard-progress-section">
        <div className="run-dashboard-progress-header">
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
        <div className="run-dashboard-current-phase">
          <div className="run-dashboard-current-phase-label">Current Phase</div>
          <div className="run-dashboard-current-phase-value">{status.current_phase_id}</div>
          {status.current_task_id && (
            <div className="run-dashboard-current-task">
              Task: {status.current_task_id}
            </div>
          )}
        </div>
      )}

      {status.last_error && (
        <div className="run-dashboard-error">
          <div className="run-dashboard-error-label">Last Error</div>
          <div className="run-dashboard-error-message">{status.last_error}</div>
        </div>
      )}

      <div className="run-dashboard-project-path">
        Project: {status.project_dir}
      </div>
    </div>
  )
}
