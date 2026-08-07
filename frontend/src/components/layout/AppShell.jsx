import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

import { Logo } from '../brand/Logo'
import { Button } from '../ui/Button'
import { useAuth } from '../../auth/AuthProvider'
import styles from './AppShell.module.css'

/**
 * Navigation, per role.
 *
 * Each role gets only its own destinations. Showing a patient a greyed-out "Donors" entry
 * would advertise a capability they will never have and invite them to wonder what they
 * are missing.
 */
const NAV = {
  admin: [
    { to: '/dashboard', label: 'Dashboard', icon: 'chart' },
    { to: '/requests', label: 'Blood requests', icon: 'clipboard' },
    { to: '/donors', label: 'Donor registry', icon: 'people' },
    { to: '/users', label: 'Accounts', icon: 'key' },
  ],
  patient: [
    { to: '/my-requests', label: 'My requests', icon: 'clipboard' },
    { to: '/request/new', label: 'New request', icon: 'plus' },
    { to: '/availability', label: 'Donor availability', icon: 'chart' },
  ],
  donor: [
    { to: '/inbox', label: 'Appeals', icon: 'inbox' },
    { to: '/my-profile', label: 'My donor record', icon: 'people' },
    { to: '/my-donations', label: 'Donation history', icon: 'clipboard' },
  ],
}

const ROLE_LABEL = {
  admin: 'Administrator',
  patient: 'Patient',
  donor: 'Donor',
}

function Icon({ name }) {
  const common = {
    width: 18,
    height: 18,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.7,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': true,
  }

  switch (name) {
    case 'chart':
      return (
        <svg {...common}>
          <path d="M4 19V5M4 19h16M8 16v-5M12.5 16V8M17 16v-3" />
        </svg>
      )
    case 'clipboard':
      return (
        <svg {...common}>
          <path d="M9 4h6v3H9zM7 5.5H5.8A1.8 1.8 0 0 0 4 7.3v11.9A1.8 1.8 0 0 0 5.8 21h12.4a1.8 1.8 0 0 0 1.8-1.8V7.3a1.8 1.8 0 0 0-1.8-1.8H17M8.5 12h7M8.5 16h4" />
        </svg>
      )
    case 'people':
      return (
        <svg {...common}>
          <circle cx="9" cy="8" r="3.2" />
          <path d="M3.5 19.5a5.5 5.5 0 0 1 11 0M16 11.2a3 3 0 0 0 0-6M17.5 19.5a5.4 5.4 0 0 0-3-4.8" />
        </svg>
      )
    case 'key':
      return (
        <svg {...common}>
          <circle cx="8" cy="12" r="3.5" />
          <path d="M11.5 12H21M18 12v3M15 12v2.2" />
        </svg>
      )
    case 'inbox':
      return (
        <svg {...common}>
          <path d="M4 13.5 6.2 5.6A1.8 1.8 0 0 1 7.9 4.3h8.2a1.8 1.8 0 0 1 1.7 1.3L20 13.5M4 13.5V18a1.8 1.8 0 0 0 1.8 1.8h12.4A1.8 1.8 0 0 0 20 18v-4.5M4 13.5h4l1.2 2.2h5.6L16 13.5h4" />
        </svg>
      )
    case 'plus':
      return (
        <svg {...common}>
          <path d="M12 5v14M5 12h14" />
        </svg>
      )
    default:
      return null
  }
}

export function AppShell() {
  const { user, role, signOut } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()

  // Close the mobile drawer on navigation. Leaving it open means a tap on a link appears
  // to do nothing, because the drawer is still covering the page it just opened.
  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  const items = NAV[role] ?? []

  return (
    <div className={styles.shell}>
      <a className="skip-link" href="#main">
        Skip to main content
      </a>

      <header className={styles.topbar}>
        <button
          type="button"
          className={styles.menuButton}
          onClick={() => setMenuOpen((open) => !open)}
          aria-expanded={menuOpen}
          aria-controls="primary-navigation"
        >
          <span className="sr-only">{menuOpen ? 'Close navigation' : 'Open navigation'}</span>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
            {menuOpen ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
          </svg>
        </button>

        <div className={styles.topbarBrand}>
          <Logo />
        </div>

        <div className={styles.topbarRight}>
          <div className={styles.identity}>
            <span className={styles.identityName}>{user?.full_name}</span>
            <span className={styles.identityRole}>{ROLE_LABEL[role] ?? role}</span>
          </div>
          <Button size="sm" variant="ghost" onClick={signOut}>
            Sign out
          </Button>
        </div>
      </header>

      <div className={styles.body}>
        <nav
          id="primary-navigation"
          className={[styles.sidebar, menuOpen ? styles.sidebarOpen : ''].filter(Boolean).join(' ')}
          aria-label="Primary"
        >
          <ul className={styles.navList}>
            {items.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  className={({ isActive }) =>
                    [styles.navLink, isActive ? styles.navLinkActive : ''].filter(Boolean).join(' ')
                  }
                  // aria-current is what tells a screen reader which page it is on. The
                  // colour change alone conveys nothing.
                  end={item.to === '/request/new'}
                >
                  <span className={styles.navIcon}>
                    <Icon name={item.icon} />
                  </span>
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>

          <div className={styles.sidebarFooter}>
            <p className={styles.footerNote}>
              Eligibility, fulfilment, and every permission are decided by the server.
            </p>
          </div>
        </nav>

        {/* Dismisses the drawer by tapping away from it. Hidden from assistive technology
            because the close button in the header already does this accessibly. */}
        {menuOpen && (
          <div className={styles.backdrop} onClick={() => setMenuOpen(false)} aria-hidden="true" />
        )}

        <main id="main" className={styles.main}>
          <div className={styles.mainInner}>
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}

/** Page heading, used at the top of every route. */
export function PageHeader({ title, description, actions, meta }) {
  return (
    <div className={styles.pageHeader}>
      <div className={styles.pageHeaderText}>
        <h1 className={styles.pageTitle}>{title}</h1>
        {description && <p className={styles.pageDescription}>{description}</p>}
        {meta && <div className={styles.pageMeta}>{meta}</div>}
      </div>
      {actions && <div className={styles.pageActions}>{actions}</div>}
    </div>
  )
}
