import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

// Predicted vs actual total arrivals. Two series -> legend always present;
// a CVD-safe blue/orange pair carries identity (never colour-alone: labelled + legend).
const ACTUAL = '#ea580c' // orange
const PREDICTED = '#1e40af' // blue

const fmtDate = (d) => d.slice(5) // MM-DD

export default function ForecastChart({ data }) {
  if (!data || data.length === 0) {
    return <div className="chart-empty">No forecast data available.</div>
  }
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: -8 }}>
        <CartesianGrid stroke="#eef1f5" vertical={false} />
        <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fontSize: 11, fill: '#64748b' }}
          tickLine={false} axisLine={{ stroke: '#e2e8f0' }} minTickGap={24} />
        <YAxis tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={false} width={44} />
        <Tooltip labelFormatter={(d) => `Date ${d}`}
          contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Line type="monotone" dataKey="actual" name="Actual" stroke={ACTUAL}
          strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="predicted" name="Predicted" stroke={PREDICTED}
          strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}
