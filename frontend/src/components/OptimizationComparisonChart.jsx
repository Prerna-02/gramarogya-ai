import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export default function OptimizationComparisonChart({ comparison, plannedHours = 0 }) {
  if (!comparison) return <p className="muted">No comparison data available.</p>
  const data = [
    { metric: 'Coverage', Baseline: comparison.baseline.coverage_pct, Optimized: comparison.optimized.coverage_pct, suffix: '%' },
    { metric: 'Preference fit', Baseline: comparison.baseline.preference_satisfaction_pct, Optimized: comparison.optimized.preference_satisfaction_pct, suffix: '%' },
  ]
  return <>
    <ResponsiveContainer width="100%" height={255}>
      <BarChart data={data} margin={{ top: 10, right: 18, left: 0, bottom: 4 }}>
        <CartesianGrid stroke="#edf1f5" vertical={false} />
        <XAxis dataKey="metric" tick={{ fontSize: 14, fill: '#475569' }} />
        <YAxis domain={[0, 100]} tick={{ fontSize: 14, fill: '#64748b' }} unit="%" />
        <Tooltip formatter={(value) => `${value}%`} />
        <Legend />
        <Bar dataKey="Baseline" fill="#b7c4d5" radius={[6, 6, 0, 0]} />
        <Bar dataKey="Optimized" fill="#0f766e" radius={[6, 6, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
    <div className="comparison-foot">
      <span><b>{comparison.baseline.unfilled_staff_slots}</b> baseline open slots</span>
      <span><b>{comparison.optimized.unfilled_staff_slots}</b> optimized open slots</span>
      <span><b>{plannedHours ? (100 * comparison.optimized.overtime_hours / plannedHours).toFixed(1) : '0.0'}%</b> overtime share</span>
    </div>
  </>
}
