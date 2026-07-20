import { useEffect, useState } from 'react'
import { CircleMarker, MapContainer, TileLayer, Tooltip } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

import { api } from '../../api.js'
import MetricCard from '../../components/MetricCard.jsx'

const HORIZONS = [7, 14, 21, 30]
const TONE = { Normal: 'good', Watch: 'warn', High: 'serious', Critical: 'critical' }
const FAC_TONE = { Available: 'good', Limited: 'warn', Busy: 'serious' }
const STATUS_COLOR = { Available: '#16a34a', Limited: '#d97706', Busy: '#dc2626' }

// Primary case-study hospital (Gadchiroli town).
const PRIMARY = { name: 'Gadchiroli Rural Hospital (primary)', latitude: 20.1809, longitude: 80.0033 }
const CENTER = [19.85, 80.05]

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

  const mapped = facilities.filter((f) => f.latitude != null && f.longitude != null)

  return (
    <div className="dashboard">
      <div className="page-head">
        <div>
          <h1>Emergency & Network</h1>
          <p className="muted">Capacity/overload check and nearby-facility readiness around Gadchiroli.</p>
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
            <MetricCard label="Overload days" value={cap.overload_days.length} tone={cap.overload_days.length ? 'serious' : 'good'} sub={`of ${horizon}`} />
            <MetricCard label="Nearby facilities" value={facilities.length} sub={`${facilities.filter((f) => f.status === 'Available').length} available`} />
          </div>

          <section className="panel">
            <h2>Emergency network map</h2>
            <div className="map-wrap">
              <MapContainer center={CENTER} zoom={9} scrollWheelZoom={false} style={{ height: 360, borderRadius: 10 }}>
                <TileLayer attribution="&copy; OpenStreetMap"
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                <CircleMarker center={[PRIMARY.latitude, PRIMARY.longitude]} radius={11}
                  pathOptions={{ color: '#1e3a8a', fillColor: '#2563eb', fillOpacity: 0.9 }}>
                  <Tooltip permanent direction="top" offset={[0, -8]}>{PRIMARY.name}</Tooltip>
                </CircleMarker>
                {mapped.map((f) => (
                  <CircleMarker key={f.id} center={[f.latitude, f.longitude]} radius={9}
                    pathOptions={{ color: '#334155', fillColor: STATUS_COLOR[f.status] || '#64748b', fillOpacity: 0.85 }}>
                    <Tooltip direction="top" offset={[0, -8]}>
                      <strong>{f.name}</strong><br />{f.type} · {f.status}<br />{f.beds_available} beds · {f.travel_time_min} min
                    </Tooltip>
                  </CircleMarker>
                ))}
              </MapContainer>
              <div className="map-legend">
                <span><i style={{ background: '#2563eb' }} /> Primary hospital</span>
                <span><i style={{ background: '#16a34a' }} /> Available</span>
                <span><i style={{ background: '#d97706' }} /> Limited</span>
                <span><i style={{ background: '#dc2626' }} /> Busy</span>
              </div>
            </div>
            <p className="muted small">Approximate prototype locations — a verified facility geodata set is
              required before operational use.</p>
          </section>

          <div className="grid-2">
            <section className="panel">
              <h2>Daily capacity risk</h2>
              <div className="table-scroll" style={{ maxHeight: 360 }}>
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
