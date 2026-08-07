import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { api, refreshSession } from '../api/client'
import {
  clearAccessToken,
  setAccessToken,
  setUnauthenticatedHandler,
} from '../api/tokenStore'

const AuthContext = createContext(null)

/**
 * Session state for the application.
 *
 * The access token lives in the module-level token store rather than in this component's
 * state, and only the user object is kept in React. Two reasons: the fetch wrapper needs
 * the current token from inside callbacks created before the last refresh, and keeping
 * the token out of the React tree means it cannot end up serialised into a devtools
 * snapshot or an error report.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  // Distinct from "no user". On first load the session is unknown until the silent
  // refresh completes, and rendering the login screen during that moment would flash it
  // at someone who is in fact signed in.
  const [status, setStatus] = useState('restoring')
  const queryClient = useQueryClient()

  const signOutLocally = useCallback(() => {
    clearAccessToken()
    setUser(null)
    setStatus('unauthenticated')
    // Cached data belongs to the account that fetched it. Left in place, the next person
    // to sign in on this browser would see the previous user's donor list for as long as
    // it took the queries to refetch.
    queryClient.clear()
  }, [queryClient])

  useEffect(() => {
    setUnauthenticatedHandler(signOutLocally)
  }, [signOutLocally])

  // Restore the session on load. The access token was lost with the page, but the
  // httpOnly refresh cookie was not.
  useEffect(() => {
    let cancelled = false

    async function restore() {
      // refreshSession, not a direct call, because it is single-flight. Refresh tokens
      // rotate, so two concurrent refreshes mean the first revokes the token the second
      // is carrying and the user is signed out for no reason. Sharing the in-flight
      // promise makes a double invocation - StrictMode in development, or anything else
      // that mounts this twice - collapse into one request.
      const body = await refreshSession()
      if (cancelled) return

      if (body) {
        setUser(body.user)
        setStatus('authenticated')
      } else {
        // No cookie, or an expired or revoked one. Not an error worth surfacing: it is
        // simply what a first visit looks like.
        setStatus('unauthenticated')
      }
    }

    restore()
    return () => {
      cancelled = true
    }
  }, [])

  const signIn = useCallback(async (email, password) => {
    const body = await api.post('/auth/login', { email, password })
    setAccessToken(body.access_token)
    setUser(body.user)
    setStatus('authenticated')
    return body.user
  }, [])

  const register = useCallback(async (payload) => {
    const body = await api.post('/auth/register', payload)
    setAccessToken(body.access_token)
    setUser(body.user)
    setStatus('authenticated')
    return body.user
  }, [])

  const signOut = useCallback(async () => {
    try {
      await api.post('/auth/logout')
    } catch {
      // The local session is cleared regardless. If the server call fails, the refresh
      // token may survive until it expires, but leaving the user apparently signed in on
      // a shared machine is the worse outcome of the two.
    }
    signOutLocally()
  }, [signOutLocally])

  const value = useMemo(
    () => ({
      user,
      status,
      isRestoring: status === 'restoring',
      isAuthenticated: status === 'authenticated',
      role: user?.role ?? null,
      signIn,
      register,
      signOut,
      setUser,
    }),
    [user, status, signIn, register, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used inside an AuthProvider.')
  }
  return context
}
