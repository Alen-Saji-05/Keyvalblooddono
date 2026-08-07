import { useId } from 'react'

import styles from './Field.module.css'

/**
 * A labelled form control with hint and error text.
 *
 * The wiring is the point. The label is bound to the control by id, the hint and the
 * error are referenced through aria-describedby, and an errored control gets
 * aria-invalid. Done by hand at each call site, one of those is always missed, and the
 * result is a form that a screen reader user cannot correct because they are never told
 * what was wrong.
 */
export function Field({ label, hint, error, required, children, htmlFor }) {
  const generatedId = useId()
  const id = htmlFor || generatedId
  const hintId = hint ? `${id}-hint` : undefined
  const errorId = error ? `${id}-error` : undefined

  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined

  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={id}>
        {label}
        {required && (
          <span className={styles.required} aria-hidden="true">
            *
          </span>
        )}
        {/* The asterisk alone means nothing without sight of it. */}
        {required && <span className="sr-only"> (required)</span>}
      </label>

      {children({ id, describedBy, invalid: Boolean(error) })}

      {hint && !error && (
        <p className={styles.hint} id={hintId}>
          {hint}
        </p>
      )}

      {error && (
        <p className={styles.error} id={errorId}>
          {error}
        </p>
      )}
    </div>
  )
}

/** Text, email, password, number, date, and so on. */
export function TextInput({ invalid, className = '', ...rest }) {
  return (
    <input
      className={[styles.input, invalid ? styles.inputInvalid : '', className]
        .filter(Boolean)
        .join(' ')}
      aria-invalid={invalid || undefined}
      {...rest}
    />
  )
}

export function Select({ invalid, children, className = '', ...rest }) {
  return (
    <div className={styles.selectWrap}>
      <select
        className={[styles.input, styles.select, invalid ? styles.inputInvalid : '', className]
          .filter(Boolean)
          .join(' ')}
        aria-invalid={invalid || undefined}
        {...rest}
      >
        {children}
      </select>
      <svg
        className={styles.selectChevron}
        viewBox="0 0 16 16"
        width="14"
        height="14"
        aria-hidden="true"
      >
        <path
          d="M4 6.5 8 10.5 12 6.5"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  )
}

export function Textarea({ invalid, className = '', rows = 3, ...rest }) {
  return (
    <textarea
      rows={rows}
      className={[styles.input, styles.textarea, invalid ? styles.inputInvalid : '', className]
        .filter(Boolean)
        .join(' ')}
      aria-invalid={invalid || undefined}
      {...rest}
    />
  )
}

/** Lays fields out in columns that collapse to one on a narrow screen. */
export function FieldGrid({ columns = 2, children }) {
  return (
    <div className={styles.grid} data-columns={columns}>
      {children}
    </div>
  )
}
