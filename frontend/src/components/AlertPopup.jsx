export default function AlertPopup({ alert, onClose }) {
  if (!alert) return null
  return (
    <aside className={`alert-popup ${alert.severity}`} role="alertdialog" aria-live="assertive" aria-label="New hospital alert">
      <div className="alert-popup-head">
        <div><span className="alert-popup-dot" /><span>New hospital alert</span></div>
        <button type="button" onClick={onClose} aria-label="Dismiss alert">×</button>
      </div>
      <strong>{alert.title}</strong>
      <p>{alert.detail}</p>
      {alert.action && <div className="alert-popup-action">{alert.action}</div>}
    </aside>
  )
}
