import { useState, useEffect } from 'react'
import {
  Alert,
  Box,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  Typography,
} from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'
import { fetchExplain } from '../api'

interface Props {
  taskId: string
  projectDir?: string
  onClose: () => void
}

export default function ExplainModal({ taskId, projectDir, onClose }: Props) {
  const [explanation, setExplanation] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchExplain(taskId, projectDir)
      .then((data) => {
        setExplanation(data.explanation)
      })
      .catch((err) => {
        setError(err.message || 'Failed to fetch explanation')
      })
      .finally(() => setLoading(false))
  }, [taskId, projectDir])

  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ pr: 6 }}>
        Why is this task blocked?
        <IconButton
          aria-label="Close"
          onClick={onClose}
          sx={{ position: 'absolute', right: 10, top: 10 }}
          size="small"
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers>
        {loading ? (
          <Typography color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>
            Loading explanation...
          </Typography>
        ) : error ? (
          <Alert severity="error">{error}</Alert>
        ) : (
          <Box
            component="pre"
            sx={{
              m: 0,
              p: 1.5,
              borderRadius: 1,
              border: '1px solid',
              borderColor: 'divider',
              bgcolor: 'background.default',
              whiteSpace: 'pre-wrap',
              fontFamily: '"IBM Plex Mono", monospace',
              fontSize: '0.85rem',
              lineHeight: 1.6,
            }}
          >
            {explanation}
          </Box>
        )}
      </DialogContent>
    </Dialog>
  )
}
