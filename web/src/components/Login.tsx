import { useState } from 'react'
import './Login.css'

interface Props {
  onLoginSuccess: (token: string, username: string) => void
}

export default function Login({ onLoginSuccess }: Props) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Login failed')
      }

      const data = await response.json()
      onLoginSuccess(data.access_token, data.username)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-container">
      <div className="login-card">
        <h1 className="login-title">Feature PRD Runner</h1>
        <p className="login-subtitle">Sign in to access the dashboard</p>

        {error && <div className="login-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="login-form-group">
            <label htmlFor="username" className="login-label">
              Username
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
              className="login-input"
            />
          </div>

          <div className="login-form-group">
            <label htmlFor="password" className="login-label">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="login-input"
            />
          </div>

          <button type="submit" disabled={loading} className="login-button">
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        <div className="login-hint">
          <strong>Default credentials (if auth enabled):</strong>
          <br />
          Username: admin
          <br />
          Password: admin
          <br />
          <br />
          <em>Configure via DASHBOARD_USERNAME and DASHBOARD_PASSWORD env vars</em>
        </div>
      </div>
    </div>
  )
}
