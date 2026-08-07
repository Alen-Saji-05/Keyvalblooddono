import { forwardRef } from 'react'
import { Link } from 'react-router-dom'

import { Spinner } from './Spinner'
import styles from './Button.module.css'

/**
 * The application's button.
 *
 * `loading` disables the button and swaps the label for a spinner in place, which stops
 * the double submit that otherwise files two blood requests, and keeps the button the
 * same width so nothing beside it moves.
 */
export const Button = forwardRef(function Button(
  {
    variant = 'secondary',
    size = 'md',
    loading = false,
    disabled = false,
    fullWidth = false,
    className = '',
    children,
    type = 'button',
    ...rest
  },
  ref,
) {
  const classes = [
    styles.button,
    styles[variant],
    styles[size],
    styles.relative,
    fullWidth ? styles.fullWidth : '',
    className,
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <button
      ref={ref}
      type={type}
      className={classes}
      disabled={disabled || loading}
      // Announced to assistive technology, which would otherwise be told only that the
      // button became disabled and not why.
      aria-busy={loading || undefined}
      {...rest}
    >
      <span className={loading ? styles.loadingLabel : undefined}>{children}</span>
      {loading && (
        <span className={styles.spinnerWrap}>
          <Spinner size={size === 'sm' ? 14 : 16} />
        </span>
      )}
    </button>
  )
})

/**
 * A navigation link that looks like a button.
 *
 * A real anchor, not a button with an onClick that calls navigate. Middle-clicking,
 * opening in a new tab, and copying the address all have to work, and none of them do on
 * a button. Wrapping a Link inside a Button would nest an anchor in a button, which is
 * invalid markup and confuses assistive technology about what the control actually is.
 */
export function LinkButton({
  to,
  variant = 'secondary',
  size = 'md',
  fullWidth = false,
  className = '',
  children,
  ...rest
}) {
  const classes = [
    styles.button,
    styles[variant],
    styles[size],
    styles.link,
    fullWidth ? styles.fullWidth : '',
    className,
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <Link to={to} className={classes} {...rest}>
      {children}
    </Link>
  )
}
