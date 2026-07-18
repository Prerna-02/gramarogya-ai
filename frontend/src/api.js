// Central place for all frontend requests to the FastAPI backend.
//
// In development, Vite proxies "/api" to http://localhost:8000 (see
// vite.config.js), so the default base URL can stay empty. Set VITE_API_URL
// to point at a deployed backend in other environments.

const BASE_URL = import.meta.env.VITE_API_URL ?? ''

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status} ${res.statusText}`)
  }
  return res.json()
}

export const api = {
  health: () => request('/api/health'),
}
