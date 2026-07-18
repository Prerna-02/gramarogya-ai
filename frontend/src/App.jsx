import { Routes, Route } from 'react-router-dom'

import Layout from './components/Layout.jsx'
import LandingPage from './pages/LandingPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import DashboardPage from './pages/admin/DashboardPage.jsx'
import PatientHomePage from './pages/patient/PatientHomePage.jsx'

// One React application serves both audiences through role-based layouts:
//   /admin/*   -> Hospital administration portal
//   /patient/* -> Patient / public interface
// The full set of pages is built in Phases 10-11; Phase 2 wires the skeleton.
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />

      <Route path="/admin" element={<Layout role="admin" />}>
        <Route index element={<DashboardPage />} />
      </Route>

      <Route path="/patient" element={<Layout role="patient" />}>
        <Route index element={<PatientHomePage />} />
      </Route>
    </Routes>
  )
}
