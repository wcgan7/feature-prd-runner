import { useState } from 'react'
import { Alert, Box, Button, Chip, Paper, Typography } from '@mui/material'
import { fetchDryRun } from '../api'

interface Props {
  projectDir?: string
}

interface DryRunResult {
  project_dir: string
  state_dir: string
  would_write_repo_files: boolean
  would_spawn_codex: boolean
  would_run_tests: boolean
  would_checkout_branch: boolean
  next: Record<string, any> | null
  warnings: string[]
  errors: string[]
}

export default function DryRunPanel({ projectDir }: Props) {
  const [result, setResult] = useState<DryRunResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleDryRun = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchDryRun(projectDir)
      setResult(data)
    } catch (err: any) {
      setError(err.message || 'Dry run failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Paper variant="outlined" sx={{ mt: 2, p: 2 }}>
      <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">Preview Next Action</Typography>
        <Button variant="contained" size="small" onClick={handleDryRun} disabled={loading}>
          {loading ? 'Checking...' : 'Dry Run'}
        </Button>
      </Box>

      {error && <Alert severity="error">{error}</Alert>}

      {result && (
        <Box sx={{ bgcolor: 'action.hover', border: 1, borderColor: 'divider', borderRadius: 1, p: 2 }}>
          {result.next && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="subtitle2" sx={{ mb: 0.75 }}>
                Next Action
              </Typography>
              <Paper variant="outlined" sx={{ p: 1.5 }}>
                <Typography variant="body2" sx={{ fontWeight: 700 }}>
                  {result.next.action}
                </Typography>
                {result.next.task_id && (
                  <Typography variant="body2">
                    Task: <code>{result.next.task_id}</code>
                  </Typography>
                )}
                {result.next.step && (
                  <Typography variant="body2">
                    Step: <code>{result.next.step}</code>
                  </Typography>
                )}
                {result.next.description && (
                  <Typography variant="body2">{result.next.description}</Typography>
                )}
              </Paper>
            </Box>
          )}

          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
            <Chip
              size="small"
              color={result.would_spawn_codex ? 'success' : 'default'}
              label={`${result.would_spawn_codex ? '\u2713' : '\u2717'} Spawn Codex`}
            />
            <Chip
              size="small"
              color={result.would_run_tests ? 'success' : 'default'}
              label={`${result.would_run_tests ? '\u2713' : '\u2717'} Run Tests`}
            />
            <Chip
              size="small"
              color={result.would_checkout_branch ? 'success' : 'default'}
              label={`${result.would_checkout_branch ? '\u2713' : '\u2717'} Checkout Branch`}
            />
          </Box>

          {result.warnings.length > 0 && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                Warnings
              </Typography>
              <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
                {result.warnings.map((w, i) => (
                  <li key={i}>
                    <Typography variant="body2" sx={{ color: 'warning.dark' }}>
                      {w}
                    </Typography>
                  </li>
                ))}
              </ul>
            </Box>
          )}

          {result.errors.length > 0 && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                Errors
              </Typography>
              <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
                {result.errors.map((e, i) => (
                  <li key={i}>
                    <Typography variant="body2" sx={{ color: 'error.main' }}>
                      {e}
                    </Typography>
                  </li>
                ))}
              </ul>
            </Box>
          )}
        </Box>
      )}
    </Paper>
  )
}
