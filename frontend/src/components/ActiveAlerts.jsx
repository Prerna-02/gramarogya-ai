import { useEffect, useRef, useState } from 'react'

// A pool of realistic synthetic alerts. One is pushed every ~3 minutes to
// simulate a live operational feed.
const POOL = [
  { severity: 'high', title: 'High dengue cases predicted', detail: 'Fever/infectious surge expected in the next 2 days.' },
  { severity: 'warn', title: 'Medicine stock low', detail: 'IV fluids and test kits below reorder point.' },
  { severity: 'warn', title: 'Bed shortage risk', detail: 'General beds projected near capacity (24–48h).' },
  { severity: 'high', title: 'OBGYN on-call gap', detail: 'Only one OBGYN available for maternity coverage.' },
  { severity: 'warn', title: 'Oxygen demand rising', detail: 'Respiratory cases increasing; check cylinder stock.' },
  { severity: 'warn', title: 'Ambulance utilisation high', detail: 'Consider activating a standby crew.' },
]
const INTERVAL_MS = 3 * 60 * 1000

const now = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

export default function ActiveAlerts({ seed = [] }) {
  const [alerts, setAlerts] = useState(() =>
    seed.map((a, i) => ({ id: `seed-${i}`, time: now(), ...a })))
  const idx = useRef(0)

  useEffect(() => {
    const t = setInterval(() => {
      const a = POOL[idx.current % POOL.length]
      idx.current += 1
      setAlerts((prev) => [{ id: `syn-${Date.now()}`, time: now(), ...a }, ...prev].slice(0, 8))
    }, INTERVAL_MS)
    return () => clearInterval(t)
  }, [])

  if (alerts.length === 0) return <p className="muted">No active alerts.</p>
  return (
    <ul className="alert-list">
      {alerts.map((a) => (
        <li key={a.id} className={`alert-item ${a.severity}`}>
          <span className="alert-dot" />
          <div>
            <div className="alert-title">{a.title}</div>
            <div className="alert-detail">{a.detail}</div>
          </div>
          <span className="alert-time">{a.time}</span>
        </li>
      ))}
    </ul>
  )
}
