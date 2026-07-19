import { Routes, Route, Navigate } from 'react-router-dom'

import Layout from './components/Layout.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import LoginPage from './pages/LoginPage.jsx'
import DashboardPage from './pages/admin/DashboardPage.jsx'
import ComingSoonPage from './pages/admin/ComingSoonPage.jsx'
import PatientHomePage from './pages/patient/PatientHomePage.jsx'

// One React app, role-based layouts:
//   /admin/*   -> Hospital administration portal (auth required)
//   /patient/* -> Patient / public interface (guest)
// Phase 10 delivers the admin foundation + Overview dashboard; the remaining
// admin pages are stubbed with ComingSoonPage and filled in next.
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/admin" replace />} />
      <Route path="/login" element={<LoginPage />} />

      <Route
        path="/admin"
        element={
          <ProtectedRoute>
            <Layout role="admin" />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="forecast" element={<ComingSoonPage title="Demand Forecast" />} />
        <Route path="resources" element={<ComingSoonPage title="Resource Planning" />} />
        <Route path="workforce" element={<ComingSoonPage title="Workforce Roster" />} />
        <Route path="emergency" element={<ComingSoonPage title="Emergency Network" />} />
        <Route path="fairness" element={<ComingSoonPage title="Fairness & Audit" />} />
      </Route>

      <Route path="/patient" element={<Layout role="patient" />}>
        <Route index element={<PatientHomePage />} />
      </Route>
    </Routes>
  )
}
