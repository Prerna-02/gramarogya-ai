const tone = (pct) => pct >= 112 ? 'high' : pct >= 100 ? 'above' : pct >= 88 ? 'normal' : 'low'

export default function ServiceDemandHeatmap({ rows, categories }) {
  if (!rows?.length) return <p className="muted">No service forecast available.</p>
  const averages = Object.fromEntries(categories.map((category) => [category.key,
    rows.reduce((sum, row) => sum + row[category.key], 0) / rows.length]))
  return (
    <div className="service-pressure-wrap">
      <div className="service-pressure-grid" style={{ gridTemplateColumns: `minmax(150px, 1.25fr) repeat(${rows.length}, minmax(52px, 1fr))` }}>
        <div className="service-pressure-corner">Patients · vs service average</div>
        {rows.map((row) => <div className="service-pressure-date" key={row.date}>{row.date}</div>)}
        {categories.map((category) => (
          <div className="service-pressure-row" key={category.key}>
            <div className="service-pressure-label"><i style={{ background: category.color }} />{category.name}</div>
            {rows.map((row) => {
              const pct = Math.round(100 * row[category.key] / averages[category.key])
              return <div className={`service-pressure-cell ${tone(pct)}`} key={row.date}
                title={`${category.name} · ${row.date}: ${row[category.key]} patients · ${pct}% of this service's window average`}>
                <strong>{row[category.key]}</strong><span>{pct}%</span>
              </div>
            })}
          </div>
        ))}
      </div>
      <div className="pressure-legend">
        <span><i className="sp-low" />Below usual</span><span><i className="sp-normal" />Near average</span>
        <span><i className="sp-high" />Above average</span>
      </div>
    </div>
  )
}
