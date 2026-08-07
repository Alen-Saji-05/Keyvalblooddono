import { Button } from './Button'
import { Spinner } from './Spinner'
import styles from './States.module.css'

/**
 * The three states every data view needs besides its content.
 *
 * Kept together in one file because they are one decision, not three. A screen that
 * renders content but forgets the empty case shows a heading over nothing and looks
 * broken; one that forgets the error case shows the same thing whether the network failed
 * or the filter genuinely matched nobody.
 */

export function LoadingState({ label = 'Loading' }) {
  return (
    <div className={styles.state} role="status">
      <Spinner size={22} />
      <p className={styles.body}>{label}</p>
    </div>
  )
}

/**
 * An empty result.
 *
 * `action` matters: an empty state that only says "no donors" is a dead end, whereas one
 * offering the button that fixes it is the shortest path forward.
 */
export function EmptyState({ title, description, action, icon }) {
  return (
    <div className={styles.state}>
      {icon && <div className={styles.icon}>{icon}</div>}
      <h3 className={styles.title}>{title}</h3>
      {description && <p className={styles.body}>{description}</p>}
      {action && <div className={styles.action}>{action}</div>}
    </div>
  )
}

/**
 * A failed request.
 *
 * Shows the server's own message rather than a generic apology. The backend already
 * returns something specific and readable, and replacing it with "Something went wrong"
 * discards the only information the user could act on.
 */
export function ErrorState({ error, onRetry, title = 'Could not load this' }) {
  const message =
    error?.message || 'The request failed. Check your connection and try again.'

  return (
    <div className={styles.state} role="alert">
      <div className={[styles.icon, styles.iconError].join(' ')} aria-hidden="true">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor">
          <path
            d="M12 8v5M12 16.5v.5"
            strokeWidth="2"
            strokeLinecap="round"
          />
          <circle cx="12" cy="12" r="9" strokeWidth="1.7" />
        </svg>
      </div>
      <h3 className={styles.title}>{title}</h3>
      <p className={styles.body}>{message}</p>
      {onRetry && (
        <div className={styles.action}>
          <Button onClick={onRetry}>Try again</Button>
        </div>
      )}
    </div>
  )
}

/** An inline message above a form, for errors that belong to no single field. */
export function FormAlert({ tone = 'critical', children }) {
  if (!children) return null
  return (
    <div className={[styles.alert, styles[`alert-${tone}`]].join(' ')} role="alert">
      {children}
    </div>
  )
}
