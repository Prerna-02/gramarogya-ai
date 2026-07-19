import { Navigate } from 'react-router-dom'

import { useAuth } from '../auth.jsx'

// Guards admin routes: redirects to /login when no valid token is present.
export default function ProtectedRoute({ children }) {
  const { isAuthed } = useAuth()
  return isAuthed ? children : <Navigate to="/login" replace />
}
