import { createContext, useContext, useState, useCallback } from 'react'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => sessionStorage.getItem('admin_token'))
  const [role, setRole] = useState(() => sessionStorage.getItem('admin_role') || 'admin')

  const login = useCallback((newToken, newRole = 'admin') => {
    sessionStorage.setItem('admin_token', newToken)
    sessionStorage.setItem('admin_role', newRole)
    setToken(newToken)
    setRole(newRole)
  }, [])

  const logout = useCallback(() => {
    sessionStorage.removeItem('admin_token')
    sessionStorage.removeItem('admin_role')
    setToken(null)
    setRole(null)
  }, [])

  return (
    <AuthContext.Provider value={{ token, role, isAuthenticated: !!token, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
