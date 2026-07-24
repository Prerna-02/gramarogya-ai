import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth.jsx'
import AppIcon from '../components/AppIcon.jsx'

export default function LoginPage() {
  const { login, isAuthed } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (isAuthed) return <Navigate to="/admin" replace />

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      await login(username, password)
      navigate('/admin', { replace: true })
    } catch (err) {
      setError(err.message === 'Unauthorized' || /invalid/i.test(err.message)
        ? 'The username or password is incorrect.' : err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="login-page">
      <section className="login-story" aria-label="GramArogya AI introduction">
        <div className="login-ambient" aria-hidden="true">
          <span className="ambient-orb ambient-orb-one" />
          <span className="ambient-orb ambient-orb-two" />
          <svg className="ambient-pulse" viewBox="0 0 1200 160" preserveAspectRatio="none">
            <path d="M0 88h220l24-20 28 46 36-100 42 132 34-58h190l22-18 31 42 30-76 38 92 34-40H1200" />
          </svg>
        </div>
        <div className="login-story-content">
          <div className="login-logo"><span className="logo-mark large"><span>+</span></span><div><strong>GramArogya <em>AI</em></strong><span>Hospital Command Centre</span></div></div>
          <div className="story-message">
            <span className="story-kicker">Smarter rural hospital operations</span>
            <h1>Plan today.<br />Prepare for tomorrow.</h1>
            <p>Forecast patient demand, coordinate limited resources and build fair workforce schedules from one command centre.</p>
          </div>
          <div className="care-visual" aria-hidden="true">
            <div className="care-orbit orbit-one" /><div className="care-orbit orbit-two" />
            <div className="care-cross"><span>+</span></div>
            <div className="care-card care-card-one"><span>Demand</span><b>7-day outlook</b></div>
            <div className="care-card care-card-two"><span>Workforce</span><b>Fair coverage</b></div>
            <div className="care-card care-card-three"><span>Resources</span><b>Ready</b></div>
          </div>
          <p className="story-foot">Built for resilient, accessible healthcare in rural communities.</p>
        </div>
      </section>

      <section className="login-panel">
        <form className="login-card" onSubmit={submit}>
          <div className="login-mobile-brand"><span className="logo-mark"><span>+</span></span><strong>GramArogya AI</strong></div>
          <div className="login-heading">
            <span className="secure-icon"><AppIcon name="lock" size={20} /></span>
            <h2>Welcome back</h2>
            <p>Sign in to access hospital administration.</p>
          </div>

          <label htmlFor="username">Username</label>
          <input id="username" value={username} onChange={(event) => setUsername(event.target.value)}
            placeholder="Enter your username" autoComplete="username" autoFocus required />

          <label htmlFor="password">Password</label>
          <div className="password-field">
            <input id="password" type={showPassword ? 'text' : 'password'} value={password}
              onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password"
              autoComplete="current-password" required />
            <button type="button" onClick={() => setShowPassword((value) => !value)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}>
              <AppIcon name={showPassword ? 'eyeOff' : 'eye'} size={19} />
            </button>
          </div>

          {error && <div className="login-error" role="alert">{error}</div>}
          <button type="submit" className="login-btn" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in securely'}
          </button>
          <div className="login-divider"><span>Patient access</span></div>
          <Link className="patient-access-link" to="/patient">Continue to the patient portal</Link>
          <p className="login-security"><AppIcon name="lock" size={14} /> Protected hospital administration access</p>
        </form>
      </section>
    </main>
  )
}
