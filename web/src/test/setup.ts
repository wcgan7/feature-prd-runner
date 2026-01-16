import { expect, afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'

// Cleanup after each test
afterEach(() => {
  cleanup()
})

// Mock localStorage
const localStorageMock = {
  getItem: (key: string) => {
    return null
  },
  setItem: (key: string, value: string) => {},
  removeItem: (key: string) => {},
  clear: () => {},
}

global.localStorage = localStorageMock as Storage

// Mock fetch
global.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
  return new Response(JSON.stringify({}), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}
