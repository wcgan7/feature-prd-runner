import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import App from './App'

describe('App default view', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    global.localStorage.clear()
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
      return Promise.resolve({
        ok: true,
        json: async () => ({}),
      })
    })
  })

  it('lands on tasks when there is no saved view', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText(/task workflow/i)).toBeInTheDocument()
    })
  })

  it('keeps an explicit saved view preference', async () => {
    global.localStorage.setItem('feature-prd-runner-view', 'diagnostics')
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText(/diagnostics workflow/i)).toBeInTheDocument()
    })
  })
})
