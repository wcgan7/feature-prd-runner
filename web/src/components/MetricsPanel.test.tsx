import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import MetricsPanel from './MetricsPanel'

describe('MetricsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders metrics when api_calls is 0 but other metrics exist', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        tokens_used: 10,
        api_calls: 0,
        estimated_cost_usd: 0.12,
        wall_time_seconds: 5,
        phases_completed: 0,
        phases_total: 1,
        files_changed: 0,
        lines_added: 0,
        lines_removed: 0,
      }),
    })

    render(<MetricsPanel />)

    await waitFor(() => {
      expect(screen.getByText(/tokens/i)).toBeInTheDocument()
      expect(screen.getByText('10')).toBeInTheDocument()
    })
  })
})

