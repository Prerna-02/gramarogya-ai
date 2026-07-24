const SHIFTS = ['Morning', 'Evening', 'Night', 'On-call']

const tone = (row) => !row || row.shortfall === 0 ? 'ready' : row.coverage_pct >= 80 ? 'watch' : 'critical'

export default function WorkforceGapHeatmap({ data }) {
  if (!data?.length) return <p className="muted">No shift coverage data available.</p>
  const dates = [...new Set(data.map((row) => row.date))]
  const byKey = new Map(data.map((row) => [`${row.date}|${row.shift}`, row]))
  return <div className="workforce-gap-wrap">
    <div className="workforce-gap-grid" style={{ gridTemplateColumns: `minmax(120px, .8fr) repeat(${dates.length}, minmax(76px, 1fr))` }}>
      <div className="workforce-gap-corner">Shift coverage</div>
      {dates.map((date) => <div className="workforce-gap-date" key={date}>{date.slice(5)}</div>)}
      {SHIFTS.map((shift) => <div className="workforce-gap-row" key={shift}>
        <div className="workforce-gap-label">{shift}</div>
        {dates.map((date) => {
          const row = byKey.get(`${date}|${shift}`)
          const gaps = row?.role_gaps?.map((item) => `${item.role}: ${item.shortfall}`).join(', ')
          return <div className={`workforce-gap-cell ${tone(row)}`} key={date}
            title={row ? `${date} ${shift}: ${row.assigned}/${row.required} filled${gaps ? `; gaps: ${gaps}` : ''}` : `${date} ${shift}: no requirement`}>
            <strong>{row ? `${row.assigned}/${row.required}` : '—'}</strong>
            <span>{row?.shortfall ? `${row.shortfall} open` : row ? 'covered' : 'none'}</span>
          </div>
        })}
      </div>)}
    </div>
    <div className="pressure-legend"><span><i className="ready" />Covered</span><span><i className="watch" />Small gap</span><span><i className="critical" />Coverage risk</span></div>
  </div>
}
