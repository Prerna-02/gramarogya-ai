import {
  CartesianGrid, Label, Line, LineChart, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'

export default function WaitTimeChart({ data }) {
  if (!data?.length) return <p className="muted">No wait-time estimate available.</p>
  return (
    <ResponsiveContainer width="100%" height={245}>
      <LineChart data={data} margin={{ top: 12, right: 20, bottom: 4, left: -6 }}>
        <CartesianGrid stroke="#edf1f5" vertical={false} />
        <XAxis dataKey="date" tickFormatter={(d) => d.slice(5)} tick={{ fontSize: 12, fill: '#64748b' }}
          axisLine={{ stroke: '#dbe3ec' }} tickLine={false} />
        <YAxis unit="m" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} />
        <Tooltip formatter={(value) => [`${value} min`, 'Estimated wait']} labelFormatter={(d) => `Date ${d}`} />
        <ReferenceLine y={30} stroke="#d97706" strokeDasharray="5 4">
          <Label value="30 min target" position="insideTopRight" fill="#a16207" fontSize={11} />
        </ReferenceLine>
        <Line type="monotone" dataKey="wait_minutes" stroke="#2563eb" strokeWidth={3}
          dot={{ r: 3, fill: '#fff', strokeWidth: 2 }} activeDot={{ r: 5 }} />
      </LineChart>
    </ResponsiveContainer>
  )
}
