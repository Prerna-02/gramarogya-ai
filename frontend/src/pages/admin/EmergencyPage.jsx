import { useEffect, useState } from 'react'

import { api } from '../../api.js'
import MetricCard from '../../components/MetricCard.jsx'

const HORIZONS = [7, 14, 21, 30]
const TONE = { Normal: 'good', Watch: 'warn', High: 'serious', Critical: 'critical' }
const FAC_TONE = { Available: 'good', Limited: 'warn', Busy: 'serious' }

export default function EmergencyPage() {
  const [horizon, setHorizon] = useState(7)
  const [cap, setCap] = useState(null)
  const [facilities, setFacilities] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true); setError('')
    Promise.all([api.emergencyCheck(horizon), api.facilities()])
      .then(([c, f]) => { setCap(c); setFacilities(f.facilities) })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [horizon])

  return (
    <div className="dashboard">
      <div className="page-head">
        <div>
          <h1>Emergency & Network</h1>
          <p className="muted">Capacity/overload check and nearby-facility readiness.</p>
        </div>
        <div className="segmented">
          {HORIZONS.map((h) => (
            <button key={h} className={horizon === h ? 'seg active' : 'seg'} onClick={() => setHorizon(h)}>{h}d</button>
          ))}
        </div>
      </div>

      {error && <div className="banner error">{error}</div>}
      {loading && <div className="banner">Checking capacity…</div>}

      {cap && !loading && (
        <>
          <div className="metric-row">
            <MetricCard label="Overall risk" value={cap.overall_risk} tone={TONE[cap.overall_risk]} />
            <MetricCard label="Overload days" value={cap.overload_days.length}
              tone={cap.overload_days.length ? 'serious' : 'good'} sub={`of ${horizon}`} />
            <MetricCard label="Nearby facilities" value={facilities.length}
              sub={`${facilities.filter((f) => f.status === 'Available').length} available`} />
          </div>

          <div className="grid-2">
            <section className="panel">
              <h2>Daily capacity risk</h2>
              <div className="table-scroll" style={{ maxHeight: 420 }}>
                <table className="data-table">
                  <thead><tr><th>Date</th><th>Status</th><th>Shortages</th></tr></thead>
                  <tbody>
                    {cap.days.map((d) => (
                      <tr key={d.date}>
                        <td>{d.date}</td>
                        <td><span className={`pill tone-${TONE[d.status]}`}>{d.status}</span></td>
                        <td>{d.shortages.length ? d.shortages.join(', ') : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="panel">
              <h2>Nearby facility readiness</h2>
              <table className="data-table">
                <thead><tr><th>Facility</th><th>Type</th><th>Distance</th><th>Travel</th><th>Beds</th><th>Status</th></tr></thead>
                <tbody>
                  {facilities.map((f) => (
                    <tr key={f.id}>
                      <td>{f.name}</td><td>{f.type}</td><td>{f.distance_km} km</td>
                      <td>{f.travel_time_min} min</td><td>{f.beds_available}</td>
                      <td><span className={`pill tone-${FAC_TONE[f.status]}`}>{f.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="muted small">Prototype network — verify availability before referral.</p>
            </section>
          </div>
        </>
      )}
    </div>
  )
}
