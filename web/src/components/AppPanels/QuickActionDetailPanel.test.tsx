import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { QuickActionDetailPanel } from './QuickActionDetailPanel'

describe('QuickActionDetailPanel', () => {
  it('renders empty state when there are no quick actions', () => {
    render(
      <QuickActionDetailPanel
        quickActions={[]}
        selectedQuickActionId=""
        selectedQuickActionDetail={null}
        selectedQuickActionLoading={false}
        selectedQuickActionError=""
        onSelectQuickAction={vi.fn()}
        onPromoteQuickAction={vi.fn()}
        onRefreshQuickActionDetail={vi.fn()}
        onRetryLoadQuickActionDetail={vi.fn()}
      />
    )

    expect(screen.getByText(/No quick actions yet/i)).toBeInTheDocument()
  })

  it('supports view and promote actions from quick action rows', () => {
    const onSelectQuickAction = vi.fn()
    const onPromoteQuickAction = vi.fn()

    render(
      <QuickActionDetailPanel
        quickActions={[
          { id: 'qa-1', prompt: 'Run checks', status: 'running', kind: 'agent', promoted_task_id: null },
          { id: 'qa-2', prompt: 'Cleanup', status: 'failed', kind: 'shortcut', promoted_task_id: 'task-7' },
        ]}
        selectedQuickActionId=""
        selectedQuickActionDetail={null}
        selectedQuickActionLoading={false}
        selectedQuickActionError=""
        onSelectQuickAction={onSelectQuickAction}
        onPromoteQuickAction={onPromoteQuickAction}
        onRefreshQuickActionDetail={vi.fn()}
        onRetryLoadQuickActionDetail={vi.fn()}
      />
    )

    const viewButtons = screen.getAllByRole('button', { name: /^View$/i })
    fireEvent.click(viewButtons[0])
    expect(onSelectQuickAction).toHaveBeenCalledWith('qa-1')

    const promoteButtons = screen.getAllByRole('button', { name: /Promote|Promoted/i })
    fireEvent.click(promoteButtons[0])
    expect(onPromoteQuickAction).toHaveBeenCalledWith('qa-1')
    expect(promoteButtons[1]).toBeDisabled()
  })

  it('supports retry and refresh in the detail panel', () => {
    const onRefreshQuickActionDetail = vi.fn()
    const onRetryLoadQuickActionDetail = vi.fn()

    render(
      <QuickActionDetailPanel
        quickActions={[{ id: 'qa-1', prompt: 'Run checks', status: 'completed', kind: 'agent' }]}
        selectedQuickActionId="qa-1"
        selectedQuickActionDetail={{
          id: 'qa-1',
          prompt: 'Run checks',
          status: 'completed',
          kind: 'agent',
          command: 'npm test',
          exit_code: 0,
          started_at: '2026-02-13T00:00:00Z',
          finished_at: '2026-02-13T00:00:01Z',
          result_summary: 'Done.',
          promoted_task_id: null,
        }}
        selectedQuickActionLoading={true}
        selectedQuickActionError="Failed to load quick action detail"
        onSelectQuickAction={vi.fn()}
        onPromoteQuickAction={vi.fn()}
        onRefreshQuickActionDetail={onRefreshQuickActionDetail}
        onRetryLoadQuickActionDetail={onRetryLoadQuickActionDetail}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: /Retry/i }))
    expect(onRetryLoadQuickActionDetail).toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: /Refresh detail/i }))
    expect(onRefreshQuickActionDetail).toHaveBeenCalled()
  })
})
