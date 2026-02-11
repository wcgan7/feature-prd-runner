import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Box,
  Chip,
  LinearProgress,
  Stack,
  Tab,
  Tabs,
  Typography,
  Alert,
} from '@mui/material'
import { buildApiUrl, buildAuthHeaders } from '../api'
import { useChannel } from '../contexts/WebSocketContext'
import EmptyState from './EmptyState'
import LoadingSpinner from './LoadingSpinner'

interface Props {
  projectDir?: string
}

interface AgentCost {
  agent_id: string
  name: string
  role: string
  tokens_used: number
  cost_usd: number
  elapsed_seconds: number
  budget_usd?: number
}

interface TaskBoardItem {
  id: string
  task_type: string
  step: string
  tokens_used: number
  cost_usd: number
}

type TabId = 'agent' | 'task' | 'step'

const PIPELINE_STEPS = ['plan', 'implement', 'verify', 'review', 'commit'] as const
const BUDGET_WARNING_THRESHOLD = 0.8
const COST_BREAKDOWN_STYLES = `
.cost-breakdown-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-4);
}

.cost-breakdown-summary {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: var(--spacing-3);
}

.cost-breakdown-summary-card {
  padding: var(--spacing-3);
  background: var(--color-bg-secondary);
  border-radius: var(--radius-sm);
  text-align: center;
}

.cost-breakdown-summary-value {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--color-text-primary);
}

.cost-breakdown-summary-label {
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  margin-top: var(--spacing-1);
}

.cost-breakdown-warnings {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.cost-breakdown-warning {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-3);
  background: var(--color-warning-50);
  border-left: 3px solid var(--color-warning-500);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  color: var(--color-text-primary);
}

.cost-breakdown-warning-icon {
  color: var(--color-warning-500);
  font-size: var(--text-lg);
  flex-shrink: 0;
}

.cost-breakdown-tabs {
  display: flex;
  gap: var(--spacing-1);
  border-bottom: 1px solid var(--color-border-default);
  padding-bottom: 0;
}

.cost-breakdown-tab {
  padding: var(--spacing-2) var(--spacing-3);
  border: none;
  background: none;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: all var(--transition-base);
}

.cost-breakdown-tab:hover {
  color: var(--color-text-primary);
}

.cost-breakdown-tab.active {
  color: var(--color-primary-500);
  border-bottom-color: var(--color-primary-500);
  font-weight: var(--font-semibold);
}

.cost-breakdown-tab-content {
  min-height: 100px;
}

.cost-breakdown-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
}

.cost-breakdown-empty {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  text-align: center;
  padding: var(--spacing-4);
}

.cost-breakdown-row {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.cost-breakdown-row-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--spacing-2);
}

.cost-breakdown-row-name {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
}

.cost-breakdown-agent-name {
  font-weight: var(--font-semibold);
  color: var(--color-text-primary);
  font-size: var(--text-sm);
}

.cost-breakdown-agent-role {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  padding: 1px var(--spacing-2);
  background: var(--color-bg-secondary);
  border-radius: var(--radius-full);
}

.cost-breakdown-type-name {
  font-weight: var(--font-semibold);
  color: var(--color-text-primary);
  font-size: var(--text-sm);
  text-transform: capitalize;
}

.cost-breakdown-type-count {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.cost-breakdown-step-name {
  font-weight: var(--font-semibold);
  color: var(--color-text-primary);
  font-size: var(--text-sm);
  text-transform: capitalize;
}

.cost-breakdown-row-stats {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
}

.cost-breakdown-stat-tokens {
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
}

.cost-breakdown-stat-cost {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--color-text-primary);
}

.cost-breakdown-stat-time {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.cost-breakdown-bar-track {
  width: 100%;
  height: 6px;
  background: var(--color-bg-secondary);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.cost-breakdown-bar-fill {
  height: 100%;
  background: var(--color-primary-500);
  border-radius: var(--radius-full);
  transition: width var(--transition-base);
  min-width: 2px;
}

.cost-breakdown-bar-fill.warning {
  background: var(--color-warning-500);
}
`

