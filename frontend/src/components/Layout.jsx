import { useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth.jsx'
import AppIcon from './AppIcon.jsx'

const ADMIN_NAV = [
  { to: '/admin', label: 'Dashboard', icon: 'dashboard', end: true },
  { to: '/admin/forecast', label: 'Demand Forecasting', icon: 'forecast' },
  { to: '/admin/resources', label: 'Resource Planning', icon: 'resources' },
  { to: '/admin/workforce', label: 'Workforce', icon: 'workforce' },
  { to: '/admin/emergency', label: 'Emergency & Alerts', icon: 'emergency' },
  { to: '/admin/fairness', label: 'Fairness & Audit', icon: 'fairness' },
]

export default function Layout({ role }) {
  const isAdmin = role === 'admin'
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)

  if (!isAdmin) {
    return (
      <div className="layout">
        <header className="layout-header patient">
          <Link to="/" className="brand">GramArogya <span>AI</span></Link>
          <span className="role-badge">Patient Interface</span>
        </header>
        <main className="layout-main"><Outlet /></main>
      </div>
    )
  }

  const signOut = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="admin-shell">
      {menuOpen && <button className="sidebar-scrim" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}
      <aside className={`sidebar ${menuOpen ? 'open' : ''}`}>
        <div className="sidebar-brand">
          <span className="logo-mark"><span>+</span></span>
          <div className="brand-copy">
            <strong>GramArogya <em>AI</em></strong>
            <span>Hospital Command Centre</span>
          </div>
        </div>
        <div className="nav-section-label">Operations</div>
        <nav className="sidebar-nav">
          {ADMIN_NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end}
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <AppIcon name={item.icon} size={19} className="nav-icon" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="sidebar-facility">
            <span className="facility-status" />
            <div><strong>Gadchiroli</strong><span>Rural Hospital</span></div>
          </div>
        </div>
      </aside>

      <div className="admin-main">
        <header className="topbar">
          <div className="topbar-left">
            <button className="menu-btn" onClick={() => setMenuOpen(true)} aria-label="Open navigation">
              <AppIcon name="menu" />
            </button>
            <div><div className="topbar-title">Hospital Administration</div><span className="topbar-context">Operations and planning</span></div>
          </div>
          <div className="topbar-right">
            <div className="admin-profile"><span className="profile-icon"><AppIcon name="user" size={17} /></span><div><strong>Administrator</strong><span>Gadchiroli Rural Hospital</span></div></div>
            <button className="logout-btn" onClick={signOut}><AppIcon name="logout" size={17} /><span>Log out</span></button>
          </div>
        </header>
        <main className="admin-content"><Outlet /></main>
      </div>
    </div>
  )
}
