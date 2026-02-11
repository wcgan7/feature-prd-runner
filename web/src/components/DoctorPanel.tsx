import { useState } from 'react'
import { Alert, Box, Button, Chip, Paper, Stack, Typography } from '@mui/material'
import { fetchDoctor } from '../api'

interface Props {
  projectDir?: string
}

interface DoctorResult {
  checks: Record<string, { status: string; path?: string; command?: string; reason?: string }>
  warnings: string[]
  errors: string[]
  exit_code: number
}

const STATUS_ICON: Record<string, string> = {
  pass: '\u2705',
  fail: '\u274C',
  skip: '\u2796',
}

export default function DoctorPanel({ projectDir }: Props) {
  const [result, setResult] = useState<DoctorResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleDoctor = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchDoctor(projectDir, true)
      setResult(data)
    } catch (err: any) {
      setError(err.message || 'Doctor check failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Paper variant="outlined" sx={{ mt: 2, p: 2 }}>
      <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">System Check</Typography>
        <Button variant="contained" onClick={handleDoctor} disabled={loading} size="small">
          {loading ? 'Checking...' : 'Run Doctor'}
        </Button>
      </Box>

      {error && <Alert severity="error">{error}</Alert>}

      {result && (
        <>
          <Stack spacing={1}>
            {Object.entries(result.checks).map(([name, check]) => (
              <Box
                key={name}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1.5,
                  p: 1,
                  borderRadius: 1,
                  fontSize: '0.85rem',
                  bgcolor: 'action.hover',
                  border: 1,
                  borderColor: 'divider',
                }}
              >
                <Box
                  sx={{
                    fontSize: '1rem',
                    flexShrink: 0,
                    color: {
                      pass: 'success.main',
                      fail: 'error.main',
                      skip: 'text.disabled',
                    }[check.status] || 'text.primary',
                  }}
                >
                  {STATUS_ICON[check.status] || '?'}
                </Box>
                <Typography variant="body2" sx={{ fontWeight: 500, minWidth: 100 }}>
                  {name}
                </Typography>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                  {check.path || check.command || check.reason || ''}
                </Typography>
              </Box>
            ))}
          </Stack>

          {result.warnings.length > 0 && (
            <Box sx={{ mt: 2 }}>
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
            <Box sx={{ mt: 2 }}>
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

          <Chip
            label={result.exit_code === 0 ? 'All checks passed' : `${result.errors.length} error(s) found`}
            color={result.exit_code === 0 ? 'success' : 'error'}
            sx={{ mt: 2, borderRadius: 1 }}
          />
        </>
      )}
    </Paper>
  )
}
