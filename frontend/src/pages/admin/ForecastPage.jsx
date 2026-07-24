import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { api } from '../../api.js'
import DepartmentDonut from '../../components/DepartmentDonut.jsx'
import InflowChart from '../../components/InflowChart.jsx'
import MetricCard from '../../components/MetricCard.jsx'
import ServiceDemandHeatmap from '../../components/ServiceDemandHeatmap.jsx'

const HORIZONS = [7, 14, 21, 30]
const CATEGORIES = [
  { key: 'general_opd_arrivals', name: 'General OPD', color: '#2859a5' },
  { key: 'fever_infectious_arrivals', name: 'Fever / infectious', color: '#df6a24' },
  { key: 'maternal_child_arrivals', name: 'Maternal & child', color: '#15906c' },
  { key: 'trauma_emergency_arrivals', name: 'Trauma / emergency', color: '#8b5bc2' },
]
const MODEL_ORDER = ['Naive', 'SeasonalNaive', 'RandomForest', 'XGBoost']
const MODEL_COLORS = { Naive: '#94a3b8', SeasonalNaive: '#7aa7d9', RandomForest: '#0f9a8a', XGBoost: '#2859a5' }

export default function ForecastPage() {
  const [bounds, setBounds] = useState(null)
  const [start, setStart] = useState('')
  const [horizon, setHorizon] = useState(14)
  const [data, setData] = useState(null)
  const [patterns, setPatterns] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [modelInfo, setModelInfo] = useState(null)
  const [explanation, setExplanation] = useState(null)
  const [showMetrics, setShowMetrics] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.forecastBounds().then((result) => {
      setBounds(result)
      const saved = JSON.parse(localStorage.getItem('gramarogya_forecast_selection') || 'null')
      const next = new Date(result.last_data_date); next.setDate(next.getDate() + 1)
      setStart(saved?.start || next.toISOString().slice(0, 10))
      if (HORIZONS.includes(saved?.horizon)) setHorizon(saved.horizon)
    }).catch((err) => setError(err.message))
    api.forecastPatterns().then(setPatterns).catch(() => {})
    api.modelMetrics().then(setMetrics).catch(() => {})
    api.modelInfo().then(setModelInfo).catch(() => {})
  }, [])

  useEffect(() => {
    if (!start) return
    setLoading(true); setError('')
    localStorage.setItem('gramarogya_forecast_selection', JSON.stringify({ start, horizon }))
    Promise.all([api.forecastSeries(start, horizon, 7), api.forecastExplain(start, horizon)])
      .then(([series, explain]) => { setData(series); setExplanation(explain) })
      .catch((err) => setError(err.message)).finally(() => setLoading(false))
  }, [start, horizon])

  const windowRows = data?.series.filter((row) => row.kind === 'window' && row.cat) ?? []
  const categoryRows = windowRows.map((row) => ({ date: row.date.slice(5), ...row.cat }))
  const composition = CATEGORIES.map((category) => ({
    name: category.name,
    value: windowRows.reduce((sum, row) => sum + row.cat[category.key], 0),
  }))
  const modelBars = metrics ? metrics.test_metrics
    .filter((item) => item.target === 'total_patient_arrivals')
    .map((item) => ({ model: item.model, R2: +item.R2.toFixed(3) }))
    .sort((a, b) => MODEL_ORDER.indexOf(a.model) - MODEL_ORDER.indexOf(b.model)) : []
  const peakDays = data?.peak_days ?? []

  return (
    <div className="dashboard">
      <div className="page-head">
        <div><div className="page-eyebrow">Predictive planning</div><h1>Demand Forecast</h1>
          <p className="muted">Patient demand outlook with service-level pressure and validated operational guidance.</p></div>
        <div className="controls-row">
          <input type="date" value={start} min={bounds?.min_date} max="2026-12-31" onChange={(event) => setStart(event.target.value)} />
          <div className="segmented">{HORIZONS.map((days) => <button key={days} className={horizon === days ? 'seg active' : 'seg'} onClick={() => setHorizon(days)}>{days}d</button>)}</div>
        </div>
      </div>
      {error && <div className="banner error">{error}</div>}
      {loading && <div className="banner">Loading selected forecast…</div>}

      {data && !loading && <>
        <div className="metric-row forecast-metrics">
          <MetricCard label="Average per day" value={data.avg ?? '—'} sub="selected window" />
          <MetricCard label="Peak demand days" value={peakDays.length || '—'}
            sub={peakDays.length ? `${data.peak?.value} max · ${peakDays.map((item) => item.date.slice(5)).join(', ')}` : 'no local peak'} tone="warn" />
          <MetricCard label="Total patients" value={data.total ?? '—'} sub={`${horizon}-day forecast`} />
        </div>

        <section className="panel panel-featured"><h2>Total patient inflow</h2>
          <p className="muted small">Patient demand outlook for the selected window.</p>
          <InflowChart data={data.series} avg={data.avg} height={330} showLabels={windowRows.length <= 10} />
        </section>

        <section className="panel panel-featured"><h2>Service demand pressure</h2>
          <p className="muted small">Daily demand pressure across hospital services.</p>
          <ServiceDemandHeatmap rows={categoryRows} categories={CATEGORIES} />
        </section>

        <section className="panel forecast-recommendation">
          <div>
            <div className="panel-head"><div><h2>Insights</h2><p className="muted small">Generated from the exact selected dates and validated against structured forecast evidence.</p></div>
              {explanation?.validated && <span className="pill tone-good">Grounded</span>}</div>
            {explanation ? <p className="ai-summary">{explanation.summary}</p> : <p className="muted">Preparing explanation…</p>}
            {explanation?.context && <div className="evidence-row">
              <span><b>{explanation.context.total_patients}</b> total patients</span>
              <span><b>{explanation.context.peak_total}</b> peak on {explanation.context.peak_date}</span>
              <span><b>{explanation.context.overall_risk}</b> capacity risk</span>
              <span><b>{explanation.evidence.resource_plans_checked}</b> daily plans checked</span>
            </div>}
          </div>
        </section>

        <div className="grid-2">
          <section className="panel"><h2>Case mix over the window</h2>
            <p className="muted small">Expected service distribution across the selected {horizon}-day window.</p>
            <DepartmentDonut data={composition} height={260} />
          </section>
          <section className="panel"><div className="panel-head"><h2>Model performance</h2>
            <button className="toggle-link" onClick={() => setShowMetrics((value) => !value)}>{showMetrics ? 'Hide ▲' : 'Show ▼'}</button></div>
            {showMetrics ? metrics ? <><p className="muted small">Total-patient R² on unseen 2025 data. Selected: <strong>{metrics.selected_family}</strong>.</p>
              <ResponsiveContainer width="100%" height={220}><BarChart data={modelBars} margin={{ top: 8, right: 12, bottom: 4, left: -12 }}>
                <CartesianGrid stroke="#edf1f5" vertical={false} /><XAxis dataKey="model" tick={{ fontSize: 12, fill: '#64748b' }} tickLine={false} />
                <YAxis domain={[0, 1]} tick={{ fontSize: 12, fill: '#64748b' }} tickLine={false} axisLine={false} width={36} />
                <Tooltip /><Bar dataKey="R2" name="R²" radius={[5, 5, 0, 0]} isAnimationActive={false}>{modelBars.map((model) => <Cell key={model.model} fill={MODEL_COLORS[model.model]} />)}</Bar>
              </BarChart></ResponsiveContainer>
              <p className="model-r2-summary"><strong>{metrics.selected_family} R²: {modelBars.find((model) => model.model === metrics.selected_family)?.R2}</strong> on unseen 2025 test data.</p></> : <p className="muted">Loading model evidence…</p> : <p className="muted">Performance comparison hidden.</p>}
          </section>
        </div>

        {modelInfo?.dataset && <section className="panel dataset-evidence-panel">
          <div className="panel-heading-copy"><h2>Forecast dataset and columns</h2>
            <p>Traceability evidence showing the historical dataset, model inputs and predicted outputs.</p></div>
          <div className="dataset-facts">
            <span><b>{modelInfo.dataset.name}</b> dataset file</span>
            <span><b>{modelInfo.dataset.records}</b> daily records</span>
            <span><b>{modelInfo.dataset.date_start}</b> first date</span>
            <span><b>{modelInfo.dataset.date_end}</b> last date</span>
          </div>
          <ColumnGroup title={`Dataset columns used for forecasting (${modelInfo.dataset.source_feature_columns.length})`}
            description="Calendar, event, weather, outbreak and prior-demand columns read from the historical dataset. Resource requirement and shortage columns are not model inputs."
            columns={modelInfo.dataset.source_feature_columns} tone="feature" />
          <ColumnGroup title={`Forecast outputs (${modelInfo.dataset.target_columns.length})`}
            description="These are the patient-demand values predicted by the model."
            columns={modelInfo.dataset.target_columns} tone="target" />
          <details className="dataset-all-columns"><summary>View model features after preprocessing ({modelInfo.dataset.feature_columns.length})</summary>
            <p>Readable categories are converted to numbers for modelling: {modelInfo.dataset.engineered_feature_columns.map((item) => `${item.derived_from} → ${item.column}`).join('; ')}.</p>
            <div className="column-chip-list all">{modelInfo.dataset.feature_columns.map((column) => <code key={column}>{column}</code>)}</div>
          </details>
          <details className="dataset-all-columns"><summary>View all source dataset columns ({modelInfo.dataset.columns.length})</summary>
            <div className="column-chip-list all">{modelInfo.dataset.columns.map((column) => <code key={column}>{column}</code>)}</div>
          </details>
        </section>}

        {patterns && <div className="grid-2">
          <PatternChart title="Weekly pattern" description="Average arrivals by day of week." data={patterns.weekly} x="day" color="#2859a5" />
          <PatternChart title="Seasonal pattern" description="Average arrivals by month." data={patterns.monthly} x="month" color="#0f9a8a" />
        </div>}
      </>}
    </div>
  )
}

function ColumnGroup({ title, description, columns, tone }) {
  return <div className="dataset-column-group"><h3>{title}</h3><p>{description}</p>
    <div className={`column-chip-list ${tone}`}>{columns.map((column) => <code key={column}>{column}</code>)}</div>
  </div>
}

function PatternChart({ title, description, data, x, color }) {
  return <section className="panel"><h2>{title}</h2><p className="muted small">{description}</p>
    <ResponsiveContainer width="100%" height={220}><BarChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -12 }}>
      <CartesianGrid stroke="#edf1f5" vertical={false} /><XAxis dataKey={x} tick={{ fontSize: 12, fill: '#64748b' }} tickLine={false} />
      <YAxis tick={{ fontSize: 12, fill: '#64748b' }} tickLine={false} axisLine={false} width={36} /><Tooltip />
      <Bar dataKey="avg" name="average per day" fill={color} radius={[5, 5, 0, 0]} isAnimationActive={false} />
    </BarChart></ResponsiveContainer>
  </section>
}
