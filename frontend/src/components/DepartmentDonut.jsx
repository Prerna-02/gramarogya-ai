import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'

// Fixed categorical colours (never cycled). `data` = [{name, value}].
const COLORS = ['#2563eb', '#dc2626', '#ea580c', '#16a34a', '#7c3aed', '#0891b2']

export default function DepartmentDonut({ data, height = 240 }) {
  const total = data.reduce((s, d) => s + d.value, 0)
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85}
          paddingAngle={2} stroke="#fff" strokeWidth={2}
          label={({ value }) => (total ? `${Math.round((100 * value) / total)}%` : '')}
          labelLine={false} fontSize={11}>
          {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
        </Pie>
        <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
      </PieChart>
    </ResponsiveContainer>
  )
}
