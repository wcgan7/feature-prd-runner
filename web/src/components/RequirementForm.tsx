import { useState } from 'react'
import { Alert, Box, Button, MenuItem, Paper, TextField, Typography } from '@mui/material'
import { sendRequirement } from '../api'

interface Props {
  projectDir?: string
  onSent?: () => void
}

export default function RequirementForm({ projectDir, onSent }: Props) {
  const [requirement, setRequirement] = useState('')
  const [taskId, setTaskId] = useState('')
  const [priority, setPriority] = useState<'high' | 'medium' | 'low'>('medium')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!requirement.trim()) return

    setSending(true)
    setError(null)
    try {
      await sendRequirement({
        requirement: requirement.trim(),
        task_id: taskId.trim() || undefined,
        priority,
      }, projectDir)
      setRequirement('')
      setTaskId('')
      onSent?.()
    } catch (err: any) {
      setError(err.message || 'Failed to send requirement')
    } finally {
      setSending(false)
    }
  }

  return (
    <Paper
      component="form"
      onSubmit={handleSubmit}
      variant="outlined"
      sx={{ display: 'flex', flexDirection: 'column', gap: 1, p: 1.5, mb: 1 }}
    >
      <Typography variant="subtitle2" sx={{ color: 'primary.main', fontWeight: 600 }}>
        Add Requirement
      </Typography>

      <TextField
        value={requirement}
        onChange={(e) => setRequirement(e.target.value)}
        placeholder="Describe the requirement..."
        disabled={sending}
        multiline
        minRows={3}
        size="small"
      />

      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
        <TextField
          value={taskId}
          onChange={(e) => setTaskId(e.target.value)}
          placeholder="Task ID (optional)"
          disabled={sending}
          size="small"
          fullWidth
        />
        <TextField
          select
          value={priority}
          onChange={(e) => setPriority(e.target.value as any)}
          disabled={sending}
          size="small"
          sx={{ minWidth: 128 }}
        >
          <MenuItem value="high">High</MenuItem>
          <MenuItem value="medium">Medium</MenuItem>
          <MenuItem value="low">Low</MenuItem>
        </TextField>
      </Box>

      {error && (
        <Alert severity="error" sx={{ py: 0 }}>
          {error}
        </Alert>
      )}

      <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Button type="submit" variant="contained" disabled={!requirement.trim() || sending} size="small">
          {sending ? 'Sending...' : 'Add Requirement'}
        </Button>
      </Box>
    </Paper>
  )
}
