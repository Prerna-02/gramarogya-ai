// Alerts are calculated by backend rules from operational, roster, resource,
// and forecast values. This component only renders that source-of-truth list.
export default function ActiveAlerts({ alerts = [] }) {
  if (alerts.length === 0) return <p className="muted">No active alerts.</p>
  return (
    <ul className="alert-list">
      {alerts.map((alert) => (
        <li key={alert.id} className={`alert-item ${alert.severity}`}>
          <span className="alert-dot" />
          <div>
            <div className="alert-title">{alert.title}</div>
            <div className="alert-detail">{alert.detail}</div>
            {alert.action && <div className="alert-action">{alert.action}</div>}
          </div>
          <span className="alert-status">{alert.status}</span>
        </li>
      ))}
    </ul>
  )
}
