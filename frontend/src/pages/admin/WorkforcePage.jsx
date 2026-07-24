import { useState } from 'react'

import { api } from '../../api.js'
import MetricCard from '../../components/MetricCard.jsx'
import OptimizationComparisonChart from '../../components/OptimizationComparisonChart.jsx'
import WorkforceCoverageChart from '../../components/WorkforceCoverageChart.jsx'
import WorkforceGapHeatmap from '../../components/WorkforceGapHeatmap.jsx'
import WorkforceLoadCharts from '../../components/WorkforceLoadCharts.jsx'

const HORIZONS = [5, 7, 14, 21]

export default function WorkforcePage() {
  const [horizon, setHorizon] = useState(7)
  const [roster, setRoster] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [dateFilter, setDateFilter] = useState('all')
  const [showMath, setShowMath] = useState(false)
  const [decision, setDecision] = useState('')

  const generate = () => {
    setLoading(true); setError(''); setRoster(null); setDateFilter('all'); setDecision('')
    api.workforceGenerate(horizon).then(setRoster).catch((err) => setError(err.message)).finally(() => setLoading(false))
  }

  const approve = async () => {
    await api.auditAction({ action: 'roster_approved', entity: roster.roster_run_id, reason: 'reviewed and approved' }).catch(() => {})
    setDecision('Roster approved and recorded in the audit trail (see Fairness & Audit).')
  }
  const recordException = async () => {
    const reason = window.prompt('Describe why the administrator is departing from the recommended roster (required):')
    if (!reason) return
    await api.auditAction({ action: 'override', entity: roster.roster_run_id, reason }).catch(() => {})
    setDecision('Exception decision recorded in the audit trail (see Fairness & Audit).')
  }

  const assignments = roster?.recommended_roster ?? []
  const dates = [...new Set(assignments.map((item) => item.date))].sort()
  const shown = dateFilter === 'all' ? assignments : assignments.filter((item) => item.date === dateFilter)
  const scores = roster?.recommended_roster_scores
  const unmet = roster?.unmet_staffing_requirements ?? []
  const missingStaffSlots = unmet.reduce((sum, item) => sum + item.shortfall, 0)
  const affectedDays = new Set(unmet.map((item) => item.date)).size
  const constrainedRole = unmet.length ? Object.entries(unmet.reduce((counts, item) => {
    counts[item.designation] = (counts[item.designation] || 0) + item.shortfall
    return counts
  }, {})).sort((a, b) => b[1] - a[1])[0]?.[0] : null
  const plannedHours = roster?.fairness_report.groups.reduce((sum, group) => sum + group.members.reduce((groupSum, member) => groupSum + member.hours, 0), 0) || 0
  const overtimeHours = roster?.overtime_metrics.total_overtime_hours || 0
  const overtimeShare = plannedHours ? (100 * overtimeHours / plannedHours).toFixed(1) : '0.0'

  return <div className="dashboard">
    <div className="page-head"><div><h1>Workforce Roster</h1><p className="muted">NSGA-II balanced roster — named staff by date, shift, department and role.</p></div>
      <div className="controls-row"><div className="segmented">{HORIZONS.map((days) => <button key={days} className={horizon === days ? 'seg active' : 'seg'} onClick={() => setHorizon(days)}>{days}d</button>)}</div>
        <button className="run-btn" onClick={generate} disabled={loading}>{loading ? 'Optimising…' : 'Generate roster'}</button></div>
    </div>

    {error && <div className="banner error">{error}</div>}
    {loading && <div className="banner">Running NSGA-II optimisation for {horizon} days…</div>}
    {!roster && !loading && <div className="banner">Pick a horizon and click <strong>Generate roster</strong>.</div>}

    {roster && !loading && <>
      <div className="metric-row workforce-metrics">
        <MetricCard label="Service coverage" value={`${scores.coverage_pct}%`} tone={scores.coverage_pct >= 90 ? 'good' : scores.coverage_pct >= 75 ? 'warn' : 'serious'} />
        <MetricCard label="Assignments" value={assignments.length} sub={`${dates.length} days`} />
        <MetricCard label="Open staff-slots" value={missingStaffSlots} sub={`${unmet.length} shift-role gaps across ${affectedDays} day${affectedDays === 1 ? '' : 's'}`} tone={missingStaffSlots ? 'warn' : 'good'} />
        <MetricCard label="Preference fit" value={`${roster.preference_satisfaction.satisfaction_pct}%`} sub="preferred shift and weekly-off fit" />
        <MetricCard label="Overtime share" value={`${overtimeShare}%`} sub={`${overtimeHours} staff-hours above target`} />
      </div>

      <div className="definition-note"><strong>What is an open staff-slot?</strong>
        <p>It is one required person on a specific date, shift and role that the optimizer could not assign without breaking a hard rule. It is not a count of unique employees. There are <b>{missingStaffSlots} open staff-slot{missingStaffSlots === 1 ? '' : 's'}</b>{constrainedRole ? `; ${constrainedRole} is currently the most constrained role` : ''}.</p>
      </div>

      <div className="grid-2 workforce-analytics-grid">
        <section className="panel"><div className="panel-heading-copy"><h2>Required versus assigned by role</h2><p>Compares the full staffing requirement with the optimizer's assigned coverage. The largest gaps appear first.</p></div>
          <WorkforceCoverageChart data={roster.coverage_by_role} />
        </section>
        <section className="panel"><div className="panel-heading-copy"><h2>Optimization impact</h2><p>Compares NSGA-II with a deterministic first-eligible baseline under the same hard scheduling rules.</p></div>
          <OptimizationComparisonChart comparison={roster.baseline_comparison} plannedHours={plannedHours} />
        </section>
      </div>

      <section className="panel panel-featured workforce-gap-panel"><div className="panel-heading-copy"><h2>Coverage gaps by date and shift</h2><p>Each cell shows assigned versus required staff. Amber or red cells identify exactly when administrator action is needed.</p></div>
        <WorkforceGapHeatmap data={roster.coverage_by_date_shift} />
      </section>

      <WorkforceLoadCharts groups={roster.fairness_report.groups} />

      <section className="panel fairness-decision-panel"><div className="panel-heading-copy"><h2>Roster fairness &amp; administrator decision</h2><p>Fairness is measured within like-for-like role groups—a doctor is compared only with doctors—and no protected attributes are used. Approve the roster or record an exception; both are written to the audit trail.</p></div>
        <div className="metric-row">
          <MetricCard label="Shift Equity Index" value={roster.fairness_report.shift_equity_index} tone={roster.fairness_report.shift_equity_index >= 75 ? 'good' : 'warn'} sub="higher = fairer share of hard shifts" />
          <MetricCard label="Workload variance" value={roster.fairness_report.workload_variance} sub="spread of shifts per staff in a group" />
          <MetricCard label="Rest compliance" value={`${roster.fairness_report.rest_compliance_pct}%`} tone="good" sub="hard minimum-rest rule" />
        </div>
        <div className="govern-note">No protected attributes such as gender, caste, age or religion are collected or used—only qualification, skill, availability and working-hour limits.</div>
        <div className="controls-row"><button className="run-btn small" onClick={approve}>Approve roster</button><button className="logout-btn" onClick={recordException}>Record exception decision</button></div>
        {decision && <div className="banner">{decision}</div>}
      </section>

      <section className="plan-method"><div><strong>How this plan was chosen</strong><span>{roster.recommendation_reason}</span></div>
        <label className="switch"><input type="checkbox" checked={showMath} onChange={(event) => setShowMath(event.target.checked)} /><span className="switch-track"><span className="switch-thumb" /></span>Technical details</label>
        {showMath && <div className="plan-method-details">
          {roster.optimization_metadata.objective_names.map((name, index) => <span key={name}><b>{name.replace(/_/g, ' ')}</b>{roster.optimization_metadata.objective_values[index]}</span>)}
          <span><b>feasible solutions</b>{roster.optimization_metadata.feasible_solutions}</span>
          <span><b>population × generations</b>{roster.optimization_metadata.population_size} × {roster.optimization_metadata.generations}</span>
          <span><b>execution time</b>{roster.optimization_metadata.execution_time_sec}s</span>
        </div>}
      </section>

      <div className="grid-2 workforce-detail-grid">
        <section className="panel"><div className="panel-head"><h2>Roster assignments</h2><select value={dateFilter} onChange={(event) => setDateFilter(event.target.value)}><option value="all">All dates</option>{dates.map((date) => <option key={date} value={date}>{date}</option>)}</select></div>
          <div className="table-scroll" style={{ maxHeight: 480 }}><table className="data-table"><thead><tr><th>Date</th><th>Shift</th><th>Department</th><th>Role</th><th>Staff</th><th>Status</th></tr></thead><tbody>
            {shown.map((item, index) => <tr key={`${item.staff_id}-${item.date}-${item.shift}-${index}`}><td>{item.date.slice(5)}</td><td>{item.shift}</td><td>{item.department}</td><td>{item.assigned_role}</td><td>{item.staff_name}</td>
              <td>{item.confirmed_or_provisional === 'provisional' ? <span className="pill tone-warn">Provisional</span> : <span className="pill tone-good">Confirmed</span>}</td></tr>)}
          </tbody></table></div>
        </section>
        <section className="panel"><h2>Unfilled shift requirements ({unmet.length})</h2><p className="muted small">A recommended response is an administrator option outside the optimizer—not an assignment already made.</p><div className="table-scroll" style={{ maxHeight: 480 }}><table className="data-table"><thead><tr><th>Date</th><th>Shift</th><th>Role</th><th>Short</th><th>Recommended response</th></tr></thead><tbody>
          {unmet.map((item, index) => <tr key={`${item.date}-${item.shift}-${item.designation}-${index}`}><td>{item.date.slice(5)}</td><td>{item.shift}</td><td>{item.designation}</td><td><strong className="tone-critical">{item.shortfall}</strong></td><td className="explain">{item.recommended_action}</td></tr>)}
          {!unmet.length && <tr><td colSpan="5" className="empty-state-good">All mandatory staffing requirements are covered.</td></tr>}
        </tbody></table></div></section>
      </div>
    </>}
  </div>
}
