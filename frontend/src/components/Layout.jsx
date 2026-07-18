import { Link, Outlet } from 'react-router-dom'

// Shared role-based layout. `role` selects which navigation/header to show,
// so the admin portal and the patient interface reuse one shell instead of
// living in two separate codebases. Navigation is intentionally minimal for
// Phase 2 and is fleshed out in Phases 10-11.
export default function Layout({ role }) {
  const isAdmin = role === 'admin'

  return (
    <div className="layout">
      <header className={`layout-header ${isAdmin ? 'admin' : 'patient'}`}>
        <Link to="/" className="brand">
          GramArogya <span>AI</span>
        </Link>
        <span className="role-badge">
          {isAdmin ? 'Hospital Admin Portal' : 'Patient Interface'}
        </span>
      </header>

      <main className="layout-main">
        <Outlet />
      </main>
    </div>
  )
}
