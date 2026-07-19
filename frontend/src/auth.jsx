import { createContext, useContext, useState } from 'react'

import { api, getToken } from './api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setTok] = useState(getToken())
  const [role, setRole] = useState(null)

  const login = async (username, password) => {
    const data = await api.login(username, password)
    setTok(getToken())
    setRole(data.role)
    return data
  }
  const logout = () => {
    api.logout()
    setTok(null)
    setRole(null)
  }

  return (
    <AuthContext.Provider value={{ token, role, isAuthed: !!token, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
