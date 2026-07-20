import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { api } from '../../api.js'
import MetricCard from '../../components/MetricCard.jsx'

const HORIZONS = [5, 7, 14, 21]
const ACT_COLOR = { login: '#2563eb', planning_run: '#0891b2', roster_approved: '#16a34a', override: '#d97706', alert_sent: '#dc2626' }

export default function FairnessPage() {
  const [status, setStatus] = useState(null)
  const [model, setModel] = useState(null)
  const [audit, setAudit] = useState([])
  const [activity, setActivity] = useState([])
  const [horizon, setHorizon] = useState(7)
  const [roster, setRoster] = useState(null)
  const [group, setGroup] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const refreshAudit = () => {
    api.auditLog().then((d) => setAudit(d.entries)).catch(() => {})
    api.auditActivity().then((d) => setActivity(d.activity)).catch(() => {})
  }
  useEffect(() => {
    api.systemStatus().then(setStatus).catch(() => {})
    api.modelInfo().then(setModel).catch(() => {})
    refreshAudit()
  }, [])

  const analyse = () => {
    setLoading(true); setError(''); setRoster(null)
    api.workforceGenerate(horizon).then((r) => {
      setRoster(r); setGroup(r.fairness_report.groups[0]?.group || null)
    }).catch((e) => setError(e.message)).finally(() => setLoading(false))
  }

  const approve = async () => {
    await api.auditAction({ action: 'roster_approved', entity: roster.roster_run_id, reason: 'reviewed and approved' }).catch(() => {})
    refreshAudit()
  }
  const override = async () => {
    const reason = window.prompt('Reason for override (required):')
    if (!reason) return
    await api.auditAction({ action: 'override', entity: roster.roster_run_id, reason }).catch(() => {})
    refreshAudit()
  }

  const fr = roster?.fairness_report
  const grp = fr?.groups.find((g) => g.group === group)

  return (
    <div className="dashboard">
      <div className="page-head">
        <div>
          <h1>Fairness &amp; Audit</h1>
          <p className="muted">Governance: workload equity within comparable roles, decision audit trail,
            model transparency, and safety controls.</p>
        </div>
      </div>

      {/* System status */}
      {status && (
        <div className="status-badges">
          <span className={`sb ${status.model_ready ? 'ok' : 'bad'}`}>● Forecast model {status.model_ready ? 'ready' : 'unavailable'}</span>
          <span className={`sb ${status.database_connected ? 'ok' : 'bad'}`}>● Database {status.database_connected ? 'connected' : 'down'}</span>
          <span className={`sb ${status.llm_configured ? 'ok' : 'warn'}`}>● AI summaries {status.llm_configured ? 'on' : 'rule-based fallback'}</span>
          <span className="sb neutral">Data through {status.last_data_date}</span>
        </div>
      )}

      {/* Fairness */}
      <div className="page-head" style={{ marginTop: '0.4rem' }}>
        <h2 style={{ margin: 0 }}>Workforce fairness</h2>
        <div className="controls-row">
          <div className="segmented">
            {HORIZONS.map((h) => <button key={h} className={horizon === h ? 'seg active' : 'seg'} onClick={() => setHorizon(h)}>{h}d</button>)}
          </div>
          <button className="run-btn" onClick={analyse} disabled={loading}>{loading ? 'Analysing…' : 'Analyse roster'}</button>
        </div>
      </div>
      {error && <div className="banner error">{error}</div>}
      {loading && <div className="banner">Generating a roster and measuring fairness…</div>}

      {fr && !loading && (
        <>
          <div className="metric-row">
            <MetricCard label="Shift Equity Index" value={fr.shift_equity_index} tone={fr.shift_equity_index >= 75 ? 'good' : 'warn'} sub="higher = fairer" />
            <MetricCard label="Workload variance" value={fr.workload_variance} sub="shifts per staff" />
            <MetricCard label="Rest compliance" value={`${fr.rest_compliance_pct}%`} tone="good" sub="min-rest enforced" />
            <MetricCard label="Preference satisfaction" value={`${roster.preference_satisfaction.satisfaction_pct}%`} />
            <MetricCard label="Overtime hours" value={roster.overtime_metrics.total_overtime_hours} />
          </div>

          <section className="panel">
            <div className="panel-head">
              <h2>Night &amp; weekend load within a role group</h2>
              <select value={group || ''} onChange={(e) => setGroup(e.target.value)}>
                {fr.groups.map((g) => <option key={g.group} value={g.group}>{g.group.replace(/_/g, ' ')}</option>)}
              </select>
            </div>
            <p className="muted small">Compared only within the same role — equal bars = fair distribution. Doctors are never compared with nurses.</p>
            {grp && (
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={grp.members} margin={{ top: 8, right: 12, bottom: 4, left: -12 }}>
                  <CartesianGrid stroke="#eef1f5" vertical={false} />
                  <XAxis dataKey="staff_name" tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} axisLine={{ stroke: '#e2e8f0' }} interval={0} angle={-15} textAnchor="end" height={50} />
                  <YAxis tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={false} width={30} allowDecimals={false} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="nights" name="Nights" fill="#1e3a8a" radius={[3, 3, 0, 0]} isAnimationActive={false} />
                  <Bar dataKey="weekends" name="Weekends" fill="#ea580c" radius={[3, 3, 0, 0]} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            )}
            <div className="govern-note">✓ No protected attributes (gender, caste, age, religion) are collected or used — only qualification, skill, availability and working-hour limits.</div>
            <div className="controls-row">
              <button className="run-btn small" onClick={approve}>✓ Approve roster</button>
              <button className="logout-btn" onClick={override}>Override (reason)</button>
            </div>
          </section>
        </>
      )}

      {/* Audit + model + governance */}
      <div className="grid-2">
        <section className="panel">
          <h2>Audit trail</h2>
          <p className="muted small">Every automated decision and human override is recorded.</p>
          {activity.length > 0 && (
            <ResponsiveContainer width="100%" height={130}>
              <BarChart data={activity} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
                <XAxis dataKey="action" tick={{ fontSize: 9, fill: '#64748b' }} tickLine={false} axisLine={{ stroke: '#e2e8f0' }} />
                <YAxis tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} axisLine={false} width={28} allowDecimals={false} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }} />
                <Bar dataKey="count" radius={[3, 3, 0, 0]} isAnimationActive={false}>
                  {activity.map((a) => <Cell key={a.action} fill={ACT_COLOR[a.action] || '#94a3b8'} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
          <div className="table-scroll" style={{ maxHeight: 240 }}>
            <table className="data-table">
              <thead><tr><th>Time</th><th>User</th><th>Action</th><th>Detail</th></tr></thead>
              <tbody>
                {audit.map((a) => (
                  <tr key={a.id}>
                    <td>{a.timestamp ? new Date(a.timestamp).toLocaleString() : '—'}</td>
                    <td>{a.user}</td>
                    <td><span className="pill tone-warn">{a.action}</span></td>
                    <td className="explain">{a.reason || a.detail || a.entity || '—'}</td>
                  </tr>
                ))}
                {audit.length === 0 && <tr><td colSpan={4} className="muted">No entries yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>

        <section className="panel">
          <h2>Model transparency</h2>
          {model ? (
            <table className="data-table">
              <tbody>
                <tr><td>Selected model</td><td><strong>{model.selected_model}</strong></td></tr>
                <tr><td>Total-patient R²</td><td>{model.total_r2}</td></tr>
                <tr><td>Total-patient WAPE</td><td>{model.total_wape_pct}%</td></tr>
                <tr><td>Features · targets</td><td>{model.n_features} · {model.n_targets}</td></tr>
                <tr><td>Test window</td><td>after {model.split.val_end}</td></tr>
                <tr><td>Trained</td><td>{model.trained_at ? new Date(model.trained_at).toLocaleDateString() : '—'}</td></tr>
              </tbody>
            </table>
          ) : <p className="muted">Model info unavailable.</p>}
          <div className="govern-note">Predictions carry an ~80% uncertainty band and a "beyond historical data" note — they are guidance, not guarantees.</div>

          <h2 style={{ marginTop: '1rem' }}>Safety &amp; oversight</h2>
          <ul className="govern-list">
            <li>👤 <b>Human-in-the-loop:</b> AI recommends; the administrator approves. Overrides require a logged reason.</li>
            <li>🔒 <b>Security:</b> hashed passwords (bcrypt), JWT sessions, role-based access (only an emergency officer can dispatch alerts), secrets kept out of the repo.</li>
            <li>🛡️ <b>Privacy:</b> no identifiable patient records — only aggregate counts. Patients use guest access.</li>
            <li>🩺 <b>Patient safety:</b> no diagnosis or treatment; red-flag symptoms escalate to emergency services.</li>
          </ul>
        </section>
      </div>
    </div>
  )
}
