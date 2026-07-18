import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api.js'

// Phase 2 landing page. Its main job is to prove the app runs AND that the
// frontend can reach the FastAPI backend (via the /api/health check).
export default function LandingPage() {
  const [health, setHealth] = useState({ state: 'checking' })

  useEffect(() => {
    api
      .health()
      .then((data) => setHealth({ state: 'ok', data }))
      .catch((err) => setHealth({ state: 'error', message: err.message }))
  }, [])

  return (
    <div className="landing">
      <h1>
        GramArogya <span className="accent">AI</span>
      </h1>
      <p className="tagline">
        AI-powered rural healthcare operations &amp; patient-access prototype.
      </p>

      <div className={`health-pill ${health.state}`}>
        {health.state === 'checking' && 'Checking backend…'}
        {health.state === 'ok' &&
          `Backend connected · v${health.data.version}`}
        {health.state === 'error' &&
          `Backend unreachable (${health.message})`}
      </div>

      <div className="entry-cards">
        <Link to="/admin" className="entry-card admin">
          <h2>Hospital Admin</h2>
          <p>Forecasts, rosters, resources &amp; emergency coordination.</p>
        </Link>
        <Link to="/patient" className="entry-card patient">
          <h2>Patient / Public</h2>
          <p>Find a nearby capable facility and emergency support.</p>
        </Link>
      </div>
    </div>
  )
}
