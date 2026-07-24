import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../../api.js'
import BedCapacityChart from '../../components/BedCapacityChart.jsx'
import InventoryBurnDownChart from '../../components/InventoryBurnDownChart.jsx'
import MetricCard from '../../components/MetricCard.jsx'
import ResourcePressureHeatmap from '../../components/ResourcePressureHeatmap.jsx'

const STATUS_TONE = { Normal: 'good', Watch: 'warn', High: 'serious', Critical: 'critical' }
const formatResource = (name) => name.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
const getSelection = () => {
  try { return JSON.parse(localStorage.getItem('gramarogya_forecast_selection')) || {} } catch { return {} }
}

function Section({ title, items, showMath }) {
  return <><tr className="group-row"><td colSpan={showMath ? 5 : 4}>{title}</td></tr>
    {items.map((item) => <tr key={item.resource} className={item.shortage > 0 ? 'short' : ''}>
      <td>{formatResource(item.resource)}</td><td>{item.required}</td><td>{item.available}</td>
      <td>{item.shortage > 0 ? <strong className="tone-critical">{item.shortage}</strong> : '0'}</td>
      {showMath && <td className="explain">{item.explanation}</td>}
    </tr>)}</>
}

export default function ResourcePlanPage() {
  const selection = getSelection()
  const horizon = selection.horizon || 7
  const start = selection.start || null
  const [plans, setPlans] = useState(null)
  const [selected, setSelected] = useState(0)
  const [showMath, setShowMath] = useState(false)
  const [bedType, setBedType] = useState('general')
  const [inventoryItem, setInventoryItem] = useState('diagnostic_test_kits')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true); setError(''); setSelected(0)
    api.resourcesPlan(horizon, start).then((result) => setPlans(result.plans))
      .catch((err) => setError(err.message)).finally(() => setLoading(false))
  }, [horizon, start])

  const day = plans?.[selected]
  const analytics = useMemo(() => buildAnalytics(plans), [plans])

  return <div className="dashboard">
    <div className="page-head"><div><div className="page-eyebrow">Capacity conversion</div><h1>Resource Planning</h1>
      <p className="muted">Forecast demand converted into staffing, bed capacity, medicine, oxygen and ambulance requirements.</p></div>
    </div>
    <div className="forecast-source-banner"><div><span>Source forecast</span><strong>{start || 'Next forecast'} · {horizon} days</strong></div>
      <p>Consumable stock is carried forward across the full window, so later dates reflect planned usage.</p><Link to="/admin/forecast">Change forecast</Link></div>

    {error && <div className="banner error">{error}</div>}
    {loading && <div className="banner">Calculating the selected resource window…</div>}
    {plans && !loading && <>
      <div className="metric-row resource-metrics">
        <MetricCard label="Physical shortage days" value={analytics.shortageDays} sub={`of ${plans.length} forecast days`} tone={analytics.shortageDays ? 'warn' : 'good'} />
        <MetricCard label="Peak bed pressure" value={`${analytics.peakBedPressure}%`} sub={formatResource(analytics.peakBedResource)} tone={analytics.peakBedPressure > 100 ? 'critical' : analytics.peakBedPressure >= 85 ? 'warn' : 'good'} />
        <MetricCard label="Next action due" value={analytics.firstPressure?.slice(5) || 'None'} sub={analytics.firstAction || 'capacity adequate'} tone={analytics.firstPressure ? 'warn' : 'good'} />
        <MetricCard label="Highest physical risk" value={analytics.highestRisk} tone={STATUS_TONE[analytics.highestRisk]} sub="beds, stock and transport" />
      </div>

      <section className="panel panel-featured"><div className="panel-heading-copy"><h2>Staff and physical resource pressure</h2>
        <p>Required versus available staffing, beds, essential supplies, oxygen and ambulance cover for every selected day.</p></div>
        <ResourcePressureHeatmap data={analytics.pressure} />
      </section>

      <div className="grid-2 resource-chart-grid">
        <section className="panel"><div className="panel-head"><div className="panel-heading-copy"><h2>Bed demand versus capacity</h2><p>Shows when the forecast approaches or exceeds usable bed capacity.</p></div>
          <select value={bedType} onChange={(event) => setBedType(event.target.value)}><option value="general">General beds</option><option value="emergency">Emergency beds</option><option value="isolation">Isolation beds</option></select></div>
          <BedCapacityChart plans={plans} bedType={bedType} />
        </section>
        <section className="panel"><div className="panel-head"><div className="panel-heading-copy"><h2>Projected stock remaining</h2><p>Shows when remaining stock crosses the demand-and-lead-time reorder threshold.</p></div>
          <select value={inventoryItem} onChange={(event) => setInventoryItem(event.target.value)}>
            {Object.keys(day.medicines).map((item) => <option key={item} value={item}>{formatResource(item)}</option>)}
          </select></div>
          <InventoryBurnDownChart plans={plans} item={inventoryItem} />
        </section>
      </div>

      <div className="resource-action-grid">
        <section className="panel"><div className="panel-heading-copy"><h2>Prioritized operational actions</h2><p>Consolidated physical-resource actions, ordered by shortage before reorder signals.</p></div>
          {analytics.actions.length ? <div className="action-queue">{analytics.actions.map((action, index) => <div className="action-row" key={action.resource}>
            <span className={`action-rank ${action.kind === 'Shortage' ? 'critical' : ''}`}>{index + 1}</span>
            <div><strong>{formatResource(action.resource)}</strong><span>{action.message}</span></div>
            <b>{action.firstDate.slice(5)}</b>
          </div>)}</div> : <div className="empty-state-good">Physical capacity covers the selected forecast. Continue routine stock monitoring.</div>}
        </section>
      </div>

      <div className="grid-2 resource-detail-grid">
        <section className="panel"><h2>Daily physical status</h2><div className="table-scroll" style={{ maxHeight: 520 }}><table className="data-table">
          <thead><tr><th>Date</th><th>Status</th><th>Physical shortages</th><th>Reorders</th></tr></thead><tbody>
          {plans.map((plan, index) => {
            const summary = physicalSummary(plan)
            return <tr key={plan.date} className={index === selected ? 'row-sel' : 'row-click'} onClick={() => setSelected(index)}>
              <td>{plan.date}</td><td><span className={`pill tone-${STATUS_TONE[summary.status]}`}>{summary.status}</span></td>
              <td>{summary.shortages.length ? summary.shortages.map(formatResource).join(', ') : '—'}</td>
              <td>{summary.reorders.length ? summary.reorders.map(formatResource).join(', ') : '—'}</td>
            </tr>
          })}</tbody></table></div>
        </section>
        <section className="panel"><div className="panel-head"><h2>Physical breakdown — {day?.date}</h2><label className="switch">
          <input type="checkbox" checked={showMath} onChange={(event) => setShowMath(event.target.checked)} /><span className="switch-track"><span className="switch-thumb" /></span>Show calculation
        </label></div>
          <p className="muted small">Forecast: {day?.forecast.total_patient_arrivals} patients; {day?.forecast.expected_admissions} expected admissions.</p>
          <div className="table-scroll" style={{ maxHeight: 560 }}><table className="data-table"><thead><tr><th>Resource</th><th>Req</th><th>Avail</th><th>Short</th>{showMath && <th>How calculated</th>}</tr></thead><tbody>
            {day && <Section title="Beds" items={Object.values(day.beds)} showMath={showMath} />}
            {day && <Section title="Medicines and consumables" items={Object.values(day.medicines)} showMath={showMath} />}
            {day && <Section title="Oxygen and transport" items={[day.oxygen, day.ambulances]} showMath={showMath} />}
          </tbody></table></div>
        </section>
      </div>
    </>}
  </div>
}

