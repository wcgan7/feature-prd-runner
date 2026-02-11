import { useState } from 'react'
import { buildApiUrl, buildAuthHeaders } from '../api'
import { useToast } from '../contexts/ToastContext'
import './ControlPanel.css'

interface Props {
  currentTaskId?: string
  currentPhaseId?: string
  status?: string
  projectDir?: string
}

type ControlAction = 'retry' | 'skip' | 'resume' | 'stop'

export default function ControlPanel({ currentTaskId, currentPhaseId, status, projectDir }: Props) {
  const [loading, setLoading] = useState<ControlAction | null>(null)
  const [selectedStep, setSelectedStep] = useState('plan_impl')
  const toast = useToast()

  const steps = [
    { value: 'plan_impl', label: 'Plan Implementation' },
    { value: 'implement', label: 'Implement' },
    { value: 'verify', label: 'Verify' },
    { value: 'review', label: 'Review' },
    { value: 'commit', label: 'Commit' },
  ]

  const executeAction = async (action: ControlAction) => {
    if (!currentTaskId && action !== 'stop') {
      toast.error('No active task to control')
      return
    }

    setLoading(action)

    try {
      const body: any = {
        action,
        task_id: currentTaskId || null,
        params: action === 'retry' ? { step: selectedStep } : null,
      }

      const response = await fetch(buildApiUrl('/api/control', projectDir), {
        method: 'POST',
        headers: buildAuthHeaders({
          'Content-Type': 'application/json',
        }),
        body: JSON.stringify(body),
      })

      const data = await response.json()

      if (data.success) {
        toast.success(data.message || `${action} completed successfully`)
      } else {
        toast.error(data.message || `${action} failed`)
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to execute action')
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="card">
      <h2>Run Control</h2>

      {/* Status Display */}
      {currentTaskId && (
        <div className="control-panel-status">
          <div className="control-panel-status-item">
            <strong>Current Task:</strong> {currentTaskId}
          </div>
          {currentPhaseId && (
            <div className="control-panel-status-item">
              <strong>Phase:</strong> {currentPhaseId}
            </div>
          )}
          {status && (
            <div className="control-panel-status-item">
              <strong>Status:</strong> {status}
            </div>
          )}
        </div>
      )}

      {/* Step Selector for Retry */}
      <div className="control-panel-step-selector">
        <label className="control-panel-label">Retry from step:</label>
        <select
          value={selectedStep}
          onChange={(e) => setSelectedStep(e.target.value)}
          className="control-panel-select"
        >
          {steps.map((step) => (
            <option key={step.value} value={step.value}>
              {step.label}
            </option>
          ))}
        </select>
      </div>

      {/* Control Buttons */}
      <div className="control-panel-buttons">
        <button
          onClick={() => executeAction('retry')}
          disabled={loading !== null || !currentTaskId}
          className={`control-btn control-btn-retry ${loading === 'retry' ? 'loading' : ''}`}
        >
          {loading === 'retry' ? 'Retrying...' : 'Retry Task'}
        </button>

        <button
          onClick={() => executeAction('skip')}
          disabled={loading !== null || !currentTaskId}
          className={`control-btn control-btn-skip ${loading === 'skip' ? 'loading' : ''}`}
        >
          {loading === 'skip' ? 'Skipping...' : 'Skip Step'}
        </button>

        <button
          onClick={() => executeAction('resume')}
          disabled={loading !== null || !currentTaskId}
          className={`control-btn control-btn-resume ${loading === 'resume' ? 'loading' : ''}`}
        >
          {loading === 'resume' ? 'Resuming...' : 'Resume Task'}
        </button>

        <button
          onClick={() => executeAction('stop')}
          disabled={loading !== null}
          className={`control-btn control-btn-stop ${loading === 'stop' ? 'loading' : ''}`}
        >
          {loading === 'stop' ? 'Stopping...' : 'Stop Run'}
        </button>
      </div>

      {/* Help Text */}
      <div className="control-panel-help">
        <strong>Controls:</strong>
        <ul>
          <li><strong>Retry:</strong> Restart task from selected step</li>
          <li><strong>Skip:</strong> Skip current step and move to next</li>
          <li><strong>Resume:</strong> Resume a blocked task</li>
          <li><strong>Stop:</strong> Send stop signal to running process</li>
        </ul>
      </div>
    </div>
  )
}