const normalizeAgents = (value: unknown): AgentCost[] => {
  if (!Array.isArray(value)) return []
  const out: AgentCost[] = []
  for (const item of value) {
    if (!item || typeof item !== 'object') continue
    const raw = item as Record<string, unknown>
    const agentId = typeof raw.agent_id === 'string' ? raw.agent_id : (typeof raw.id === 'string' ? raw.id : '')
    if (!agentId) continue
    out.push({
      agent_id: agentId,
      name: typeof raw.name === 'string' ? raw.name : agentId,
      role: typeof raw.role === 'string' ? raw.role : '',
      tokens_used: typeof raw.tokens_used === 'number' && Number.isFinite(raw.tokens_used) ? raw.tokens_used : 0,
      cost_usd: typeof raw.cost_usd === 'number' && Number.isFinite(raw.cost_usd) ? raw.cost_usd : 0,
      elapsed_seconds: typeof raw.elapsed_seconds === 'number' && Number.isFinite(raw.elapsed_seconds) ? raw.elapsed_seconds : 0,
      budget_usd: typeof raw.budget_usd === 'number' && Number.isFinite(raw.budget_usd) ? raw.budget_usd : undefined,
    })
  }
  return out
}

const normalizeTasks = (value: unknown): TaskBoardItem[] => {
  if (!value || typeof value !== 'object') return []

  let items: unknown[] = []
  if (Array.isArray(value)) {
    items = value
  } else {
    const raw = value as Record<string, unknown>
    if (Array.isArray(raw.columns)) {
      for (const col of raw.columns) {
        if (col && typeof col === 'object' && Array.isArray((col as Record<string, unknown>).tasks)) {
          items.push(...(col as Record<string, unknown>).tasks as unknown[])
        }
      }
    } else if (Array.isArray(raw.tasks)) {
      items = raw.tasks
    }
  }

  const out: TaskBoardItem[] = []
  for (const item of items) {
    if (!item || typeof item !== 'object') continue
    const raw = item as Record<string, unknown>
    const id = typeof raw.id === 'string' ? raw.id : ''
    if (!id) continue
    out.push({
      id,
      task_type: typeof raw.task_type === 'string' ? raw.task_type : (typeof raw.type === 'string' ? raw.type : 'unknown'),
      step: typeof raw.step === 'string' ? raw.step : '',
      tokens_used: typeof raw.tokens_used === 'number' && Number.isFinite(raw.tokens_used) ? raw.tokens_used : 0,
      cost_usd: typeof raw.cost_usd === 'number' && Number.isFinite(raw.cost_usd) ? raw.cost_usd : 0,
    })
  }
  return out
}

