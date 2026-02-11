import { Box, Typography } from '@mui/material'

/**
 * AgentStream — renders the tail of an agent's output log.
 * Extracted from AgentCard for independent reuse.
 */

interface AgentStreamProps {
  outputTail: string[]
  maxLines?: number
}

export function AgentStream({ outputTail, maxLines = 10 }: AgentStreamProps) {
  if (outputTail.length === 0) {
    return null
  }

  return (
    <Box sx={{ mt: 1.5 }}>
      <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: 0.5 }}>
        Output
      </Typography>
      <Box
        component="pre"
        sx={{
          m: 0,
          mt: 0.5,
          p: 1.5,
          borderRadius: 1,
          bgcolor: 'grey.900',
          color: 'grey.200',
          fontFamily: '"IBM Plex Mono", monospace',
          fontSize: '0.75rem',
          maxHeight: 160,
          overflowY: 'auto',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-all',
        }}
      >
        {outputTail.slice(-maxLines).join('\n')}
      </Box>
    </Box>
  )
}
