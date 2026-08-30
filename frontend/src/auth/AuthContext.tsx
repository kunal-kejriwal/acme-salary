import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'

import { auth } from '../api/endpoints'
import type { User } from '../api/types'

interface AuthState {
  user: User | null
  /** True until the first `/auth/me` settles, so routes do not flash. */
  loading: boolean
  signIn: (username: string, password: string) => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthState | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Doubles as the CSRF bootstrap -- /auth/me sets the cookie the login
    // POST needs.
    auth
      .me()
      .then(setUser)
      .finally(() => setLoading(false))
  }, [])

  const signIn = useCallback(async (username: string, password: string) => {
    setUser(await auth.login(username, password))
  }, [])

  const signOut = useCallback(async () => {
    await auth.logout()
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside an AuthProvider')
  return context
}
