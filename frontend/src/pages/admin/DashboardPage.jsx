import { useEffect, useRef, useState } from 'react'

import { api } from '../../api.js'
import ActiveAlerts from '../../components/ActiveAlerts.jsx'
import ActiveStaffTable from '../../components/ActiveStaffTable.jsx'
import AlertPopup from '../../components/AlertPopup.jsx'
import DepartmentDonut from '../../components/DepartmentDonut.jsx'
import InflowChart from '../../components/InflowChart.jsx'
import MetricCard from '../../components/MetricCard.jsx'
import ResourcePressureHeatmap from '../../components/ResourcePressureHeatmap.jsx'
import WaitTimeChart from '../../components/WaitTimeChart.jsx'
import WorkforceCoverageChart from '../../components/WorkforceCoverageChart.jsx'

const metricTone = (value, watch, critical) => value >= critical ? 'critical' : value >= watch ? 'warn' : 'good'
const FORECAST_HORIZONS = [7, 14, 21, 30]

const getForecastSelection = () => {
  try {
    const saved = JSON.parse(localStorage.getItem('gramarogya_forecast_selection') || 'null')
    return { start: saved?.start || null, horizon: FORECAST_HORIZONS.includes(saved?.horizon) ? saved.horizon : 7 }
  } catch {
    return { start: null, horizon: 7 }
  }
}

const dayLabel = (value) => {
  if (!value) return '—'
  const [year, month, day] = value.split('-').map(Number)
  return new Intl.DateTimeFormat('en', { day: 'numeric', month: 'short' }).format(new Date(Date.UTC(year, month - 1, day)))
}

function buildForecastInsight(inflow) {
  const rows = inflow?.series?.filter((row) => row.kind === 'window' && (row.actual != null || row.predicted != null)) ?? []
  if (!rows.length) return null
  const value = (row) => row.actual ?? row.predicted
  const first = rows[0]
  const last = rows.at(-1)
  const lowest = rows.reduce((best, row) => value(row) < value(best) ? row : best, first)
  const peak = rows.reduce((best, row) => value(row) > value(best) ? row : best, first)
  const average = inflow.avg ?? Math.round(rows.reduce((sum, row) => sum + value(row), 0) / rows.length)
  const firstDifference = value(first) - average
  const startPosition = firstDifference === 0 ? 'at the window average'
    : `${Math.abs(firstDifference)} patient${Math.abs(firstDifference) === 1 ? '' : 's'} ${firstDifference < 0 ? 'below' : 'above'} the window average`
  const overallDifference = value(last) - value(first)
  const overallDirection = overallDifference === 0 ? 'finishes at the same level as it starts'
    : `finishes ${Math.abs(overallDifference)} patient${Math.abs(overallDifference) === 1 ? '' : 's'} ${overallDifference > 0 ? 'above' : 'below'} the starting level`
  return {
    summary: `For ${dayLabel(first.date)} to ${dayLabel(last.date)}, patient inflow begins at ${value(first)}, ${startPosition}. `
      + `The lowest expected load is ${value(lowest)} on ${dayLabel(lowest.date)}, while the peak is ${value(peak)} on ${dayLabel(peak.date)}. `
      + `The window averages ${average} patients per day and ${overallDirection}.`,
    first, last, lowest, peak, average,
  }
}

