import {
  Area, CartesianGrid, ComposedChart, Label, LabelList, Legend, Line, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

const ACTUAL = '#ea580c'
const PREDICTED = '#1e40af'
const BAND = '#a78bfa'

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const row = payload[0].payload
  return (
    <div className="chart-tip">
      <div className="tip-date">{label}</div>
      {row.actual != null && <div><b>{row.actual}</b> actual</div>}
      {row.predicted != null && <div><b>{row.predicted}</b> predicted</div>}
      {row.band && <div className="tip-range">forecast range {row.band[0]}–{row.band[1]}</div>}
    </div>
  )
}

// Patient-inflow chart: recent actuals + forecast line, an ~80% forecast range
// (shaded), a labelled average reference line, and counts on the forecast points.
export default function InflowChart({ data, avg, height = 300, showLabels = true }) {
  const forecastStart = data.find((d) => d.band != null)?.date
  // Label only the forecast points, not every historical point.
  const rows = data.map((d) => ({ ...d, flabel: d.band ? d.predicted : null,
    peakValue: d.is_peak && d.band ? d.predicted : null }))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={rows} margin={{ top: 18, right: 20, bottom: 4, left: -8 }}>
        <CartesianGrid stroke="#eef1f5" vertical={false} />
        <XAxis dataKey="date" tickFormatter={(d) => d.slice(5)} minTickGap={22}
          tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={{ stroke: '#e2e8f0' }} />
        <YAxis tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={false} width={44} domain={['dataMin - 15', 'dataMax + 15']} />
        <Tooltip content={<CustomTooltip />} />
        <Legend verticalAlign="bottom" height={34} iconType="line" />
        <Area dataKey="band" stroke={BAND} strokeWidth={1} fill={BAND} fillOpacity={0.22}
          name="~80% forecast range" isAnimationActive={false} connectNulls={false} />
        {avg != null && (
          <ReferenceLine y={avg} stroke="#94a3b8" strokeDasharray="5 4">
            <Label value={`avg ${avg}/day`} position="insideTopRight" fontSize={11} fill="#64748b" />
          </ReferenceLine>
        )}
        {forecastStart && <ReferenceLine x={forecastStart} stroke="#cbd5e1" strokeDasharray="3 3" />}
        <Line dataKey="actual" name="Observed patients" stroke={ACTUAL} strokeWidth={2.5} dot={false} connectNulls isAnimationActive={false} />
        <Line dataKey="predicted" name="Forecast patients" stroke={PREDICTED} strokeWidth={2.5} strokeDasharray="7 5"
          dot={{ r: 2.5 }} connectNulls isAnimationActive={false}>
          {showLabels && <LabelList dataKey="flabel" position="top" fontSize={10} fill="#1e40af"
            formatter={(v) => (v == null ? '' : Math.round(v))} />}
        </Line>
        <Line dataKey="peakValue" name="Peak day" legendType="none" stroke="none" connectNulls={false}
          dot={{ r: 5, fill: '#d97706', stroke: '#ffffff', strokeWidth: 2 }} isAnimationActive={false} />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
