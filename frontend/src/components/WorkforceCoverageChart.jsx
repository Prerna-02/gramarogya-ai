import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

const shortName = (value) => value
  .replace('Obstetrician and Gynecologist', 'OB/GYN')
  .replace('Emergency Medical Officer', 'Emergency Doctor')
  .replace('General Medical Officer', 'General Doctor')
  .replace('Senior Nursing Officer', 'Senior Nurse')

export default function WorkforceCoverageChart({ data }) {
  if (!data?.length) return <p className="muted">No coverage data available.</p>
  const labelKey = Object.hasOwn(data[0], 'role') ? 'role' : 'department'
  return (
    <ResponsiveContainer width="100%" height={Math.max(330, data.length * 42)}>
      <BarChart data={data} layout="vertical" margin={{ top: 8, right: 24, bottom: 8, left: 48 }}>
        <CartesianGrid stroke="#edf1f5" horizontal={false} />
        <XAxis type="number" allowDecimals={false} tick={{ fontSize: 14, fill: '#64748b' }} />
        <YAxis type="category" dataKey={labelKey} width={155} tickFormatter={shortName}
          tick={{ fontSize: 14, fill: '#475569' }} axisLine={false} tickLine={false} />
        <Tooltip formatter={(value, name) => [value, name === 'required' ? 'Required' : 'Assigned']} />
        <Legend formatter={(value) => value === 'required' ? 'Required positions' : 'Assigned staff'} />
        <Bar dataKey="required" fill="#cbd5e1" radius={[0, 5, 5, 0]} barSize={10} />
        <Bar dataKey="assigned" fill="#0f766e" radius={[0, 5, 5, 0]} barSize={10} />
      </BarChart>
    </ResponsiveContainer>
  )
}
