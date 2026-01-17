import { describe, it, expect, beforeEach } from 'vitest'
import { buildApiUrl, buildAuthHeaders, STORAGE_KEY_TOKEN } from './api'

describe('api helpers', () => {
  beforeEach(() => {
    global.localStorage.clear()
  })

  it('buildApiUrl appends project_dir', () => {
    expect(buildApiUrl('/api/phases', '/tmp/project')).toBe(
      '/api/phases?project_dir=%2Ftmp%2Fproject'
    )
  })

  it('buildApiUrl preserves existing query params', () => {
    expect(buildApiUrl('/api/runs?limit=25', '/tmp/project')).toBe(
      '/api/runs?limit=25&project_dir=%2Ftmp%2Fproject'
    )
  })

  it('buildAuthHeaders adds Authorization when token exists', () => {
    global.localStorage.setItem(STORAGE_KEY_TOKEN, 'token-123')
    const headers = buildAuthHeaders({ 'Content-Type': 'application/json' }) as Record<string, string>
    expect(headers['Authorization']).toBe('Bearer token-123')
    expect(headers['Content-Type']).toBe('application/json')
  })
})