function physicalLines(plan) {
  return [...Object.values(plan.beds), ...Object.values(plan.medicines), plan.oxygen, plan.ambulances]
}

function physicalSummary(plan) {
  const lines = physicalLines(plan)
  const shortages = lines.filter((line) => line.shortage > 0).map((line) => line.resource)
  const reorders = lines.filter((line) => line.reorder_needed && line.shortage === 0).map((line) => line.resource)
  const n = shortages.length
  return { shortages, reorders, status: n >= 3 ? 'Critical' : n === 2 ? 'High' : n === 1 || reorders.length ? 'Watch' : 'Normal' }
}

function buildAnalytics(plans) {
  if (!plans?.length) return { shortageDays: 0, actions: [], highestRisk: 'Normal', firstPressure: null, pressure: [], peakBedPressure: 0, peakBedResource: 'general_beds' }
  const riskOrder = { Normal: 0, Watch: 1, High: 2, Critical: 3 }
  const actions = new Map()
  const pressure = []
  const curated = [
    'general_doctors', 'physicians', 'emergency_doctors', 'obgyn_doctors', 'pediatricians',
    'senior_nursing_officers', 'nursing_officers', 'anm_staff', 'lab_technicians', 'pharmacists',
    'general_beds', 'emergency_beds', 'isolation_beds', 'diagnostic_test_kits', 'iv_fluids',
    'oxygen_cylinders', 'ambulances',
  ]
  let peakBed = { pressure: 0, resource: 'general_beds' }
  for (const plan of plans) {
    const lines = Object.fromEntries([...Object.values(plan.staff), ...physicalLines(plan)].map((line) => [line.resource, line]))
    for (const resource of curated) {
      const line = lines[resource]
      pressure.push({ date: plan.date, resource, required: line.required, available: line.available, shortage: line.shortage, pressure_pct: line.available ? +(100 * line.required / line.available).toFixed(1) : 999 })
    }
    for (const line of Object.values(plan.beds)) {
      const pct = line.available ? Math.round(100 * line.required / line.available) : 999
      if (pct > peakBed.pressure) peakBed = { pressure: pct, resource: line.resource }
    }
    for (const line of physicalLines(plan)) {
      if (line.shortage > 0) addAction(actions, line.resource, 'Shortage', plan.date, line.shortage)
      else if (line.reorder_needed) addAction(actions, line.resource, 'Reorder', plan.date, 0)
    }
  }
  const sortedActions = [...actions.values()].sort((a, b) => (a.kind === b.kind ? a.firstDate.localeCompare(b.firstDate) : a.kind === 'Shortage' ? -1 : 1))
    .map((action) => ({ ...action, message: action.kind === 'Shortage'
      ? `Prepare ${action.maxShortage} additional unit${action.maxShortage === 1 ? '' : 's'}; pressure continues on ${action.days} day${action.days === 1 ? '' : 's'}.`
      : `Place a reorder before stock crosses its safety threshold; signal continues on ${action.days} day${action.days === 1 ? '' : 's'}.` }))
  const summaries = plans.map(physicalSummary)
  const firstAction = sortedActions[0]
  return {
    shortageDays: summaries.filter((item) => item.shortages.length).length,
    actions: sortedActions,
    highestRisk: summaries.reduce((risk, item) => riskOrder[item.status] > riskOrder[risk] ? item.status : risk, 'Normal'),
    firstPressure: firstAction?.firstDate || null,
    firstAction: firstAction ? formatResource(firstAction.resource) : null,
    pressure,
    peakBedPressure: peakBed.pressure,
    peakBedResource: peakBed.resource,
  }
}

function addAction(actions, resource, kind, date, shortage) {
  const current = actions.get(resource) || { resource, kind, firstDate: date, days: 0, maxShortage: 0 }
  current.days += 1; current.maxShortage = Math.max(current.maxShortage, shortage); if (kind === 'Shortage') current.kind = kind
  actions.set(resource, current)
}
