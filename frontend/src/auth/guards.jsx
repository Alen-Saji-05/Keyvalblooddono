import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { FullPageSpinner } from '../components/ui/Spinner'
import { useAuth } from './AuthProvider'

/**
 * The landing route for each role.
 *
 * An administrator opens onto the network dashboard, a patient onto their requests, a
 * donor onto their inbox. Sending everyone to one page and having two thirds of them
 * immediately navigate elsewhere is a worse first second.
 */
export const HOME_FOR_ROLE = {
  admin: '/dashboard',
  patient: '/my-requests',
  donor: '/inbox',
}

/**
 * Require a signed-in account, optionally of specific roles.
 *
 * These guards are a usability measure, not a security one. The server authorises every
 * request independently; hiding a route here only stops someone being shown a screen that
 * would fail. Anyone editing this file should not assume it protects data.
 */
export function RequireAuth({ roles }) {
  const { isAuthenticated, isRestoring, role } = useAuth()
  const location = useLocation()

  if (isRestoring) {
    return <FullPageSpinner label="Restoring your session" />
  }

  if (!isAuthenticated) {
    // The attempted location is carried through so that signing in returns the user
    // where they were going, rather than dumping them on a default page.
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  if (roles && !roles.includes(role)) {
    return <Navigate to={HOME_FOR_ROLE[role] ?? '/'} replace />
  }

  return <Outlet />
}

/** Keep a signed-in user away from the login and registration screens. */
export function RequireAnonymous() {
  const { isAuthenticated, isRestoring, role } = useAuth()

  if (isRestoring) {
    return <FullPageSpinner label="Restoring your session" />
  }

  if (isAuthenticated) {
    return <Navigate to={HOME_FOR_ROLE[role] ?? '/'} replace />
  }

  return <Outlet />
}

/** Send the root path to wherever this particular account starts. */
export function RoleHomeRedirect() {
  const { isAuthenticated, isRestoring, role } = useAuth()

  if (isRestoring) {
    return <FullPageSpinner label="Loading" />
  }

  return <Navigate to={isAuthenticated ? (HOME_FOR_ROLE[role] ?? '/login') : '/login'} replace />
}
