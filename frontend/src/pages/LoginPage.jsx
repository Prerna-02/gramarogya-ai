import { Link } from 'react-router-dom'

// Placeholder. Real authentication (admin login + patient guest/OTP access)
// is implemented in Phase 9 with the backend auth endpoints.
export default function LoginPage() {
  return (
    <div className="centered">
      <h1>Login</h1>
      <p>Authentication is implemented in Phase 9.</p>
      <Link to="/" className="back-link">
        ← Back to home
      </Link>
    </div>
  )
}
