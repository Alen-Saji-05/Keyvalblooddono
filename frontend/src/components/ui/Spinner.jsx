import styles from './Spinner.module.css'

/** An indeterminate progress indicator. */
export function Spinner({ size = 16, label }) {
  return (
    <span
      className={styles.spinner}
      style={{ width: size, height: size }}
      // Decorative when it sits inside a control that already describes itself; given a
      // role and a label only when it is the sole indication that something is happening.
      role={label ? 'status' : undefined}
      aria-label={label || undefined}
      aria-hidden={label ? undefined : true}
    />
  )
}

/** Centred spinner for a whole page or a route that has not resolved yet. */
export function FullPageSpinner({ label = 'Loading' }) {
  return (
    <div className={styles.fullPage}>
      <Spinner size={28} label={label} />
      <p className={styles.fullPageLabel}>{label}</p>
    </div>
  )
}
