import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'

function mockFetchForApp() {
  global.fetch = vi.fn().mockImplementation((url) => {
    const urlString = url.toString()
    if (urlString.includes('/api/auth/status')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          enabled: false,
          authenticated: true,
          username: null,
        }),
      })
    }
    if (urlString.includes('/api/status')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          project_dir: '',
          status: 'idle',
          phases_completed: 0,
          phases_total: 0,
          tasks_ready: 0,
          tasks_running: 0,
          tasks_done: 0,
          tasks_blocked: 0,
        }),
      })
    }
    if (urlString.includes('/api/workers/')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          success: true,
          message: 'ok',
        }),
      })
    }
    if (urlString.includes('/api/workers')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          default_worker: 'codex',
          routing: {},
          providers: [],
        }),
      })
    }
    return Promise.resolve({
      ok: true,
      json: async () => ({}),
    })
  })
}

async function clickNav(label: string) {
  const btn = screen.getByRole('button', { name: new RegExp(`^${label}`, 'i') })
  await userEvent.click(btn)
}

describe('Accessibility coverage for core cockpit views', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    global.localStorage.clear()
    mockFetchForApp()
  })

  it('renders landmarks and accessible global controls', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText(/task workflow/i)).toBeInTheDocument()
    })
    expect(screen.getByRole('main')).toBeInTheDocument()
    expect(screen.getByLabelText(/command palette/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/activity rail/i)).toBeInTheDocument()
  })

  it('keeps Tasks, Execution, and Agents navigable via labeled nav buttons', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText(/task workflow/i)).toBeInTheDocument()
    })

    await clickNav('Execution')
    await waitFor(() => {
      expect(screen.getByText(/execution workflow/i)).toBeInTheDocument()
    })

    await clickNav('Agents')
    await waitFor(() => {
      expect(screen.getByText(/agent operations/i)).toBeInTheDocument()
    })

    await clickNav('Tasks')
    await waitFor(() => {
      expect(screen.getByText(/task workflow/i)).toBeInTheDocument()
    })
  })
})
