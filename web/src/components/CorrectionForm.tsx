import { useState } from 'react'
import { Alert, Box, Button, Stack, TextField, Typography } from '@mui/material'
import { sendCorrection } from '../api'

interface Props {
  taskId: string
  projectDir?: string
  onSent?: () => void
}

export default function CorrectionForm({ taskId, projectDir, onSent }: Props) {
  const [issue, setIssue] = useState('')
  const [filePath, setFilePath] = useState('')
  const [suggestedFix, setSuggestedFix] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!issue.trim()) return

    setSending(true)
    setError(null)
    try {
      await sendCorrection(taskId, {
        issue: issue.trim(),
        file_path: filePath.trim() || undefined,
        suggested_fix: suggestedFix.trim() || undefined,
      }, projectDir)
      setIssue('')
      setFilePath('')
      setSuggestedFix('')
      onSent?.()
    } catch (err: any) {
      setError(err.message || 'Failed to send correction')
    } finally {
      setSending(false)
    }
  }

  return (
    <Box
      component="form"
      onSubmit={handleSubmit}
      sx={{ p: 1.25, bgcolor: 'background.default', border: '1px solid', borderColor: 'divider', borderRadius: 1.5 }}
    >
      <Typography variant="subtitle2" color="error.main" sx={{ mb: 1 }}>
        Send Correction
      </Typography>

      <Stack spacing={1}>
        <TextField
          value={issue}
          onChange={(e) => setIssue(e.target.value)}
          placeholder="Describe the issue..."
          disabled={sending}
          multiline
          minRows={3}
          fullWidth
          size="small"
        />

        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
          <TextField
            value={filePath}
            onChange={(e) => setFilePath(e.target.value)}
            placeholder="File path (optional)"
            disabled={sending}
            fullWidth
            size="small"
          />
          <TextField
            value={suggestedFix}
            onChange={(e) => setSuggestedFix(e.target.value)}
            placeholder="Suggested fix (optional)"
            disabled={sending}
            fullWidth
            size="small"
          />
        </Stack>

        {error && <Alert severity="error">{error}</Alert>}

        <Stack direction="row" justifyContent="flex-end">
          <Button type="submit" variant="contained" color="error" disabled={!issue.trim() || sending}>
            {sending ? 'Sending...' : 'Send Correction'}
          </Button>
        </Stack>
      </Stack>
    </Box>
  )
}
