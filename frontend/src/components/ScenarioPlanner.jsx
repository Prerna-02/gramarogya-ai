import { useEffect, useMemo, useRef, useState } from 'react'
import { Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip as LTooltip } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

import { api } from '../api.js'

const RISK_TONE = { Normal: 'good', Watch: 'warn', High: 'serious', Critical: 'critical' }
const PRIMARY = { name: 'Gadchiroli Rural Hospital', lat: 20.1849, lon: 79.9948 }
const PHASE_LABEL = { sending: 'Sending…', delivered: 'Delivered', ack: 'Acknowledged', accepted: 'Accepted', declined: 'Declined' }
const PHASE_COLOR = { idle: '#94a3b8', sending: '#2563eb', delivered: '#2563eb', ack: '#d97706', accepted: '#16a34a', declined: '#dc2626' }

function useCountUp(target, ms = 900) {
  const [v, setV] = useState(0)
  useEffect(() => {
    let raf, start
    const step = (t) => {
      if (!start) start = t
      const p = Math.min(1, (t - start) / ms)
      setV(Math.round(target * p))
      if (p < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [target, ms])
  return v
}

function Impact({ sim }) {
  const peak = useCountUp(sim.impact.peak_surged)
  const extra = useCountUp(sim.impact.extra_patients)
  const overflow = useCountUp(sim.impact.overflow_estimate)
  return (
    <div className="metric-row">
      <div className="metric-card"><div className="metric-label">Risk level</div>
        <div className={`metric-value tone-${RISK_TONE[sim.impact.risk_level]} risk-pulse`}>{sim.impact.risk_level}</div>
        <div className="metric-sub">peak {sim.impact.peak_date}</div></div>
      <div className="metric-card"><div className="metric-label">Peak inflow (mostly OPD)</div>
        <div className="metric-value">{peak}</div><div className="metric-sub">baseline {sim.impact.peak_baseline} · +{extra} over {sim.horizon}d</div></div>
      <div className="metric-card"><div className="metric-label">Admissions (need beds)</div>
        <div className="metric-value tone-warn">{sim.impact.baseline_admissions}→{sim.impact.surged_admissions}</div>
        <div className="metric-sub">only inpatients use beds</div></div>
      <div className="metric-card"><div className="metric-label">Projected overflow</div>
        <div className={`metric-value ${overflow ? 'tone-critical' : 'tone-good'}`}>{overflow}</div>
        <div className="metric-sub">beds beyond capacity</div></div>
    </div>
  )
}

export default function ScenarioPlanner() {
  const [scenarios, setScenarios] = useState([])
  const [sel, setSel] = useState(null)
  const [severity, setSeverity] = useState(3)
  const [sim, setSim] = useState(null)
  const [loading, setLoading] = useState(false)
  const [phase, setPhase] = useState({})
  const [sent, setSent] = useState(false)
  const timers = useRef([])

  useEffect(() => {
    api.emergencyScenarios().then((d) => { setScenarios(d.scenarios); setSel(d.scenarios[0]?.id) }).catch(() => {})
    return () => timers.current.forEach(clearTimeout)
  }, [])

  const simulate = () => {
    setLoading(true); setSim(null); setSent(false); setPhase({})
    timers.current.forEach(clearTimeout); timers.current = []
    api.emergencySimulate(sel, severity).then(setSim).catch(() => {}).finally(() => setLoading(false))
  }

  const dispatch = async () => {
    setSent(true)
    try {
      await api.emergencySendAlert({ scenario: sim.scenario.name, severity: sim.severity,
        requested_support: sim.alert.requested_support, facility_ids: sim.facilities.map((f) => f.id) })
    } catch { /* still animate */ }
    const init = {}; sim.facilities.forEach((f) => { init[f.id] = 'sending' }); setPhase(init)
    sim.facilities.forEach((f, i) => {
      const base = 400 + i * 650
      const final = f.status === 'Busy' ? 'declined' : 'accepted'
      timers.current.push(setTimeout(() => setPhase((p) => ({ ...p, [f.id]: 'delivered' })), base))
      timers.current.push(setTimeout(() => setPhase((p) => ({ ...p, [f.id]: 'ack' })), base + 700))
      timers.current.push(setTimeout(() => setPhase((p) => ({ ...p, [f.id]: final })), base + 1400))
    })
  }

  const maxReq = useMemo(() => sim ? Math.max(...sim.resources.map((r) => Math.max(r.surged, r.available))) : 1, [sim])
  const bedsSecured = sim ? sim.facilities.filter((f) => phase[f.id] === 'accepted').reduce((s, f) => s + f.beds_available, 0) : 0
  const accepted = sim ? sim.facilities.filter((f) => phase[f.id] === 'accepted').length : 0

  return (
    <section className="panel scenario-planner">
      <div className="panel-head"><h2>⚡ Scenario Planning</h2><span className="pill tone-warn">simulator</span></div>
      <p className="muted small">Pick a scenario and severity to see the surge on top of the baseline forecast,
        its impact on this hospital, the precautions to take, and how alerts flow to nearby facilities.</p>

      <div className="scen-cards">
        {scenarios.map((s) => (
          <button key={s.id} className={`scen-card ${sel === s.id ? 'active' : ''}`} onClick={() => setSel(s.id)}>
            <span className="scen-ic">{s.icon}</span>
            <span className="scen-name">{s.name}</span>
            {s.examples && <span className="scen-ex">{s.examples}</span>}
            <span className="scen-cat">{s.category}</span>
          </button>
        ))}
      </div>

      <div className="scen-controls">
        <label>Severity <b>{severity}</b>/5
          <input type="range" min="1" max="5" value={severity} onChange={(e) => setSeverity(+e.target.value)} />
        </label>
        <button className="run-btn" onClick={simulate} disabled={loading || !sel}>
          {loading ? 'Simulating…' : '▶ Simulate scenario'}
        </button>
      </div>

      {sim && !loading && (
        <div className="scen-results">
          <Impact key={`${sim.scenario.id}-${sim.severity}`} sim={sim} />

          <div className="grid-2">
            <div className="sub-panel">
              <h3>Forecast surge</h3>
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={sim.forecast} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
                  <CartesianGrid stroke="#eef1f5" vertical={false} />
                  <XAxis dataKey="date" tickFormatter={(d) => d.slice(5)} tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} axisLine={{ stroke: '#e2e8f0' }} />
                  <YAxis tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} axisLine={false} width={34} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Area dataKey="baseline_total" name="Baseline" stackId="1" stroke="#1e40af" fill="#93c5fd" fillOpacity={0.8} />
                  <Area dataKey="surge" name="Scenario surge" stackId="1" stroke="#dc2626" fill="#fca5a5" fillOpacity={0.85} />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            <div className="sub-panel">
              <h3>Impact on this hospital (peak day)</h3>
              <div className="res-bars">
                {sim.resources.map((r) => (
                  <div key={r.resource} className="res-row">
                    <span className="res-name">{r.resource.replace(/_/g, ' ')}</span>
                    <div className="res-track">
                      <div className={`res-fill ${r.shortage > 0 ? 'short' : ''}`} style={{ width: `${Math.min(100, (r.surged / maxReq) * 100)}%` }} />
                      <div className="res-avail" style={{ left: `${Math.min(100, (r.available / maxReq) * 100)}%` }} title="available" />
                    </div>
                    <span className="res-num">{r.baseline}→<b>{r.surged}</b>{r.shortage > 0 && <em className="tone-critical"> −{r.shortage}</em>}</span>
                  </div>
                ))}
              </div>
              <p className="muted small">Bar = required under surge · marker = available · red = shortage.</p>
              <p className="muted small">Most inflow is outpatient (seen &amp; sent home). Beds only serve
                <b> admissions</b>, so bed pressure is far smaller than total footfall — while staff and
                consumables scale with the whole surge.</p>
            </div>
          </div>

          <div className="grid-2">
            <div className="sub-panel">
              <h3>Precautions for this hospital</h3>
              <ul className="precautions">
                {sim.precautions.map((p, i) => (
                  <li key={i} style={{ animationDelay: `${i * 0.12}s` }}>✓ {p}</li>
                ))}
              </ul>
            </div>

            <div className="sub-panel">
              <div className="panel-head">
                <h3>Alert nearby facilities</h3>
                {!sent && <button className="run-btn small" onClick={dispatch}>📡 Send alerts (approve)</button>}
              </div>
              {sent && <div className="dispatch-progress">{accepted} of {sim.facilities.length} accepted · {bedsSecured} beds secured</div>}
              <div className="dispatch-map">
                <MapContainer center={[19.9, 80.05]} zoom={8} scrollWheelZoom={false} style={{ height: 200, borderRadius: 8 }}>
                  <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap" />
                  <CircleMarker center={[PRIMARY.lat, PRIMARY.lon]} radius={9} pathOptions={{ color: '#1e3a8a', fillColor: '#2563eb', fillOpacity: 0.9 }}>
                    <LTooltip permanent direction="top" offset={[0, -6]}>Our hospital</LTooltip>
                  </CircleMarker>
                  {sim.facilities.filter((f) => f.latitude != null).map((f) => (
                    <span key={f.id}>
                      {sent && <Polyline positions={[[PRIMARY.lat, PRIMARY.lon], [f.latitude, f.longitude]]}
                        pathOptions={{ color: PHASE_COLOR[phase[f.id]] || '#94a3b8', weight: 2, opacity: 0.8, dashArray: phase[f.id] === 'accepted' ? null : '6 6' }} />}
                      <CircleMarker center={[f.latitude, f.longitude]} radius={7}
                        pathOptions={{ color: '#334155', fillColor: sent ? (PHASE_COLOR[phase[f.id]] || '#94a3b8') : (f.can_help ? '#16a34a' : '#94a3b8'), fillOpacity: 0.85 }}>
                        <LTooltip direction="top" offset={[0, -6]}>{f.name}</LTooltip>
                      </CircleMarker>
                    </span>
                  ))}
                </MapContainer>
              </div>
              <div className="dispatch-list">
                {sim.facilities.map((f) => (
                  <div key={f.id} className="dispatch-row">
                    <span className="dot" style={{ background: sent ? PHASE_COLOR[phase[f.id]] : (f.can_help ? '#16a34a' : '#cbd5e1') }} />
                    <span className="d-name">{f.name}</span>
                    <span className="d-meta">{f.travel_time_min}m · {f.beds_available} beds</span>
                    <span className={`d-phase ${phase[f.id] || ''}`}>{sent ? (PHASE_LABEL[phase[f.id]] || '…') : (f.can_help ? 'can help' : '—')}</span>
                  </div>
                ))}
              </div>
              <p className="muted small">Human-approved dispatch. Facility responses are simulated in this prototype.</p>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
