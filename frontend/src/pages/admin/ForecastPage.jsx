import { useEffect, useState } from 'react'
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

import { api } from '../../api.js'

const HORIZONS = [7, 14, 21, 30]
const ACTUAL = '#ea580c'
const PREDICTED = '#1e40af'

export default function ForecastPage() {
  const [bounds, setBounds] = useState(null)
  const [start, setStart] = useState('')
  const [horizon, setHorizon] = useState(14)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [metrics, setMetrics] = useState(null)
  const [showMetrics, setShowMetrics] = useState(false)

  useEffect(() => {
    api.forecastBounds().then((b) => {
      setBounds(b)
      // default start = day after last data (future forecast)
      const d = new Date(b.last_data_date)
      d.setDate(d.getDate() + 1)
      setStart(d.toISOString().slice(0, 10))
    }).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!start) return
    setLoading(true); setError('')
    api.forecastSeries(start, horizon)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [start, horizon])

  const loadMetrics = () => {
    setShowMetrics((v) => !v)
    if (!metrics) api.modelMetrics().then(setMetrics).catch(() => {})
  }

  const total = (t) => data?.series.filter((r) => r[t] != null).length

  return (
    <div className="dashboard">
      <div className="page-head">
        <div>
          <h1>Demand Forecast</h1>
          <p className="muted">Total patient inflow. Pick a start date — past dates show actual vs
            predicted; future dates show the forecast.</p>
        </div>
        <div className="controls-row">
          <input type="date" value={start} min={bounds?.min_date} max="2026-12-31"
            onChange={(e) => setStart(e.target.value)} />
          <div className="segmented">
            {HORIZONS.map((h) => (
              <button key={h} className={horizon === h ? 'seg active' : 'seg'} onClick={() => setHorizon(h)}>{h}d</button>
            ))}
          </div>
        </div>
      </div>

      {error && <div className="banner error">{error}</div>}
      {loading && <div className="banner">Loading forecast…</div>}

      {data && !loading && (
        <>
          <section className="panel">
            <div className="panel-head">
              <h2>Total patient inflow</h2>
              <span className={`pill ${data.is_future ? 'tone-warn' : 'tone-good'}`}>
                {data.is_future ? 'Future forecast' : 'Backtest (actual vs predicted)'}
              </span>
            </div>
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={data.series} margin={{ top: 8, right: 16, bottom: 4, left: -8 }}>
                <CartesianGrid stroke="#eef1f5" vertical={false} />
                <XAxis dataKey="date" tickFormatter={(d) => d.slice(5)} minTickGap={20}
                  tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={{ stroke: '#e2e8f0' }} />
                <YAxis tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={false} width={44} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {total('actual') > 0 && (
                  <Line type="monotone" dataKey="actual" name="Actual" stroke={ACTUAL}
                    strokeWidth={2} dot={false} connectNulls />
                )}
                <Line type="monotone" dataKey="predicted" name="Predicted" stroke={PREDICTED}
                  strokeWidth={2} dot={false} connectNulls />
              </LineChart>
            </ResponsiveContainer>
            <p className="muted small">{data.is_future
              ? 'These dates are beyond the historical data, so only the forecast is shown.'
              : `The model was evaluated on these dates — actual counts are shown alongside its prediction.`}</p>
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>Model performance</h2>
              <button className="toggle-link" onClick={loadMetrics}>
                {showMetrics ? 'Hide ▲' : 'Show comparison ▼'}
              </button>
            </div>
            {showMetrics && (
              metrics ? (
                <>
                  <p className="muted small">Test-set metrics per target. Selected model:
                    <strong> {metrics.selected_family}</strong> (best generalisation).</p>
                  <div className="table-scroll">
                    <table className="data-table">
                      <thead><tr><th>Target</th><th>Model</th><th>R²</th><th>MAE</th><th>RMSE</th><th>WAPE</th></tr></thead>
                      <tbody>
                        {metrics.test_metrics.map((m, i) => (
                          <tr key={i} className={m.model === metrics.selected_family ? 'row-sel' : ''}>
                            <td>{m.target.replace(/_/g, ' ').replace(' arrivals', '')}</td>
                            <td>{m.model}</td>
                            <td>{m.R2.toFixed(3)}</td>
                            <td>{m.MAE.toFixed(2)}</td>
                            <td>{m.RMSE.toFixed(2)}</td>
                            <td>{(m.WAPE * 100).toFixed(1)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : <p className="muted">Loading metrics…</p>
            )}
          </section>
        </>
      )}
    </div>
  )
}
