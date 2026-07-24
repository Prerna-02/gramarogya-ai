import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export default function BedCapacityChart({ plans, bedType }) {
  const data = (plans || []).map((plan) => ({ date: plan.date.slice(5), required: plan.beds[bedType].required, available: plan.beds[bedType].available }))
  return <ResponsiveContainer width="100%" height={290}>
    <BarChart data={data} margin={{ top: 10, right: 18, left: 0, bottom: 5 }}>
      <CartesianGrid stroke="#edf1f5" vertical={false} />
      <XAxis dataKey="date" tick={{ fontSize: 14, fill: '#64748b' }} />
      <YAxis allowDecimals={false} tick={{ fontSize: 14, fill: '#64748b' }} />
      <Tooltip />
      <Legend formatter={(value) => value === 'required' ? 'Beds required' : 'Beds available'} />
      <Bar dataKey="available" fill="#cbd5e1" radius={[5, 5, 0, 0]} />
      <Bar dataKey="required" fill="#2f66b2" radius={[5, 5, 0, 0]} />
    </BarChart>
  </ResponsiveContainer>
}
