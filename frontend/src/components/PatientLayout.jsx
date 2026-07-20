import { NavLink, Outlet } from 'react-router-dom'

import { LANGS, useI18n } from '../i18n.jsx'

const NAV = [
  { to: '/patient', icon: '🏠', key: 'nav_home', end: true },
  { to: '/patient/search', icon: '🏥', key: 'nav_hospitals' },
  { to: '/patient/emergency', icon: '🚑', key: 'nav_emergency' },
]

export default function PatientLayout() {
  const { lang, setLang, t } = useI18n()
  return (
    <div className="pt-viewport">
      <div className="pt-shell">
        <header className="pt-topbar">
          <div className="pt-brand"><span className="pt-logo">✚</span> GramArogya <b>AI</b></div>
          <div className="pt-lang">
            {LANGS.map((l) => (
              <button key={l.code} className={lang === l.code ? 'pt-lang-btn active' : 'pt-lang-btn'}
                onClick={() => setLang(l.code)}>{l.label}</button>
            ))}
          </div>
        </header>

        <main className="pt-main"><Outlet /></main>

        <nav className="pt-bottomnav">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end}
              className={({ isActive }) => `pt-nav-item ${isActive ? 'active' : ''}`}>
              <span className="pt-nav-icon">{n.icon}</span>
              <span>{t(n.key)}</span>
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  )
}
