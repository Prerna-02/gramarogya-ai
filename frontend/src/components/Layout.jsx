import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth.jsx'

const ADMIN_NAV = [
  { to: '/admin', label: 'Dashboard', icon: '▦', end: true },
  { to: '/admin/forecast', label: 'Forecasting', icon: '📈' },
  { to: '/admin/resources', label: 'Resource Planning', icon: '🩺' },
  { to: '/admin/workforce', label: 'Workforce', icon: '👥' },
  { to: '/admin/emergency', label: 'Emergency & Alerts', icon: '🚑' },
  { to: '/admin/fairness', label: 'Fairness & Audit', icon: '⚖️' },
]

// Shared role-based shell. Admin gets the command-centre sidebar; patient gets a
// simple public header.
export default function Layout({ role }) {
  const isAdmin = role === 'admin'
  const { logout } = useAuth()
  const navigate = useNavigate()

  if (!isAdmin) {
    return (
      <div className="layout">
        <header className="layout-header patient">
          <Link to="/" className="brand">
            GramArogya <span>AI</span>
          </Link>
          <span className="role-badge">Patient Interface</span>
        </header>
        <main className="layout-main">
          <Outlet />
        </main>
      </div>
    )
  }

  return (
    <div className="admin-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="logo-dot">✚</span>
          <div>
            GramArogya <span>AI</span>
            <div className="sidebar-sub">Command Center</div>
          </div>
        </div>
        <nav className="sidebar-nav">
          {ADMIN_NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <span className="nav-icon">{n.icon}</span>
              {n.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="admin-main">
        <header className="topbar">
          <div className="topbar-title">Hospital Administration</div>
          <div className="topbar-right">
            <span className="hospital-name">Gadchiroli Rural Hospital</span>
            <button
              className="logout-btn"
              onClick={() => {
                logout()
                navigate('/login')
              }}
            >
              Log out
            </button>
          </div>
        </header>
        <main className="admin-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
