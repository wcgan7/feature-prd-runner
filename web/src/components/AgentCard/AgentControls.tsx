/**
 * AgentControls — lifecycle control buttons (pause / resume / terminate).
 * Extracted from AgentCard for independent reuse.
 */

import { Button, Stack } from '@mui/material'

interface AgentControlsProps {
  agentId: string
  status: string
  onAction: (agentId: string, action: string) => void
}

export function AgentControls({ agentId, status, onAction }: AgentControlsProps) {
  return (
    <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
      {status === 'running' && (
        <Button size="small" variant="outlined" onClick={() => onAction(agentId, 'pause')}>
          Pause
        </Button>
      )}
      {status === 'paused' && (
        <Button size="small" variant="outlined" onClick={() => onAction(agentId, 'resume')}>
          Resume
        </Button>
      )}
      {status !== 'terminated' && (
        <Button size="small" color="error" variant="outlined" onClick={() => onAction(agentId, 'terminate')}>
          Terminate
        </Button>
      )}
    </Stack>
  )
}
