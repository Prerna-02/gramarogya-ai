// A single KPI tile. `tone` optionally colours the value (status).
export default function MetricCard({ label, value, sub, tone }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className={`metric-value ${tone ? `tone-${tone}` : ''}`}>{value}</div>
      {sub && <div className="metric-sub">{sub}</div>}
    </div>
  )
}
