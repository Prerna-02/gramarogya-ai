import { useEffect, useState } from 'react'

import { api } from '../../api.js'
import ActiveAlerts from '../../components/ActiveAlerts.jsx'
import DepartmentDonut from '../../components/DepartmentDonut.jsx'
import InflowChart from '../../components/InflowChart.jsx'
import MetricCard from '../../components/MetricCard.jsx'

const RISK_TONE = { Normal: 'good', Watch: 'warn', High: 'serious', Critical: 'critical' }

export default function DashboardPage() {
  const [summary, setSummary] = useState(null)
  const [inflow, setInflow] = useState(null)
  const [explain, setExplain] = useState(null)
  const [error, setError] = useState('')
  const [run, setRun] = useState(null)
  const [running, setRunning] = useState(false)

  useEffect(() => {
    api.dashboardSummary().then(setSummary).catch((e) => setError(e.message))
    api.forecastSeries(null, 7, 7).then(setInflow).catch(() => {})   // next 7 days + 7 days context
    api.dashboardExplain().then(setExplain).catch(() => {})
  }, [])

  const startRun = async () => {
    setRunning(true); setRun(null)
    try { setRun(await api.createPlanningRun(7)) } catch (e) { setError(e.message) } finally { setRunning(false) }
  }

  if (error) return <div className="banner error">Could not load dashboard: {error}</div>
  if (!summary) return <div className="banner">Loading dashboard…</div>

  const future = summary.future_forecast || []
  const nextDay = future[0]
  const peak = future.length ? Math.max(...future.map((f) => f.total_patient_arrivals)) : null
  const res = summary.latest_resource_status
  const risk = res?.emergency_risk_level ?? 'Unknown'

  const deptData = nextDay ? [
    { name: 'General OPD', value: nextDay.general_opd_arrivals },
    { name: 'Emergency', value: nextDay.trauma_emergency_arrivals },
    { name: 'Fever / Medicine', value: nextDay.fever_infectious_arrivals },
    { name: 'Maternal & Child', value: nextDay.maternal_child_arrivals },
  ] : []

  const seedAlerts = []
  if (res && risk !== 'Normal') {
    seedAlerts.push({ severity: risk === 'Critical' || risk === 'High' ? 'high' : 'warn',
      title: `Capacity risk: ${risk}`, detail: `${res.resource_shortage_count} resource shortage(s) on the latest day.` })
  }
  if (peak) seedAlerts.push({ severity: 'warn', title: '7-day peak load', detail: `Peak ~${peak} patients/day forecast this week.` })
  if (explain?.context?.top_shortages?.length) {
    seedAlerts.push({ severity: 'warn', title: 'Projected shortage', detail: `Most frequent: ${explain.context.top_shortages.join(', ')}.` })
  }

  return (
    <div className="dashboard">
      <div className="page-head">
        <div>
          <h1>Overview Dashboard</h1>
          <p className="muted">Data as of {summary.as_of} · {summary.staff_count} staff · {summary.nearby_facilities} nearby facilities</p>
        </div>
        <button className="run-btn" onClick={startRun} disabled={running}>
          {running ? 'Running plan…' : '▶ Run 7-day plan'}
        </button>
      </div>

      <div className="metric-row">
        <MetricCard label="Predicted patients (next day)" value={nextDay ? nextDay.total_patient_arrivals : '—'} sub="forecast" />
        <MetricCard label="7-day peak" value={peak ?? '—'} sub="patients/day" />
        <MetricCard label="Available general beds" value={res ? res.available_general_beds : '—'} sub={`as of ${res?.date ?? '—'}`} />
        <MetricCard label="Emergency risk" value={risk} tone={RISK_TONE[risk]} sub={`${res?.resource_shortage_count ?? 0} shortages`} />
        <MetricCard label="Overflow patients" value={res ? res.overflow_patients : '—'} sub="latest day" />
      </div>

      <div className="grid-2">
        <section className="panel">
          <h2>Patient inflow — next 7 days</h2>
          <p className="muted small">Forecast with an ~80% expected range (shaded). Recent actuals shown for context.</p>
          {inflow ? <InflowChart data={inflow.series} avg={inflow.avg} /> : <p className="muted">Loading…</p>}
        </section>
        <section className="panel">
          <h2>Department-wise load (next day)</h2>
          {deptData.length ? <DepartmentDonut data={deptData} /> : <p className="muted">No data.</p>}
        </section>
      </div>

      <div className="grid-2">
        <section className="panel">
          <h2>AI Recommendation Explanation</h2>
          {explain ? <p className="ai-summary">{explain.summary}</p> : <p className="muted">Generating summary…</p>}
        </section>
        <section className="panel">
          <div className="panel-head"><h2>Active alerts</h2><span className="pill tone-warn">live</span></div>
          <ActiveAlerts key={explain ? 'e' : 'ne'} seed={seedAlerts} />
        </section>
      </div>

      <div className="grid-2">
        <section className="panel">
          <h2>7-day forecast</h2>
          <table className="data-table">
            <thead><tr><th>Date</th><th>Total</th><th>Fever</th><th>Maternal</th><th>Trauma</th><th>Admissions</th></tr></thead>
            <tbody>
              {future.map((f) => (
                <tr key={f.date}>
                  <td>{f.date.slice(5)}</td><td><strong>{f.total_patient_arrivals}</strong></td>
                  <td>{f.fever_infectious_arrivals}</td><td>{f.maternal_child_arrivals}</td>
                  <td>{f.trauma_emergency_arrivals}</td><td>{f.expected_admissions}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section className="panel">
          <h2>Latest planning run</h2>
          {run ? (
            <div className="run-result">
              <div className="run-line"><span>Status</span><strong className="tone-good">{run.status}</strong></div>
              <div className="run-line"><span>Capacity risk</span>
                <strong className={`tone-${RISK_TONE[run.capacity_check.overall_risk] || ''}`}>{run.capacity_check.overall_risk}</strong></div>
              {run.roster_summary && (<>
                <div className="run-line"><span>Roster coverage</span><strong>{run.roster_summary.coverage_pct}%</strong></div>
                <div className="run-line"><span>Assignments</span><strong>{run.roster_summary.assignments}</strong></div>
                <div className="run-line"><span>Unmet requirements</span><strong>{run.roster_summary.unmet_requirements}</strong></div>
              </>)}
              <p className="muted small">Run id {run.planning_run_id.slice(0, 8)} · saved to database</p>
            </div>
          ) : (
            <p className="muted">Click <strong>Run 7-day plan</strong> to generate a forecast, resource plan,
              and staff roster in one step (saved under one planning id).</p>
          )}
        </section>
      </div>
    </div>
  )
}
