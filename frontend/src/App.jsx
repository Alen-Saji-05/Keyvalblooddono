import { Route, Routes } from 'react-router-dom'

import { AppShell } from './components/layout/AppShell'
import { RequireAnonymous, RequireAuth, RoleHomeRedirect } from './auth/guards'
import { LoginPage } from './features/auth/LoginPage'
import { RegisterPage } from './features/auth/RegisterPage'
import { DashboardPage } from './features/dashboard/DashboardPage'
import { DonorDetailPage } from './features/donors/DonorDetailPage'
import { DonorsPage } from './features/donors/DonorsPage'
import { InboxPage } from './features/donor/InboxPage'
import { MyDonationsPage } from './features/donor/MyDonationsPage'
import { MyProfilePage } from './features/donor/MyProfilePage'
import { NotFoundPage } from './features/misc/NotFoundPage'
import { AvailabilityPage } from './features/patient/AvailabilityPage'
import { NewRequestPage } from './features/patient/NewRequestPage'
import { RequestDetailPage } from './features/requests/RequestDetailPage'
import { RequestsPage } from './features/requests/RequestsPage'
import { UsersPage } from './features/users/UsersPage'

/**
 * Route table, grouped by who may reach each branch, so the permission for a screen is
 * visible in the structure rather than buried in the component.
 *
 * These guards are convenience only. The server authorises every request independently,
 * and removing a guard here would expose a screen, not data.
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
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/requests" element={<RequestsPage />} />
          <Route path="/requests/:id" element={<RequestDetailPage />} />
          <Route path="/donors" element={<DonorsPage />} />
          <Route path="/donors/:id" element={<DonorDetailPage />} />
          <Route path="/users" element={<UsersPage />} />
        </Route>
      </Route>

      {/* --- Patient --- */}
      <Route element={<RequireAuth roles={['patient']} />}>
        <Route element={<AppShell />}>
          {/* The same list and detail components as the administrator sees. The server
              scopes the rows, so a patient's query returns only their own requests and
              the screen needs no separate implementation. */}
          <Route path="/my-requests" element={<RequestsPage />} />
          <Route path="/my-requests/:id" element={<RequestDetailPage />} />
          <Route path="/request/new" element={<NewRequestPage />} />
          <Route path="/availability" element={<AvailabilityPage />} />
        </Route>
      </Route>

      {/* --- Donor --- */}
      <Route element={<RequireAuth roles={['donor']} />}>
        <Route element={<AppShell />}>
          <Route path="/inbox" element={<InboxPage />} />
          <Route path="/my-profile" element={<MyProfilePage />} />
          <Route path="/my-donations" element={<MyDonationsPage />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
