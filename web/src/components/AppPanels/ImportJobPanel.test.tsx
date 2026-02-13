import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { ImportJobPanel } from './ImportJobPanel'

describe('ImportJobPanel', () => {
  it('renders empty states when no import data is available', () => {
    render(
      <ImportJobPanel
        importJobId=""
        importPreview={null}
        recentImportJobIds={[]}
        selectedImportJobId=""
        selectedImportJob={null}
        selectedImportJobLoading={false}
        selectedImportJobError=""
        selectedCreatedTaskIds={[]}
        onCommitImport={vi.fn()}
        onSelectImportJob={vi.fn()}
        onRefreshImportJob={vi.fn()}
        onRetryLoadImportJob={vi.fn()}
      />
    )

    expect(screen.getByText(/No import jobs yet/i)).toBeInTheDocument()
  })

  it('supports preview, selection, commit, retry, and refresh actions', () => {
    const onCommitImport = vi.fn()
    const onSelectImportJob = vi.fn()
    const onRefreshImportJob = vi.fn()
    const onRetryLoadImportJob = vi.fn()

    render(
      <ImportJobPanel
        importJobId="job-1"
        importPreview={{
          nodes: [{ id: 'task-a', title: 'Task A', priority: 'P2' }],
          edges: [{ from: 'task-a', to: 'task-b' }],
        }}
        recentImportJobIds={['job-1', 'job-2']}
        selectedImportJobId="job-1"
        selectedImportJob={{
          id: 'job-1',
          title: 'Import tasks',
          status: 'preview_ready',
          created_at: '2026-02-13T00:00:00Z',
          tasks: [{ title: 'Task A', priority: 'P2' }],
        }}
        selectedImportJobLoading={false}
        selectedImportJobError="Load failed"
        selectedCreatedTaskIds={['task-a']}
        onCommitImport={onCommitImport}
        onSelectImportJob={onSelectImportJob}
        onRefreshImportJob={onRefreshImportJob}
        onRetryLoadImportJob={onRetryLoadImportJob}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: /View details/i }))
    expect(onSelectImportJob).toHaveBeenCalledWith('job-1')

    fireEvent.click(screen.getByRole('button', { name: /Commit to board/i }))
    expect(onCommitImport).toHaveBeenCalled()

    fireEvent.click(screen.getAllByRole('button', { name: /^Open$/i })[0])
    expect(onSelectImportJob).toHaveBeenCalledWith('job-1')

    fireEvent.click(screen.getByRole('button', { name: /Retry/i }))
    expect(onRetryLoadImportJob).toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: /Refresh job/i }))
    expect(onRefreshImportJob).toHaveBeenCalled()
  })
})