export default function CostBreakdown({ projectDir }: Props) {
  const [agents, setAgents] = useState<AgentCost[]>([])
  const [tasks, setTasks] = useState<TaskBoardItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<TabId>('agent')

  const fetchData = async () => {
    try {
      const [agentsRes, tasksRes] = await Promise.all([
        fetch(buildApiUrl('/api/v2/agents', projectDir), {
          headers: buildAuthHeaders(),
        }),
        fetch(buildApiUrl('/api/v2/tasks/board', projectDir), {
          headers: buildAuthHeaders(),
        }),
      ])

      if (agentsRes.ok) {
        const agentsData = await agentsRes.json()
        setAgents(normalizeAgents(agentsData))
      }

      if (tasksRes.ok) {
        const tasksData = await tasksRes.json()
        setTasks(normalizeTasks(tasksData))
      }

      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch cost data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [projectDir])

  useChannel('agents', useCallback(() => {
    fetchData()
  }, [projectDir]))

  useChannel('metrics', useCallback(() => {
    fetchData()
  }, [projectDir]))

  const totalCost = useMemo(() => agents.reduce((sum, a) => sum + a.cost_usd, 0), [agents])
  const totalTokens = useMemo(() => agents.reduce((sum, a) => sum + a.tokens_used, 0), [agents])
  const avgCostPerTask = useMemo(() => {
    if (tasks.length === 0) return 0
    const taskTotal = tasks.reduce((sum, t) => sum + t.cost_usd, 0)
    return taskTotal / tasks.length
  }, [tasks])

  const budgetWarnings = useMemo(() => {
    return agents.filter((a) => {
      if (!a.budget_usd || a.budget_usd <= 0) return false
      return a.cost_usd / a.budget_usd >= BUDGET_WARNING_THRESHOLD
    })
  }, [agents])

  const taskTypeBreakdown = useMemo(() => {
    const map: Record<string, { tokens: number; cost: number; count: number }> = {}
    for (const t of tasks) {
      const key = t.task_type || 'unknown'
      if (!map[key]) map[key] = { tokens: 0, cost: 0, count: 0 }
      map[key].tokens += t.tokens_used
      map[key].cost += t.cost_usd
      map[key].count += 1
    }
    return Object.entries(map)
      .map(([type, data]) => ({ type, ...data }))
      .sort((a, b) => b.cost - a.cost)
  }, [tasks])

  const stepBreakdown = useMemo(() => {
    const map: Record<string, { tokens: number; cost: number; count: number }> = {}
    for (const step of PIPELINE_STEPS) map[step] = { tokens: 0, cost: 0, count: 0 }
    for (const t of tasks) {
      const step = t.step || 'unknown'
      if (!map[step]) map[step] = { tokens: 0, cost: 0, count: 0 }
      map[step].tokens += t.tokens_used
      map[step].cost += t.cost_usd
      map[step].count += 1
    }
    return Object.entries(map)
      .map(([step, data]) => ({ step, ...data }))
      .sort((a, b) => b.cost - a.cost)
  }, [tasks])

  const maxAgentCost = useMemo(() => Math.max(...agents.map((a) => a.cost_usd), 0.01), [agents])
  const maxTaskTypeCost = useMemo(() => Math.max(...taskTypeBreakdown.map((t) => t.cost), 0.01), [taskTypeBreakdown])
  const maxStepCost = useMemo(() => Math.max(...stepBreakdown.map((s) => s.cost), 0.01), [stepBreakdown])

  const formatCost = (cost: number): string => `$${cost.toFixed(4)}`
  const formatTokens = (tokens: number): string => tokens.toLocaleString()
  const formatDuration = (seconds: number): string => {
    if (seconds === 0) return '0s'
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = Math.floor(seconds % 60)
    const parts = []
    if (hours > 0) parts.push(`${hours}h`)
    if (minutes > 0) parts.push(`${minutes}m`)
    if (secs > 0 || parts.length === 0) parts.push(`${secs}s`)
    return parts.join(' ')
  }

  const hasData = agents.length > 0 || tasks.length > 0

  return (
    <Box>
      <style>{COST_BREAKDOWN_STYLES}</style>
      <Typography variant="h2" sx={{ fontSize: '1.125rem', mb: 1.5 }}>Cost Breakdown</Typography>

      {loading ? (
        <LoadingSpinner label="Loading cost data..." />
      ) : error ? (
        <EmptyState
          icon={<span>&#x26A0;</span>}
          title="Error loading cost data"
          description={error}
          size="sm"
        />
      ) : !hasData ? (
        <EmptyState
          icon={<span>&#x1F4B0;</span>}
          title="No cost data available"
          description="Cost data will appear once agents start processing tasks"
          size="sm"
        />
      ) : (
        <Stack spacing={1.5} className="cost-breakdown-content">
          <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" className="cost-breakdown-summary">
            <Chip className="cost-breakdown-summary-card" label={`Total Cost ${formatCost(totalCost)}`} color="warning" variant="outlined" />
            <Chip className="cost-breakdown-summary-card" label={`Total Tokens ${formatTokens(totalTokens)}`} color="info" variant="outlined" />
            <Chip className="cost-breakdown-summary-card" label={`Avg Cost / Task ${formatCost(avgCostPerTask)}`} variant="outlined" />
          </Stack>

          {budgetWarnings.length > 0 && (
            <Stack spacing={1} className="cost-breakdown-warnings">
              {budgetWarnings.map((agent) => (
                <Alert key={agent.agent_id} className="cost-breakdown-warning" severity="warning">
                  <strong>{agent.name}</strong> has used{' '}
                  {agent.budget_usd
                    ? `${Math.round((agent.cost_usd / agent.budget_usd) * 100)}%`
                    : 'N/A'}{' '}
                  of budget ({formatCost(agent.cost_usd)} / {formatCost(agent.budget_usd || 0)})
                </Alert>
              ))}
            </Stack>
          )}

          <Tabs
            className="cost-breakdown-tabs"
            value={activeTab}
            onChange={(_, value: TabId) => setActiveTab(value)}
            variant="scrollable"
            allowScrollButtonsMobile
          >
            <Tab className="cost-breakdown-tab" value="agent" label="By Agent" />
            <Tab className="cost-breakdown-tab" value="task" label="By Task Type" />
            <Tab className="cost-breakdown-tab" value="step" label="By Step" />
          </Tabs>

          <Box className="cost-breakdown-tab-content">
            {activeTab === 'agent' && (
              <Stack spacing={1} className="cost-breakdown-list">
                {agents.length === 0 ? (
                  <Typography className="cost-breakdown-empty" color="text.secondary">No agent data available</Typography>
                ) : (
                  agents.slice().sort((a, b) => b.cost_usd - a.cost_usd).map((agent) => (
                    <Box key={agent.agent_id} className="cost-breakdown-row">
                      <Stack direction="row" justifyContent="space-between" className="cost-breakdown-row-header" sx={{ mb: 0.5 }}>
                        <Stack direction="row" spacing={1} className="cost-breakdown-row-name">
                          <Typography className="cost-breakdown-agent-name" fontWeight={600}>{agent.name}</Typography>
                          {agent.role && <Typography className="cost-breakdown-agent-role" variant="caption" color="text.secondary">{agent.role}</Typography>}
                        </Stack>
                        <Stack direction="row" spacing={1} className="cost-breakdown-row-stats">
                          <Typography className="cost-breakdown-stat-tokens" variant="caption">{formatTokens(agent.tokens_used)} tokens</Typography>
                          <Typography className="cost-breakdown-stat-cost" variant="caption">{formatCost(agent.cost_usd)}</Typography>
                          <Typography className="cost-breakdown-stat-time" variant="caption">{formatDuration(agent.elapsed_seconds)}</Typography>
                        </Stack>
                      </Stack>
                      <LinearProgress
                        className="cost-breakdown-bar-track"
                        variant="determinate"
                        value={Math.min((agent.cost_usd / maxAgentCost) * 100, 100)}
                        color={agent.budget_usd && agent.cost_usd / agent.budget_usd >= BUDGET_WARNING_THRESHOLD ? 'warning' : 'info'}
                      />
                    </Box>
                  ))
                )}
              </Stack>
            )}

            {activeTab === 'task' && (
              <Stack spacing={1} className="cost-breakdown-list">
                {taskTypeBreakdown.length === 0 ? (
                  <Typography className="cost-breakdown-empty" color="text.secondary">No task data available</Typography>
                ) : (
                  taskTypeBreakdown.map((entry) => (
                    <Box key={entry.type} className="cost-breakdown-row">
                      <Stack direction="row" justifyContent="space-between" className="cost-breakdown-row-header" sx={{ mb: 0.5 }}>
                        <Stack direction="row" spacing={1} className="cost-breakdown-row-name">
                          <Typography className="cost-breakdown-type-name" fontWeight={600}>{entry.type}</Typography>
                          <Typography className="cost-breakdown-type-count" variant="caption" color="text.secondary">{entry.count} tasks</Typography>
                        </Stack>
                        <Stack direction="row" spacing={1} className="cost-breakdown-row-stats">
                          <Typography className="cost-breakdown-stat-tokens" variant="caption">{formatTokens(entry.tokens)} tokens</Typography>
                          <Typography className="cost-breakdown-stat-cost" variant="caption">{formatCost(entry.cost)}</Typography>
                        </Stack>
                      </Stack>
                      <LinearProgress className="cost-breakdown-bar-track" variant="determinate" value={Math.min((entry.cost / maxTaskTypeCost) * 100, 100)} />
                    </Box>
                  ))
                )}
              </Stack>
            )}

            {activeTab === 'step' && (
              <Stack spacing={1} className="cost-breakdown-list">
                {stepBreakdown.length === 0 ? (
                  <Typography className="cost-breakdown-empty" color="text.secondary">No step data available</Typography>
                ) : (
                  stepBreakdown.map((entry) => (
                    <Box key={entry.step} className="cost-breakdown-row">
                      <Stack direction="row" justifyContent="space-between" className="cost-breakdown-row-header" sx={{ mb: 0.5 }}>
                        <Stack direction="row" spacing={1} className="cost-breakdown-row-name">
                          <Typography className="cost-breakdown-step-name" fontWeight={600}>{entry.step}</Typography>
                          <Typography className="cost-breakdown-type-count" variant="caption" color="text.secondary">{entry.count} tasks</Typography>
                        </Stack>
                        <Stack direction="row" spacing={1} className="cost-breakdown-row-stats">
                          <Typography className="cost-breakdown-stat-tokens" variant="caption">{formatTokens(entry.tokens)} tokens</Typography>
                          <Typography className="cost-breakdown-stat-cost" variant="caption">{formatCost(entry.cost)}</Typography>
                        </Stack>
                      </Stack>
                      <LinearProgress className="cost-breakdown-bar-track" variant="determinate" value={Math.min((entry.cost / maxStepCost) * 100, 100)} />
                    </Box>
                  ))
                )}
              </Stack>
            )}
          </Box>
        </Stack>
      )}
    </Box>
  )
}
