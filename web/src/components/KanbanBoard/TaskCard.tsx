/**
 * Compact task card for the Kanban board.
 */

import { useState } from 'react'
import { Box, Chip, Stack, Typography } from '@mui/material'
import ExplainModal from '../ExplainModal'

interface TaskData {
  id: string
  title: string
  task_type: string
  priority: string
  status: string
  labels: string[]
  assignee: string | null
  blocked_by: string[]
  effort: string | null
  error: string | null
}

const TYPE_ICONS: Record<string, string> = {
  feature: 'F',
  bug: 'B',
  refactor: 'R',
  research: '?',
  test: 'T',
  docs: 'D',
  security: 'S',
  performance: 'P',
  custom: 'C',
  review: 'V',
}

const PRIORITY_COLORS: Record<string, string> = {
  P0: '#ef4444',
  P1: '#f97316',
  P2: '#3b82f6',
  P3: '#9ca3af',
}

const TYPE_COLORS: Record<string, string> = {
  feature: '#3b82f6',
  bug: '#ef4444',
  refactor: '#8b5cf6',
  research: '#06b6d4',
  test: '#10b981',
  docs: '#f59e0b',
  security: '#ec4899',
  performance: '#22c55e',
  custom: '#6b7280',
  review: '#6366f1',
}

interface Props {
  task: TaskData
  projectDir?: string
  onClick: () => void
  onDragStart: () => void
}

export function TaskCard({ task, projectDir, onClick, onDragStart }: Props) {
  const isBlocked = task.blocked_by.length > 0 || task.status === 'blocked'
  const hasError = !!task.error
  const typeIcon = TYPE_ICONS[task.task_type] || '?'
  const priorityColor = PRIORITY_COLORS[task.priority] || PRIORITY_COLORS.P2
  const typeColor = TYPE_COLORS[task.task_type] || '#6b7280'
  const [showExplain, setShowExplain] = useState(false)

  return (
    <>
      <Box
        draggable
        onClick={onClick}
        onDragStart={(e) => {
          e.dataTransfer.setData('text/plain', task.id)
          onDragStart()
        }}
        sx={{
          display: 'flex',
          border: '1px solid',
          borderColor: hasError ? 'error.main' : 'divider',
          borderRadius: 1,
          cursor: 'pointer',
          overflow: 'hidden',
          bgcolor: 'background.paper',
          opacity: isBlocked ? 0.8 : 1,
          transition: 'box-shadow 120ms ease, border-color 120ms ease',
          '&:hover': {
            boxShadow: 2,
            borderColor: 'text.disabled',
          },
        }}
      >
        <Box sx={{ width: 4, flexShrink: 0, bgcolor: priorityColor }} />
        <Box sx={{ flex: 1, p: 1, minWidth: 0 }}>
          <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mb: 0.5 }}>
            <Box
              title={task.task_type}
              sx={{
                width: 18,
                height: 18,
                borderRadius: 0.5,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.625rem',
                fontWeight: 700,
                color: 'common.white',
                bgcolor: typeColor,
              }}
            >
              {typeIcon}
            </Box>
            <Typography variant="caption" color="text.disabled" sx={{ fontFamily: '"IBM Plex Mono", monospace' }}>
              {task.id.slice(-8)}
            </Typography>
            {task.effort && <Chip size="small" label={task.effort} variant="outlined" sx={{ height: 18 }} />}
          </Stack>

          <Typography
            variant="body2"
            sx={{
              fontWeight: 500,
              mb: 0.75,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              lineHeight: 1.3,
            }}
          >
            {task.title}
          </Typography>

          <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={0.5}>
            <Stack direction="row" spacing={0.5} useFlexGap flexWrap="wrap" sx={{ minWidth: 0 }}>
              {task.labels.slice(0, 3).map((label) => (
                <Chip key={label} size="small" label={label} variant="outlined" sx={{ height: 18 }} />
              ))}
            </Stack>

            <Stack direction="row" spacing={0.5} alignItems="center" sx={{ flexShrink: 0 }}>
              {isBlocked && (
                <Typography
                  component="button"
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    setShowExplain(true)
                  }}
                  sx={{
                    border: 'none',
                    background: 'none',
                    color: 'error.dark',
                    textDecoration: 'underline',
                    cursor: 'pointer',
                    fontSize: '0.75rem',
                    p: 0,
                  }}
                >
                  locked?
                </Typography>
              )}
              {task.assignee && (
                <Box
                  title={task.assignee}
                  sx={{
                    width: 20,
                    height: 20,
                    borderRadius: '50%',
                    bgcolor: 'info.main',
                    color: 'common.white',
                    fontSize: '0.6rem',
                    fontWeight: 700,
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  {task.assignee.slice(0, 2).toUpperCase()}
                </Box>
              )}
            </Stack>
          </Stack>
        </Box>
      </Box>

      {showExplain && (
        <ExplainModal
          taskId={task.id}
          projectDir={projectDir}
          onClose={() => setShowExplain(false)}
        />
      )}
    </>
  )
}
