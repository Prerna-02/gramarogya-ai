import { useEffect, useState } from 'react'
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

import { api } from '../../api.js'

const HORIZONS = [7, 14, 21, 30]

// Fixed categorical order + hues (never cycled). Total is the dark anchor line.
const SERIES = [
  { key: 'total_patient_arrivals', name: 'Total', color: '#0f172a', width: 2.5 },
  { key: 'general_opd_arrivals', name: 'General OPD', color: '#2563eb', width: 1.6 },
  { key: 'fever_infectious_arrivals', name: 'Fever/infectious', color: '#ea580c', width: 1.6 },
  { key: 'maternal_child_arrivals', name: 'Maternal-child', color: '#059669', width: 1.6 },
  { key: 'trauma_emergency_arrivals', name: 'Trauma/emergency', color: '#7c3aed', width: 1.6 },
]

export default function ForecastPage() {
  const [horizon, setHorizon] = useState(14)
  const [forecast, setForecast] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    setError('')
    api.forecastRun(horizon)
      .then((d) => setForecast(d.forecast))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [horizon])

  return (
    <div className="dashboard">
      <div className="page-head">
        <div>
          <h1>Demand Forecast</h1>
          <p className="muted">Predicted patient arrivals by service category. Choose a horizon.</p>
        </div>
        <div className="segmented">
          {HORIZONS.map((h) => (
            <button key={h} className={horizon === h ? 'seg active' : 'seg'} onClick={() => setHorizon(h)}>
              {h} days
            </button>
          ))}
        </div>
      </div>

      {error && <div className="banner error">Could not load forecast: {error}</div>}
      {loading && <div className="banner">Forecasting {horizon} days…</div>}

      {forecast && !loading && (
        <>
          <section className="panel">
            <h2>{horizon}-day forecast</h2>
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={forecast} margin={{ top: 8, right: 16, bottom: 4, left: -8 }}>
                <CartesianGrid stroke="#eef1f5" vertical={false} />
                <XAxis dataKey="date" tickFormatter={(d) => d.slice(5)} minTickGap={20}
                  tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={{ stroke: '#e2e8f0' }} />
                <YAxis tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={false} width={44} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {SERIES.map((s) => (
                  <Line key={s.key} type="monotone" dataKey={s.key} name={s.name}
                    stroke={s.color} strokeWidth={s.width} dot={false} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </section>

          <section className="panel">
            <h2>Forecast table</h2>
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Date</th><th>Total</th><th>General OPD</th><th>Fever</th>
                    <th>Maternal-child</th><th>Trauma</th><th>Admissions</th>
                  </tr>
                </thead>
                <tbody>
                  {forecast.map((f) => (
                    <tr key={f.date}>
                      <td>{f.date}</td>
                      <td><strong>{f.total_patient_arrivals}</strong></td>
                      <td>{f.general_opd_arrivals}</td>
                      <td>{f.fever_infectious_arrivals}</td>
                      <td>{f.maternal_child_arrivals}</td>
                      <td>{f.trauma_emergency_arrivals}</td>
                      <td>{f.expected_admissions}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  )
}
