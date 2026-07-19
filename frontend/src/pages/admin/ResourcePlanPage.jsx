import { useEffect, useState } from 'react'

import { api } from '../../api.js'

const HORIZONS = [7, 14, 21, 30]
const STATUS_TONE = { Normal: 'good', Watch: 'warn', High: 'serious', Critical: 'critical' }

function Section({ title, items }) {
  return (
    <>
      <tr className="group-row"><td colSpan={5}>{title}</td></tr>
      {items.map((it) => (
        <tr key={it.resource} className={it.shortage > 0 ? 'short' : ''}>
          <td>{it.resource}</td>
          <td>{it.required}</td>
          <td>{it.available}</td>
          <td>{it.shortage > 0 ? <strong className="tone-critical">{it.shortage}</strong> : '0'}</td>
          <td className="explain">{it.explanation}</td>
        </tr>
      ))}
    </>
  )
}

export default function ResourcePlanPage() {
  const [horizon, setHorizon] = useState(7)
  const [plans, setPlans] = useState(null)
  const [sel, setSel] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true); setError(''); setSel(0)
    api.resourcesPlan(horizon)
      .then((d) => setPlans(d.plans))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [horizon])

  const day = plans && plans[sel]

  return (
    <div className="dashboard">
      <div className="page-head">
        <div>
          <h1>Resource Planning</h1>
          <p className="muted">Forecast converted into required staff, beds, medicines, oxygen and ambulances.</p>
        </div>
        <div className="segmented">
          {HORIZONS.map((h) => (
            <button key={h} className={horizon === h ? 'seg active' : 'seg'} onClick={() => setHorizon(h)}>{h} days</button>
          ))}
        </div>
      </div>

      {error && <div className="banner error">{error}</div>}
      {loading && <div className="banner">Planning {horizon} days…</div>}

      {plans && !loading && (
        <div className="grid-2">
          <section className="panel">
            <h2>Daily status</h2>
            <table className="data-table">
              <thead><tr><th>Date</th><th>Status</th><th>Shortages</th></tr></thead>
              <tbody>
                {plans.map((p, i) => (
                  <tr key={p.date} className={i === sel ? 'row-sel' : 'row-click'} onClick={() => setSel(i)}>
                    <td>{p.date}</td>
                    <td><span className={`pill tone-${STATUS_TONE[p.summary.status]}`}>{p.summary.status}</span></td>
                    <td>{p.summary.shortages.length ? p.summary.shortages.join(', ') : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="panel">
            <h2>Breakdown — {day?.date}</h2>
            <p className="muted small">Forecast: {day?.forecast.total_patient_arrivals} patients
              ({day?.forecast.fever_infectious_arrivals} fever, {day?.forecast.trauma_emergency_arrivals} trauma)</p>
            <div className="table-scroll" style={{ maxHeight: 420 }}>
              <table className="data-table">
                <thead><tr><th>Resource</th><th>Req</th><th>Avail</th><th>Short</th><th>How it was calculated</th></tr></thead>
                <tbody>
                  {day && <Section title="Staff" items={Object.values(day.staff)} />}
                  {day && <Section title="Beds" items={Object.values(day.beds)} />}
                  {day && <Section title="Medicines" items={Object.values(day.medicines)} />}
                  {day && <Section title="Oxygen & Ambulance" items={[day.oxygen, day.ambulances]} />}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}
    </div>
  )
}
