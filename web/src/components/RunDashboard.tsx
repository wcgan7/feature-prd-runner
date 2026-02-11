import {
  Alert,
  Box,
  Chip,
  LinearProgress,
  Stack,
  Typography,
} from '@mui/material'

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
      <Box>
        <Typography variant="h2" sx={{ fontSize: '1.125rem', mb: 1.25 }}>Project Overview</Typography>
        <Typography color="text.secondary">No project data available</Typography>
      </Box>
    )
  }

  const progressPercent = status.phases_total > 0
    ? (status.phases_completed / status.phases_total) * 100
    : 0

  return (
    <Box>
      <Typography variant="h2" sx={{ fontSize: '1.125rem', mb: 1.25 }}>Project Overview</Typography>

      <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" sx={{ mb: 2 }}>
        <Chip label={`Phases ${status.phases_completed}/${status.phases_total}`} variant="outlined" />
        <Chip label={`Done ${status.tasks_done}`} color="success" variant="outlined" />
        <Chip label={`Running ${status.tasks_running}`} color="info" variant="outlined" />
        <Chip label={`Ready ${status.tasks_ready}`} color="warning" variant="outlined" />
        <Chip label={`Blocked ${status.tasks_blocked}`} color="error" variant="outlined" />
      </Stack>

      <Box sx={{ mb: 2 }}>
        <Stack direction="row" justifyContent="space-between" sx={{ mb: 0.5 }}>
          <Typography variant="body2" color="text.secondary">Overall Progress</Typography>
          <Typography variant="body2" color="text.secondary">{Math.round(progressPercent)}%</Typography>
        </Stack>
        <LinearProgress variant="determinate" value={progressPercent} />
      </Box>

      {status.current_phase_id && (
        <Alert severity="info" sx={{ mb: 1.25 }}>
          Current phase: <strong>{status.current_phase_id}</strong>
          {status.current_task_id ? ` | Task: ${status.current_task_id}` : ''}
        </Alert>
      )}

      {status.last_error && (
        <Alert severity="error" sx={{ mb: 1.25 }}>
          Last error: {status.last_error}
        </Alert>
      )}

      <Typography variant="caption" color="text.secondary" sx={{ wordBreak: 'break-word' }}>
        Project: {status.project_dir}
      </Typography>
    </Box>
  )
}
