const LABELS = {
  general_doctors: 'General doctors', physicians: 'Physicians',
  emergency_doctors: 'Emergency doctors', obgyn_doctors: 'OB/GYN doctors',
  pediatricians: 'Pediatricians', senior_nursing_officers: 'Senior nursing officers',
  nursing_officers: 'Nursing officers', anm_staff: 'ANM staff',
  lab_technicians: 'Lab technicians', pharmacists: 'Pharmacists',
  general_beds: 'General beds',
  emergency_beds: 'Emergency beds', isolation_beds: 'Isolation beds',
  diagnostic_test_kits: 'Diagnostic kits', iv_fluids: 'IV fluids',
  oxygen_cylinders: 'Oxygen cylinders', ambulances: 'Ambulances',
}

const tone = (pct) => pct > 100 ? 'critical' : pct >= 85 ? 'watch' : 'ready'

export default function ResourcePressureHeatmap({ data }) {
  if (!data?.length) return <p className="muted">No resource-pressure data available.</p>
  const dates = [...new Set(data.map((row) => row.date))]
  const resources = [...new Set(data.map((row) => row.resource))]
  const byKey = new Map(data.map((row) => [`${row.resource}|${row.date}`, row]))
  return (
    <div className="pressure-wrap">
      <div className="pressure-grid" style={{ gridTemplateColumns: `minmax(190px, 1.2fr) repeat(${dates.length}, minmax(70px, 1fr))` }}>
        <div className="pressure-corner">Capacity used</div>
        {dates.map((date) => <div key={date} className="pressure-date">{date.slice(5)}</div>)}
        {resources.map((resource) => (
          <div className="pressure-row" key={resource}>
            <div className="pressure-label">{LABELS[resource] ?? resource.replaceAll('_', ' ')}</div>
            {dates.map((date) => {
              const row = byKey.get(`${resource}|${date}`)
              return <div key={date} className={`pressure-cell ${tone(row.pressure_pct)}`}
                title={`${LABELS[resource] ?? resource.replaceAll('_', ' ')} · ${date}: ${row.required} required / ${row.available} available${row.shortage ? ` · shortage ${row.shortage}` : ''}`}>
                {Math.round(row.pressure_pct)}%
              </div>
            })}
          </div>
        ))}
      </div>
      <div className="pressure-legend">
        <span><i className="ready" />Below 85%</span><span><i className="watch" />85–100%</span>
        <span><i className="critical" />Over capacity</span>
      </div>
    </div>
  )
}
