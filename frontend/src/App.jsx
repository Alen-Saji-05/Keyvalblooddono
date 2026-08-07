import { Route, Routes } from 'react-router-dom'

import { AppShell } from './components/layout/AppShell'
import { RequireAnonymous, RequireAuth, RoleHomeRedirect } from './auth/guards'
import { LoginPage } from './features/auth/LoginPage'
import { RegisterPage } from './features/auth/RegisterPage'
import { NotFoundPage } from './features/misc/NotFoundPage'
import { PlaceholderPage } from './features/misc/PlaceholderPage'

/**
 * Route table.
 *
 * Grouped by who may reach each branch, so the permission for a screen is visible in the
 * structure rather than buried inside the component. These guards are convenience only -
 * the server authorises every request independently, and removing one here would expose
 * a screen, not data.
 *
 * The screens themselves land in the phases that follow; the placeholders below keep every
 * navigation destination reachable so the shell and the guards can be exercised now.
 */
export function App() {
  return (
    <Routes>
      <Route element={<RequireAnonymous />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      <Route path="/" element={<RoleHomeRedirect />} />

      {/* --- Administrator --- */}
      <Route element={<RequireAuth roles={['admin']} />}>
        <Route element={<AppShell />}>
          <Route path="/dashboard" element={<PlaceholderPage title="Network dashboard" phase="Phase 7" />} />
          <Route path="/requests" element={<PlaceholderPage title="Blood requests" phase="Phase 5" />} />
          <Route path="/requests/:id" element={<PlaceholderPage title="Request detail" phase="Phase 5" />} />
          <Route path="/donors" element={<PlaceholderPage title="Donor registry" phase="Phase 5" />} />
          <Route path="/donors/:id" element={<PlaceholderPage title="Donor detail" phase="Phase 5" />} />
          <Route path="/users" element={<PlaceholderPage title="Accounts" phase="Phase 5" />} />
        </Route>
      </Route>

      {/* --- Patient --- */}
      <Route element={<RequireAuth roles={['patient']} />}>
        <Route element={<AppShell />}>
          <Route path="/my-requests" element={<PlaceholderPage title="My requests" phase="Phase 6" />} />
          <Route path="/my-requests/:id" element={<PlaceholderPage title="Request progress" phase="Phase 6" />} />
          <Route path="/request/new" element={<PlaceholderPage title="New blood request" phase="Phase 6" />} />
          <Route path="/availability" element={<PlaceholderPage title="Donor availability" phase="Phase 6" />} />
        </Route>
      </Route>

      {/* --- Donor --- */}
      <Route element={<RequireAuth roles={['donor']} />}>
        <Route element={<AppShell />}>
          <Route path="/inbox" element={<PlaceholderPage title="Appeals for blood" phase="Phase 6" />} />
          <Route path="/my-profile" element={<PlaceholderPage title="My donor record" phase="Phase 6" />} />
          <Route path="/my-donations" element={<PlaceholderPage title="Donation history" phase="Phase 6" />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
