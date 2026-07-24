import { useEffect, useState } from 'react'
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { api } from '../../api.js'

const ACT_COLOR = { login: '#2563eb', planning_run: '#0891b2', roster_approved: '#16a34a', override: '#d97706', alert_sent: '#dc2626' }

const KPIS = [
  ['Shift Equity Index', '0–100, higher is fairer', 'How evenly the hard shifts—nights, weekends and on-call—are shared among staff doing the same job. 100 means everyone in that role group carries an equal share.'],
  ['Workload variance', 'lower is more even', 'The spread in the number of shifts assigned per person within a role group. A low value means nobody is overloaded while others sit idle.'],
  ['Preference fit', 'percentage', 'The share of assignments that matched a staff member’s preferred shift or weekly-off. Coverage and safety rank above preferences, so this is a genuine trade-off, not an error.'],
  ['Rest compliance', 'percentage', 'The share of assignments that respect the mandatory minimum rest between shifts. It is a hard rule, so it stays at 100%.'],
  ['Overtime share', 'percentage', 'Planned overtime hours as a fraction of total planned hours—how much the roster leans on extra hours rather than regular shifts.'],
]

export default function FairnessPage() {
  const [status, setStatus] = useState(null)
  const [model, setModel] = useState(null)
  const [audit, setAudit] = useState([])
  const [activity, setActivity] = useState([])

  useEffect(() => {
    api.systemStatus().then(setStatus).catch(() => {})
    api.modelInfo().then(setModel).catch(() => {})
    api.auditLog().then((result) => setAudit(result.entries)).catch(() => {})
    api.auditActivity().then((result) => setActivity(result.activity)).catch(() => {})
  }, [])

  return <div className="dashboard">
    <div className="page-head"><div><h1>Fairness &amp; Audit</h1><p className="muted">Governance review, decision audit trail, model transparency and safety controls.</p></div></div>

    {status && <div className="status-badges">
      <span className={`sb ${status.model_ready ? 'ok' : 'bad'}`}>● Forecast model {status.model_ready ? 'ready' : 'unavailable'}</span>
      <span className={`sb ${status.database_connected ? 'ok' : 'bad'}`}>● Database {status.database_connected ? 'connected' : 'down'}</span>
      <span className={`sb ${status.llm_configured ? 'ok' : 'warn'}`}>● AI summaries {status.llm_configured ? 'on' : 'fallback active'}</span>
      <span className="sb neutral">Data through {status.last_data_date}</span>
    </div>}

    <section className="panel fairness-decision-panel"><div className="panel-heading-copy"><h2>Workforce fairness — what we measure and how</h2>
      <p>The live values for these metrics, and the <strong>Approve roster</strong> / <strong>Record exception</strong> controls, sit on the <strong>Workforce Roster</strong> tab beside the roster they apply to. This is what each number means.</p></div>
      <div className="govern-note">Fairness is measured <strong>within like-for-like role groups</strong>—a doctor is compared only with doctors, a nurse only with nurses. No protected attributes such as gender, caste, age or religion are ever collected or used; only qualification, skill, availability and working-hour limits.</div>
      <div className="table-scroll"><table className="data-table"><thead><tr><th>Metric</th><th>Scale</th><th>What it tells you</th></tr></thead><tbody>
        {KPIS.map(([name, scale, meaning]) => <tr key={name}><td><strong>{name}</strong></td><td className="muted">{scale}</td><td className="explain">{meaning}</td></tr>)}
      </tbody></table></div>
      <div className="fairness-method-note"><strong>What is an exception decision?</strong><span>It records that an administrator chose to depart from the recommended roster. A reason is mandatory and remains visible in the audit trail; it never silently removes qualification, rest or maximum-hour safeguards.</span></div>
    </section>

    <div className="grid-2">
      <section className="panel"><h2>Audit trail</h2><p className="muted small">Every automated decision and administrator exception is recorded.</p>
        {activity.length > 0 && <ResponsiveContainer width="100%" height={150}><BarChart data={activity} margin={{ top: 4, right: 8, bottom: 0, left: -12 }}>
          <XAxis dataKey="action" tick={{ fontSize: 13, fill: '#64748b' }} /><YAxis tick={{ fontSize: 13, fill: '#64748b' }} width={32} allowDecimals={false} /><Tooltip />
          <Bar dataKey="count" radius={[4, 4, 0, 0]}>{activity.map((item) => <Cell key={item.action} fill={ACT_COLOR[item.action] || '#94a3b8'} />)}</Bar>
        </BarChart></ResponsiveContainer>}
        <div className="table-scroll" style={{ maxHeight: 260 }}><table className="data-table"><thead><tr><th>Time</th><th>User</th><th>Decision</th><th>Detail</th></tr></thead><tbody>
          {audit.map((item) => <tr key={item.id}><td>{item.timestamp ? new Date(item.timestamp).toLocaleString() : '—'}</td><td>{item.user}</td><td><span className="pill tone-warn">{item.action === 'override' ? 'exception' : item.action}</span></td><td className="explain">{item.reason || item.detail || item.entity || '—'}</td></tr>)}
          {!audit.length && <tr><td colSpan="4" className="muted">No entries yet.</td></tr>}
        </tbody></table></div>
      </section>

      <section className="panel"><h2>Model transparency</h2>
        {model ? <table className="data-table"><tbody><tr><td>Selected model</td><td><strong>{model.selected_model}</strong></td></tr><tr><td>Total-patient R²</td><td>{model.total_r2}</td></tr><tr><td>Total-patient WAPE</td><td>{model.total_wape_pct}%</td></tr><tr><td>Features · targets</td><td>{model.n_features} · {model.n_targets}</td></tr><tr><td>Test window</td><td>after {model.split.val_end}</td></tr><tr><td>Trained</td><td>{model.trained_at ? new Date(model.trained_at).toLocaleDateString() : '—'}</td></tr></tbody></table> : <p className="muted">Model information unavailable.</p>}
        <div className="govern-note">Predictions carry an approximately 80% uncertainty band. They are planning guidance, not guarantees.</div>
        <h2 style={{ marginTop: '1rem' }}>Safety &amp; oversight</h2><ul className="govern-list"><li><b>Human oversight:</b> AI recommends; the administrator approves or records an exception.</li><li><b>Security:</b> hashed passwords, JWT sessions and role-based access.</li><li><b>Privacy:</b> no identifiable patient records; planning uses aggregate counts.</li><li><b>Patient safety:</b> no diagnosis or treatment; red-flag symptoms escalate to emergency services.</li></ul>
      </section>
    </div>
  </div>
}
