// Central client for all requests to the FastAPI backend.
// In dev, Vite proxies "/api" to the backend (see vite.config.js).

const BASE_URL = import.meta.env.VITE_API_URL ?? ''
const TOKEN_KEY = 'gramarogya_token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t)
export const clearToken = () => localStorage.removeItem(TOKEN_KEY)

async function request(path, { method = 'GET', body, auth = true, form = false } = {}) {
  const headers = {}
  const opts = { method, headers }
  if (auth) {
    const t = getToken()
    if (t) headers['Authorization'] = `Bearer ${t}`
  }
  if (form) {
    headers['Content-Type'] = 'application/x-www-form-urlencoded'
    opts.body = body
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  const res = await fetch(`${BASE_URL}${path}`, opts)
  if (res.status === 401) {
    clearToken()
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  login: async (username, password) => {
    const body = new URLSearchParams({ username, password })
    const data = await request('/api/auth/admin/login', { method: 'POST', body, form: true, auth: false })
    setToken(data.access_token)
    return data
  },
  logout: () => clearToken(),
  health: () => request('/api/health', { auth: false }),
  dashboardSummary: () => request('/api/dashboard/summary'),
  dashboardExplain: () => request('/api/dashboard/explain'),
  createPlanningRun: (horizon_days = 7) =>
    request('/api/planning-runs', { method: 'POST', body: { horizon_days } }),
  forecastLatest: () => request('/api/forecast/latest'),
  forecastRun: (horizon_days = 7) =>
    request('/api/forecast/run', { method: 'POST', body: { horizon_days } }),
  forecastSeries: (start, horizon = 14) =>
    request(`/api/forecast/series?start=${start}&horizon=${horizon}`),
  forecastBounds: () => request('/api/forecast/bounds'),
  modelMetrics: () => request('/api/forecast/model-metrics'),
  resourcesPlan: (horizon_days = 7) =>
    request('/api/resources/plan', { method: 'POST', body: { horizon_days } }),
  workforceGenerate: (roster_horizon_days = 7) =>
    request('/api/workforce/generate', { method: 'POST', body: { horizon_days: roster_horizon_days, roster_horizon_days } }),
  emergencyCheck: (horizon_days = 7) =>
    request('/api/emergency/check', { method: 'POST', body: { horizon_days } }),
  facilities: () => request('/api/patient/facilities', { auth: false }),
}

