import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '../auth.jsx'

export default function LoginPage() {
  const { login, isAuthed } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (isAuthed) {
    navigate('/admin', { replace: true })
  }

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await login(username, password)
      navigate('/admin', { replace: true })
    } catch (err) {
      setError(err.message === 'Unauthorized' || /invalid/i.test(err.message)
        ? 'Invalid username or password.' : err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <div className="login-brand">
          <span className="logo-dot">✚</span>
          <h1>GramArogya <span className="accent">AI</span></h1>
        </div>
        <p className="login-sub">Hospital Administration Login</p>

        <label>Username</label>
        <input value={username} onChange={(e) => setUsername(e.target.value)}
          placeholder="admin" autoFocus />

        <label>Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••" />

        {error && <div className="login-error">{error}</div>}

        <button type="submit" className="login-btn" disabled={busy}>
          {busy ? 'Signing in…' : 'Log in'}
        </button>
        <p className="login-hint">Demo: admin / admin123</p>
      </form>
    </div>
  )
}
