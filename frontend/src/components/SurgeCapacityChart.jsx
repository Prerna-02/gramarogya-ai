const label = (value) => value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())

export default function SurgeCapacityChart({ resources }) {
  if (!resources?.length) return <p className="muted">No scenario impact available.</p>
  const normalized = resources.map((resource) => ({ ...resource,
    baselinePct: resource.available ? 100 * resource.baseline / resource.available : 200,
    surgePct: resource.available ? 100 * resource.surged / resource.available : 200 }))
  const scale = Math.max(125, Math.ceil(Math.max(...normalized.map((row) => row.surgePct)) / 25) * 25)
  return <div className="surge-capacity-chart">
    <div className="surge-axis"><span>0%</span><span style={{ left: `${10000 / scale}%` }}>100% capacity</span><span>{scale}%</span></div>
    {normalized.map((resource) => <div className="surge-capacity-row" key={resource.resource}
      title={`${label(resource.resource)}: ${resource.available} available · ${resource.baseline} baseline required · ${resource.surged} scenario required · ${resource.shortage} shortage`}>
      <div className="surge-resource-label">{label(resource.resource)}</div>
      <div className="surge-track"><div className="surge-baseline" style={{ width: `${Math.min(100, 100 * resource.baselinePct / scale)}%` }} />
        <div className={`surge-scenario ${resource.shortage ? 'short' : ''}`} style={{ width: `${Math.min(100, 100 * resource.surgePct / scale)}%` }} />
        <div className="surge-capacity-marker" style={{ left: `${10000 / scale}%` }} /></div>
      <div className="surge-value"><strong>{Math.round(resource.surgePct)}%</strong>{resource.shortage > 0 ? <span>gap {resource.shortage}</span> : <span>ready</span>}</div>
    </div>)}
    <div className="surge-chart-legend"><span><i className="baseline" />Baseline required</span><span><i className="scenario" />Scenario required</span><span><i className="capacity" />Available capacity</span></div>
  </div>
}
