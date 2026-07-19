import { useState } from 'react'

import { api } from '../../api.js'
import DepartmentDonut from '../../components/DepartmentDonut.jsx'
import MetricCard from '../../components/MetricCard.jsx'

const HORIZONS = [5, 7, 14, 21]

export default function WorkforcePage() {
  const [horizon, setHorizon] = useState(7)
  const [roster, setRoster] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [dateFilter, setDateFilter] = useState('all')
  const [showMath, setShowMath] = useState(false)

  const generate = () => {
    setLoading(true); setError(''); setRoster(null); setDateFilter('all')
    api.workforceGenerate(horizon).then(setRoster).catch((e) => setError(e.message)).finally(() => setLoading(false))
  }

  const assignments = roster?.recommended_roster ?? []
  const dates = [...new Set(assignments.map((a) => a.date))].sort()
  const shown = dateFilter === 'all' ? assignments : assignments.filter((a) => a.date === dateFilter)
  const s = roster?.recommended_roster_scores

  const deptCounts = {}
  assignments.forEach((a) => { deptCounts[a.department] = (deptCounts[a.department] || 0) + 1 })
  const deptData = Object.entries(deptCounts).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value)

  return (
    <div className="dashboard">
      <div className="page-head">
        <div>
          <h1>Workforce Roster</h1>
          <p className="muted">NSGA-II balanced roster — named staff by date, shift, department and role.</p>
        </div>
        <div className="controls-row">
          <div className="segmented">
            {HORIZONS.map((h) => (
              <button key={h} className={horizon === h ? 'seg active' : 'seg'} onClick={() => setHorizon(h)}>{h}d</button>
            ))}
          </div>
          <button className="run-btn" onClick={generate} disabled={loading}>{loading ? 'Optimising…' : 'Generate roster'}</button>
        </div>
      </div>

      {error && <div className="banner error">{error}</div>}
      {loading && <div className="banner">Running NSGA-II optimisation for {horizon} days… (a few seconds)</div>}
      {!roster && !loading && <div className="banner">Pick a horizon and click <strong>Generate roster</strong>.</div>}

      {roster && !loading && (
        <>
          <div className="metric-row">
            <MetricCard label="Service coverage" value={`${s.coverage_pct}%`} tone={s.coverage_pct >= 90 ? 'good' : s.coverage_pct >= 75 ? 'warn' : 'serious'} />
            <MetricCard label="Assignments" value={assignments.length} sub={`${dates.length} days`} />
            <MetricCard label="Unmet requirements" value={roster.unmet_staffing_requirements.length} tone={roster.unmet_staffing_requirements.length ? 'warn' : 'good'} />
            <MetricCard label="Preference satisfaction" value={`${roster.preference_satisfaction.satisfaction_pct}%`} />
            <MetricCard label="Overtime hours" value={roster.overtime_metrics.total_overtime_hours} />
          </div>

          <div className="grid-2">
            <section className="panel">
              <h2>Assignments by department</h2>
              {deptData.length ? <DepartmentDonut data={deptData} height={260} /> : <p className="muted">No assignments.</p>}
            </section>
            <section className="panel">
              <div className="panel-head">
                <h2>How the plan was chosen</h2>
                <label className="switch">
                  <input type="checkbox" checked={showMath} onChange={(e) => setShowMath(e.target.checked)} />
                  <span className="switch-track"><span className="switch-thumb" /></span>
                  Show math
                </label>
              </div>
              <p className="ai-summary small">{roster.recommendation_reason}</p>
              {showMath && (
                <table className="data-table">
                  <tbody>
                    {roster.optimization_metadata.objective_names.map((n, i) => (
                      <tr key={n}><td>{n.replace(/_/g, ' ')}</td><td><strong>{roster.optimization_metadata.objective_values[i]}</strong></td></tr>
                    ))}
                    <tr><td>feasible solutions</td><td>{roster.optimization_metadata.feasible_solutions}</td></tr>
                    <tr><td>population × generations</td><td>{roster.optimization_metadata.population_size} × {roster.optimization_metadata.generations}</td></tr>
                    <tr><td>seed · time</td><td>{roster.optimization_metadata.seed} · {roster.optimization_metadata.execution_time_sec}s</td></tr>
                  </tbody>
                </table>
              )}
            </section>
          </div>

          <div className="grid-2">
            <section className="panel">
              <div className="panel-head">
                <h2>Roster</h2>
                <select value={dateFilter} onChange={(e) => setDateFilter(e.target.value)}>
                  <option value="all">All dates</option>
                  {dates.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
              <div className="table-scroll" style={{ maxHeight: 460 }}>
                <table className="data-table">
                  <thead><tr><th>Date</th><th>Shift</th><th>Department</th><th>Role</th><th>Staff</th><th></th></tr></thead>
                  <tbody>
                    {shown.map((a, i) => (
                      <tr key={i}>
                        <td>{a.date.slice(5)}</td><td>{a.shift}</td><td>{a.department}</td>
                        <td>{a.assigned_role}</td><td>{a.staff_name}</td>
                        <td>{a.confirmed_or_provisional === 'provisional' ? <span className="pill tone-warn">prov</span> : <span className="pill tone-good">conf</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="panel">
              <h2>Unmet requirements ({roster.unmet_staffing_requirements.length})</h2>
              <div className="table-scroll" style={{ maxHeight: 460 }}>
                <table className="data-table">
                  <thead><tr><th>Date</th><th>Shift</th><th>Role</th><th>Short</th><th>Action</th></tr></thead>
                  <tbody>
                    {roster.unmet_staffing_requirements.map((u, i) => (
                      <tr key={i}>
                        <td>{u.date.slice(5)}</td><td>{u.shift}</td><td>{u.designation}</td>
                        <td><strong className="tone-critical">{u.shortfall}</strong></td>
                        <td className="explain">{u.recommended_action}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        </>
      )}
    </div>
  )
}