export default function DashboardPage() {
  const selection = getForecastSelection()
  const [operations, setOperations] = useState(null)
  const [inflow, setInflow] = useState(null)
  const [error, setError] = useState('')
  const [popupAlert, setPopupAlert] = useState(null)
  const activeAlertIds = useRef(new Set())

  useEffect(() => {
    let active = true
    Promise.all([
      api.dashboardOperations(selection.start, selection.horizon),
      api.forecastSeries(selection.start, selection.horizon, 7),
    ]).then(([operationsData, inflowData]) => {
      if (!active) return
      setOperations(operationsData)
      setInflow(inflowData)
    }).catch((err) => active && setError(err.message))
    return () => { active = false }
  }, [selection.start, selection.horizon])

  useEffect(() => {
    const interval = setInterval(() => {
      api.dashboardOperations(selection.start, selection.horizon).then(setOperations).catch(() => {})
    }, 30_000)
    return () => clearInterval(interval)
  }, [selection.start, selection.horizon])

  useEffect(() => {
    if (!operations) return
    const incoming = new Set(operations.alerts.map((alert) => alert.id))
    const newAlert = operations.alerts.find((alert) => !activeAlertIds.current.has(alert.id))
    activeAlertIds.current = incoming
    if (newAlert) setPopupAlert(newAlert)
  }, [operations])

  if (error) return <div className="banner error">Could not load dashboard: {error}</div>
  if (!operations || !inflow) return <div className="page-loading">Preparing hospital operations dashboard…</div>

  const metrics = operations.metrics
  const windowRows = inflow.series.filter((row) => row.kind === 'window' && row.cat)
  const nextDay = windowRows[0]
  const departmentMix = nextDay ? [
    { name: 'General OPD', value: nextDay.cat.general_opd_arrivals },
    { name: 'Emergency', value: nextDay.cat.trauma_emergency_arrivals },
    { name: 'Fever / Medicine', value: nextDay.cat.fever_infectious_arrivals },
    { name: 'Maternal & Child', value: nextDay.cat.maternal_child_arrivals },
  ] : []
  const insight = buildForecastInsight(inflow)
  const forecastEnd = operations.forecast_selection?.end || windowRows.at(-1)?.date

  return (
    <div className="dashboard dashboard-overview">
      <div className="page-head dashboard-head">
        <div>
          <div className="page-eyebrow">Hospital operations</div>
          <h1>Administration Dashboard</h1>
          <p className="muted">Gadchiroli Rural Hospital · Operational view for {operations.as_of}</p>
        </div>
        <div className="updated-chip">
          <span className="updated-dot" />
          Data calculated from the latest hospital record
        </div>
      </div>

      <div className="metric-row dashboard-metrics">
        <MetricCard label="Today's patient count" value={metrics.today_patients} sub={`${metrics.today_patients_source} · ${operations.as_of}`} />
        <MetricCard label="Current patient wait" value={`${metrics.current_wait_minutes} min`}
          tone={metricTone(metrics.current_wait_minutes, 30, 45)} sub="estimated · target under 30 min" />
        <MetricCard label="Actively treating" value={metrics.active_treating_staff}
          sub={`${metrics.active_staff_on_duty} total staff on duty`} />
        <MetricCard label="Staff utilization" value={`${metrics.planned_staff_utilization_pct}%`}
          tone={metricTone(metrics.planned_staff_utilization_pct, 80, 90)} sub="planned active capacity" />
        <MetricCard label="General bed occupancy" value={metrics.general_bed_occupancy_pct == null ? '—' : `${metrics.general_bed_occupancy_pct}%`}
          tone={metricTone(metrics.general_bed_occupancy_pct ?? 0, 80, 90)} sub="latest resource status" />
        <MetricCard label="Schedule fairness" value={metrics.schedule_fairness_index}
          tone={metrics.schedule_fairness_index >= 75 ? 'good' : 'warn'} sub={`shift equity · ${metrics.overtime_hours}h overtime`} />
      </div>

      <section className="panel panel-featured">
        <div className="panel-heading-copy">
          <h2>Total patient inflow</h2>
          <p>{selection.horizon}-day patient demand outlook · {dayLabel(inflow.start)} to {dayLabel(forecastEnd)}.</p>
        </div>
        <InflowChart data={inflow.series} avg={inflow.avg} height={330} />
      </section>

      {insight && <section className="panel forecast-insight-panel">
        <div className="panel-heading-copy">
          <h2>Forecast insights</h2>
          <p>Analytical interpretation of the selected patient-inflow window.</p>
        </div>
        <p className="forecast-insight-summary">{insight.summary}</p>
        <div className="evidence-row forecast-insight-evidence">
          <span><b>{insight.first.actual ?? insight.first.predicted}</b>starting demand · {dayLabel(insight.first.date)}</span>
          <span><b>{insight.lowest.actual ?? insight.lowest.predicted}</b>lowest demand · {dayLabel(insight.lowest.date)}</span>
          <span><b>{insight.peak.actual ?? insight.peak.predicted}</b>peak demand · {dayLabel(insight.peak.date)}</span>
          <span><b>{insight.average}</b>average patients/day</span>
        </div>
      </section>}

      <div className="grid-analytics">
        <section className="panel">
          <div className="panel-heading-copy">
            <h2>Workforce coverage by department</h2>
            <p>Department staffing readiness for the current-duty allocation.</p>
          </div>
          <WorkforceCoverageChart data={operations.department_coverage} />
        </section>
        <section className="panel">
          <div className="panel-heading-copy">
            <h2>Patient wait-time trend</h2>
            <p>Estimated patient waiting pressure over the latest seven days.</p>
          </div>
          <WaitTimeChart data={operations.wait_time_trend} />
        </section>
      </div>

      <section className="panel panel-featured">
        <div className="panel-heading-copy">
          <h2>{selection.horizon}-day demand and resource pressure</h2>
          <p>Forecast-driven staffing and capacity pressure for {dayLabel(inflow.start)} to {dayLabel(forecastEnd)}.</p>
        </div>
        <ResourcePressureHeatmap data={operations.resource_pressure} />
      </section>

      <div className="grid-analytics operations-grid">
        <section className="panel">
          <div className="panel-head">
            <div className="panel-heading-copy">
              <h2>Staff actively supporting care</h2>
              <p>Current-duty allocation with role and department.</p>
            </div>
            <span className="pill tone-good">{operations.active_staff.length} on duty</span>
          </div>
          <ActiveStaffTable staff={operations.active_staff} />
        </section>
        <section className="panel">
          <div className="panel-head">
            <div className="panel-heading-copy">
              <h2>Live alerts</h2>
              <p>Current operational and forecast exceptions requiring attention.</p>
            </div>
            {operations.alerts.length > 0 && <span className="pill tone-warn">{operations.alerts.length} active</span>}
          </div>
          <ActiveAlerts alerts={operations.alerts} />
        </section>
      </div>

      <section className="panel">
        <div className="panel-heading-copy">
          <h2>First-day service mix</h2>
          <p>Expected patient distribution on {dayLabel(nextDay?.date)} for the selected forecast window.</p>
        </div>
        {departmentMix.length ? <DepartmentDonut data={departmentMix} height={260} /> : <p className="muted">No forecast available.</p>}
      </section>
      <AlertPopup alert={popupAlert} onClose={() => setPopupAlert(null)} />
    </div>
  )
}
