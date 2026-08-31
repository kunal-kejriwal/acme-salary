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

  /**
   * Always signs the person out locally, whatever the server says.
   *
   * The POST can fail for reasons that have nothing to do with intent: an
   * already-expired session answers 403, and so does any CSRF problem. If a
   * rejection here skipped `setUser(null)`, the button would do nothing at
   * all -- no state change, no navigation, no message -- which is a worse
   * outcome than a server session that lingers until it expires on its own.
   */
  const signOut = useCallback(async () => {
    try {
      await auth.logout()
    } catch {
      // Deliberately swallowed; the local session is cleared either way.
    } finally {
      setUser(null)
    }
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
