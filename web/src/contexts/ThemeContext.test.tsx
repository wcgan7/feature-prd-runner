import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { ThemeProvider, useTheme } from './ThemeContext'

function ThemeProbe() {
  const { theme, effectiveTheme, setTheme, toggleTheme } = useTheme()
  return (
    <div>
      <p>theme:{theme}</p>
      <p>effective:{effectiveTheme}</p>
      <button onClick={() => setTheme('dark')}>Set dark</button>
      <button onClick={() => setTheme('system')}>Set system</button>
      <button onClick={toggleTheme}>Toggle</button>
    </div>
  )
}

function BrokenProbe() {
  useTheme()
  return null
}

describe('ThemeContext', () => {
  it('throws when useTheme is called outside ThemeProvider', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    try {
      expect(() => render(<BrokenProbe />)).toThrow(/useTheme must be used within a ThemeProvider/i)
    } finally {
      errorSpy.mockRestore()
    }
  })

  it('persists and toggles theme state', () => {
    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>
    )

    expect(screen.getByText(/theme:system/i)).toBeInTheDocument()
    expect(document.documentElement.getAttribute('data-theme')).toBe('system')

    fireEvent.click(screen.getByRole('button', { name: /Set dark/i }))
    expect(screen.getByText(/theme:dark/i)).toBeInTheDocument()
    expect(localStorage.getItem('feature-prd-runner-theme')).toBe('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')

    fireEvent.click(screen.getByRole('button', { name: /Toggle/i }))
    expect(screen.getByText(/theme:light/i)).toBeInTheDocument()
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')

    fireEvent.click(screen.getByRole('button', { name: /Set system/i }))
    expect(screen.getByText(/theme:system/i)).toBeInTheDocument()
    expect(localStorage.getItem('feature-prd-runner-theme')).toBe('system')
  })
})
