import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { TaskExplorerPanel } from './TaskExplorerPanel'

describe('TaskExplorerPanel', () => {
  it('renders empty state when no items are present', () => {
    render(
      <TaskExplorerPanel
        query=""
        status=""
        taskType=""
        priority=""
        onlyBlocked={false}
        loading={false}
        error=""
        items={[]}
        page={1}
        pageSize={6}
        totalItems={0}
        statusOptions={['ready', 'blocked']}
        typeOptions={['feature', 'bug']}
        onQueryChange={vi.fn()}
        onStatusChange={vi.fn()}
        onTypeChange={vi.fn()}
        onPriorityChange={vi.fn()}
        onOnlyBlockedChange={vi.fn()}
        onPageChange={vi.fn()}
        onPageSizeChange={vi.fn()}
        onSelectTask={vi.fn()}
        onRetry={vi.fn()}
      />
    )

    expect(screen.getByText(/No matching tasks/i)).toBeInTheDocument()
  })

  it('wires filter and pagination callbacks', () => {
    const onQueryChange = vi.fn()
    const onStatusChange = vi.fn()
    const onTypeChange = vi.fn()
    const onPriorityChange = vi.fn()
    const onOnlyBlockedChange = vi.fn()
    const onPageChange = vi.fn()
    const onPageSizeChange = vi.fn()
    const onSelectTask = vi.fn()

    render(
      <TaskExplorerPanel
        query=""
        status=""
        taskType=""
        priority=""
        onlyBlocked={false}
        loading={false}
        error=""
        items={[{ id: 'task-1', title: 'Task 1', status: 'ready', priority: 'P2' }]}
        page={2}
        pageSize={6}
        totalItems={18}
        statusOptions={['ready', 'blocked']}
        typeOptions={['feature', 'bug']}
        onQueryChange={onQueryChange}
        onStatusChange={onStatusChange}
        onTypeChange={onTypeChange}
        onPriorityChange={onPriorityChange}
        onOnlyBlockedChange={onOnlyBlockedChange}
        onPageChange={onPageChange}
        onPageSizeChange={onPageSizeChange}
        onSelectTask={onSelectTask}
        onRetry={vi.fn()}
      />
    )

    fireEvent.change(screen.getByLabelText(/Task explorer search/i), { target: { value: 'task' } })
    expect(onQueryChange).toHaveBeenCalledWith('task')

    const selects = screen.getAllByRole('combobox')
    fireEvent.change(selects[0], { target: { value: 'blocked' } })
    expect(onStatusChange).toHaveBeenCalledWith('blocked')

    fireEvent.change(selects[1], { target: { value: 'bug' } })
    expect(onTypeChange).toHaveBeenCalledWith('bug')

    fireEvent.change(selects[2], { target: { value: 'P1' } })
    expect(onPriorityChange).toHaveBeenCalledWith('P1')

    fireEvent.click(screen.getByLabelText(/Only blocked/i))
    expect(onOnlyBlockedChange).toHaveBeenCalledWith(true)

    fireEvent.click(screen.getByRole('button', { name: /Task 1/i }))
    expect(onSelectTask).toHaveBeenCalledWith('task-1')

    fireEvent.click(screen.getByRole('button', { name: /^Prev$/i }))
    expect(onPageChange).toHaveBeenCalledWith(1)

    fireEvent.click(screen.getByRole('button', { name: /^Next$/i }))
    expect(onPageChange).toHaveBeenCalledWith(3)

    fireEvent.change(screen.getByLabelText(/Per page/i), { target: { value: '10' } })
    expect(onPageSizeChange).toHaveBeenCalledWith(10)
  })

  it('shows retry UI when explorer request fails', () => {
    const onRetry = vi.fn()
    render(
      <TaskExplorerPanel
        query=""
        status=""
        taskType=""
        priority=""
        onlyBlocked={false}
        loading={false}
        error="Failed to load explorer"
        items={[]}
        page={1}
        pageSize={6}
        totalItems={0}
        statusOptions={['ready', 'blocked']}
        typeOptions={['feature', 'bug']}
        onQueryChange={vi.fn()}
        onStatusChange={vi.fn()}
        onTypeChange={vi.fn()}
        onPriorityChange={vi.fn()}
        onOnlyBlockedChange={vi.fn()}
        onPageChange={vi.fn()}
        onPageSizeChange={vi.fn()}
        onSelectTask={vi.fn()}
        onRetry={onRetry}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: /Retry/i }))
    expect(onRetry).toHaveBeenCalled()
  })
})
