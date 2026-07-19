import { useEffect, useState } from 'react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'

import { api } from '../../api.js'
import DepartmentDonut from '../../components/DepartmentDonut.jsx'
import InflowChart from '../../components/InflowChart.jsx'
import MetricCard from '../../components/MetricCard.jsx'

const HORIZONS = [7, 14, 21, 30]
const CATS = [
  { key: 'general_opd_arrivals', name: 'General OPD', color: '#2563eb' },
  { key: 'fever_infectious_arrivals', name: 'Fever/infectious', color: '#ea580c' },
  { key: 'maternal_child_arrivals', name: 'Maternal-child', color: '#16a34a' },
  { key: 'trauma_emergency_arrivals', name: 'Trauma/emergency', color: '#7c3aed' },
]
const MODEL_ORDER = ['Naive', 'SeasonalNaive', 'RandomForest', 'XGBoost']

export default function ForecastPage() {
  const [bounds, setBounds] = useState(null)
  const [start, setStart] = useState('')
  const [horizon, setHorizon] = useState(14)
  const [data, setData] = useState(null)
  const [patterns, setPatterns] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [showMetrics, setShowMetrics] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.forecastBounds().then((b) => {
      setBounds(b)
      const d = new Date(b.last_data_date); d.setDate(d.getDate() + 1)
      setStart(d.toISOString().slice(0, 10))
    }).catch((e) => setError(e.message))
    api.forecastPatterns().then(setPatterns).catch(() => {})
  }, [])

  useEffect(() => {
    if (!start) return
    setLoading(true); setError('')
    api.forecastSeries(start, horizon, 7)
      .then(setData).catch((e) => setError(e.message)).finally(() => setLoading(false))
  }, [start, horizon])

  const loadMetrics = () => {
    setShowMetrics((v) => !v)
    if (!metrics) api.modelMetrics().then(setMetrics).catch(() => {})
  }

  const win = data?.series.filter((r) => r.kind === 'window' && r.cat) ?? []
  const catSeries = (data?.series ?? []).filter((r) => r.cat).map((r) => ({ date: r.date.slice(5), ...r.cat }))
  const compo = CATS.map((c) => ({ name: c.name, value: win.reduce((s, r) => s + r.cat[c.key], 0) }))
  const modelBars = metrics
    ? metrics.test_metrics.filter((m) => m.target === 'total_patient_arrivals')
        .map((m) => ({ model: m.model, R2: +m.R2.toFixed(3), WAPE: +(m.WAPE * 100).toFixed(1) }))
        .sort((a, b) => MODEL_ORDER.indexOf(a.model) - MODEL_ORDER.indexOf(b.model))
    : []

  return (
    <div className="dashboard">
      <div className="page-head">
        <div>
          <h1>Demand Forecast</h1>
          <p className="muted">Total patient inflow with an ~80% expected range. Past dates show actual vs predicted.</p>
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
          <div className="metric-row">
            <MetricCard label="Average / day" value={data.avg ?? '—'} sub="over the window" />
            <MetricCard label="Peak day" value={data.peak?.value ?? '—'} sub={data.peak?.date ?? ''} tone="warn" />
            <MetricCard label="Total patients" value={data.total ?? '—'} sub={`${horizon} days`} />
            <MetricCard label="View" value={data.is_future ? 'Forecast' : 'Backtest'}
              tone={data.is_future ? 'warn' : 'good'} sub={data.is_future ? 'future dates' : 'actual vs predicted'} />
          </div>

          <section className="panel">
            <h2>Total patient inflow</h2>
            <InflowChart data={data.series} avg={data.avg} height={330} showLabels={win.length <= 10} />
          </section>

          <section className="panel">
            <h2>By service category</h2>
            <p className="muted small">Category mix (stacks to the total). Estimated from the model's learned seasonal/outbreak patterns.</p>
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={catSeries} margin={{ top: 8, right: 16, bottom: 4, left: -8 }}>
                <CartesianGrid stroke="#eef1f5" vertical={false} />
                <XAxis dataKey="date" minTickGap={22} tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={{ stroke: '#e2e8f0' }} />
                <YAxis tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={false} width={44} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {CATS.map((c) => (
                  <Area key={c.key} type="monotone" dataKey={c.key} name={c.name} stackId="1"
                    stroke={c.color} fill={c.color} fillOpacity={0.75} isAnimationActive={false} />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </section>

          <div className="grid-2">
            <section className="panel">
              <h2>Case-mix over the window</h2>
              <DepartmentDonut data={compo} height={260} />
            </section>
            <section className="panel">
              <div className="panel-head">
                <h2>Model performance</h2>
                <button className="toggle-link" onClick={loadMetrics}>{showMetrics ? 'Hide ▲' : 'Show ▼'}</button>
              </div>
              {showMetrics ? (metrics ? (
                <>
                  <p className="muted small">Total-patient R² on unseen 2025 data. Selected:
                    <strong> {metrics.selected_family}</strong>.</p>
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={modelBars} margin={{ top: 8, right: 12, bottom: 4, left: -12 }}>
                      <CartesianGrid stroke="#eef1f5" vertical={false} />
                      <XAxis dataKey="model" tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={{ stroke: '#e2e8f0' }} />
                      <YAxis domain={[0, 1]} tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={false} width={36} />
                      <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }} />
                      <Bar dataKey="R2" name="R²" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                        {modelBars.map((m) => (
                          <Cell key={m.model} fill={m.model === metrics.selected_family ? '#1e3a8a' : '#94a3b8'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                  <p className="muted small">Higher R² = better. XGBoost also has the lowest WAPE
                    ({modelBars.find((m) => m.model === 'XGBoost')?.WAPE}%).</p>
                </>
              ) : <p className="muted">Loading…</p>) : (
                <p className="muted">Compare Naive / Seasonal / Random Forest / XGBoost on total patients.</p>
              )}
            </section>
          </div>

          {patterns && (
            <div className="grid-2">
              <section className="panel">
                <h2>Weekly pattern</h2>
                <p className="muted small">Average arrivals by day of week (market days & weekends).</p>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={patterns.weekly} margin={{ top: 8, right: 12, bottom: 4, left: -12 }}>
                    <CartesianGrid stroke="#eef1f5" vertical={false} />
                    <XAxis dataKey="day" tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={{ stroke: '#e2e8f0' }} />
                    <YAxis tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={false} width={36} />
                    <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }} />
                    <Bar dataKey="avg" name="avg/day" fill="#2563eb" radius={[4, 4, 0, 0]} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </section>
              <section className="panel">
                <h2>Seasonal pattern</h2>
                <p className="muted small">Average arrivals by month (the monsoon surge).</p>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={patterns.monthly} margin={{ top: 8, right: 12, bottom: 4, left: -12 }}>
                    <CartesianGrid stroke="#eef1f5" vertical={false} />
                    <XAxis dataKey="month" tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} axisLine={{ stroke: '#e2e8f0' }} />
                    <YAxis tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={false} width={36} />
                    <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }} />
                    <Bar dataKey="avg" name="avg/day" fill="#0891b2" radius={[4, 4, 0, 0]} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </section>
            </div>
          )}
        </>
      )}
    </div>
  )
}
