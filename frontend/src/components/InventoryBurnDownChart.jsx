import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export default function InventoryBurnDownChart({ plans, item }) {
  const data = (plans || []).map((plan) => ({
    date: plan.date.slice(5),
    closing: plan.inventory_closing?.[item] ?? 0,
    reorderPoint: plan.medicines[item]?.reorder_point ?? 0,
    dailyUse: plan.medicines[item]?.required ?? 0,
  }))
  const opening = plans?.[0]?.inventory_opening?.[item] ?? 0
  const closing = data.at(-1)?.closing ?? 0
  const totalUse = data.reduce((sum, row) => sum + row.dailyUse, 0)
  const firstReorder = data.find((row) => row.closing <= row.reorderPoint)?.date
  return <><ResponsiveContainer width="100%" height={265}>
    <LineChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
      <CartesianGrid stroke="#edf1f5" vertical={false} />
      <XAxis dataKey="date" tick={{ fontSize: 14, fill: '#64748b' }} />
      <YAxis allowDecimals={false} tick={{ fontSize: 14, fill: '#64748b' }} />
      <Tooltip formatter={(value, name) => [value, name === 'closing' ? 'Stock remaining' : 'Reorder threshold']} />
      <Legend formatter={(value) => value === 'closing' ? 'Projected stock remaining' : 'Reorder threshold'} />
      <Line type="monotone" dataKey="closing" stroke="#0f766e" strokeWidth={3} dot={{ r: 3 }} />
      <Line type="monotone" dataKey="reorderPoint" stroke="#d97706" strokeWidth={2} strokeDasharray="5 4" dot={false} />
    </LineChart>
  </ResponsiveContainer><div className="inventory-summary">
    <span><b>{opening}</b>starting stock</span><span><b>{totalUse}</b>planned use</span>
    <span><b>{closing}</b>stock remaining</span><span><b>{firstReorder || 'None'}</b>first reorder signal</span>
  </div></>
}
