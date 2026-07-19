import { useState } from 'react'

import { api } from '../../api.js'
import MetricCard from '../../components/MetricCard.jsx'

const HORIZONS = [5, 7, 14, 21]

export default function FairnessPage() {
  const [horizon, setHorizon] = useState(7)
  const [roster, setRoster] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const generate = () => {
    setLoading(true); setError(''); setRoster(null)
    api.workforceGenerate(horizon).then(setRoster).catch((e) => setError(e.message)).finally(() => setLoading(false))
  }

  const groups = roster ? Object.entries(roster.fairness_metrics) : []

  return (
    <div className="dashboard">
      <div className="page-head">
        <div>
          <h1>Fairness & Audit</h1>
          <p className="muted">Workload equity within comparable roles, fatigue and overtime.</p>
        </div>
        <div className="controls-row">
          <div className="segmented">
            {HORIZONS.map((h) => (
              <button key={h} className={horizon === h ? 'seg active' : 'seg'} onClick={() => setHorizon(h)}>{h}d</button>
            ))}
          </div>
          <button className="run-btn" onClick={generate} disabled={loading}>
            {loading ? 'Optimising…' : 'Analyse roster'}
          </button>
        </div>
      </div>

      {error && <div className="banner error">{error}</div>}
      {loading && <div className="banner">Generating a roster and measuring fairness…</div>}
      {!roster && !loading && <div className="banner">Click <strong>Analyse roster</strong> to compute fairness metrics.</div>}

      {roster && !loading && (
        <>
          <div className="metric-row">
            <MetricCard label="Unfairness (lower better)" value={roster.recommended_roster_scores.unfairness} />
            <MetricCard label="Fatigue score" value={roster.fatigue_metrics.total_fatigue_score} />
            <MetricCard label="Overtime hours" value={roster.overtime_metrics.total_overtime_hours} />
            <MetricCard label="Preference satisfaction" value={`${roster.preference_satisfaction.satisfaction_pct}%`} />
          </div>

          <section className="panel">
            <h2>Fairness within comparable role groups</h2>
            <p className="muted small">Night/weekend spread is compared only among staff with similar
              designation — never doctors vs nurses.</p>
            <table className="data-table">
              <thead>
                <tr><th>Role group</th><th>Members</th><th>Night σ</th><th>Weekend σ</th><th>Max nights</th><th>Min nights</th></tr>
              </thead>
              <tbody>
                {groups.length === 0 && <tr><td colSpan={6} className="muted">No multi-member groups scheduled.</td></tr>}
                {groups.map(([g, m]) => (
                  <tr key={g}>
                    <td>{g.replace(/_/g, ' ')}</td>
                    <td>{m.members}</td>
                    <td>{m.night_std}</td>
                    <td>{m.weekend_std}</td>
                    <td>{m.max_nights}</td>
                    <td>{m.min_nights}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="panel">
            <h2>Human oversight</h2>
            <p className="muted">AI recommends; the administrator approves. Manual overrides are revalidated
              against clinical constraints and recorded in an audit log with a reason. No hard constraint
              is ever traded for a fairness score.</p>
          </section>
        </>
      )}
    </div>
  )
}
