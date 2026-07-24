import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export default function WorkforceLoadCharts({ groups }) {
  const [selected, setSelected] = useState(groups?.[0]?.group || '')
  useEffect(() => { setSelected(groups?.[0]?.group || '') }, [groups])
  if (!groups?.length) return null
  const group = groups.find((item) => item.group === selected) || groups[0]
  const hours = group.members.map((member) => ({ ...member, regular_hours: member.hours - member.overtime_hours }))
  const tick = { fontSize: 13, fill: '#64748b' }
  return <section className="panel panel-featured workforce-load-panel">
    <div className="panel-head"><div className="panel-heading-copy"><h2>Shift burden and planned hours</h2><p>Operational workload for comparable staff, including nights, weekends, on-call duty and overtime.</p></div>
      <select value={group.group} onChange={(event) => setSelected(event.target.value)}>{groups.map((item) => <option value={item.group} key={item.group}>{item.group.replaceAll('_', ' ')}</option>)}</select>
    </div>
    <div className="grid-2 workforce-load-grid">
      <div><h3>Unsocial-shift assignments</h3><ResponsiveContainer width="100%" height={285}><BarChart data={group.members} margin={{ top: 8, right: 12, bottom: 35, left: 0 }}>
        <CartesianGrid stroke="#eef1f5" vertical={false} /><XAxis dataKey="staff_name" tick={tick} interval={0} angle={-18} textAnchor="end" height={62} /><YAxis tick={tick} allowDecimals={false} width={32} />
        <Tooltip /><Legend /><Bar dataKey="nights" name="Nights" fill="#2859a5" radius={[4, 4, 0, 0]} /><Bar dataKey="weekends" name="Weekends" fill="#d97706" radius={[4, 4, 0, 0]} /><Bar dataKey="oncall" name="On-call" fill="#7c3aed" radius={[4, 4, 0, 0]} />
      </BarChart></ResponsiveContainer></div>
      <div><h3>Planned hours and overtime</h3><ResponsiveContainer width="100%" height={285}><BarChart data={hours} margin={{ top: 8, right: 12, bottom: 35, left: 0 }}>
        <CartesianGrid stroke="#eef1f5" vertical={false} /><XAxis dataKey="staff_name" tick={tick} interval={0} angle={-18} textAnchor="end" height={62} /><YAxis tick={tick} width={38} />
        <Tooltip /><Legend /><ReferenceLine y={hours[0]?.target_hours || 40} stroke="#d97706" strokeDasharray="5 4" />
        <Bar dataKey="regular_hours" name="Regular hours" stackId="hours" fill="#4f86c6" /><Bar dataKey="overtime_hours" name="Overtime" stackId="hours" fill="#c92c37" radius={[4, 4, 0, 0]} />
      </BarChart></ResponsiveContainer></div>
    </div>
  </section>
}
