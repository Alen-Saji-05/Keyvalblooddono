import styles from './Toolbar.module.css'

/** A row of filters above a table. */
export function Toolbar({ children, onReset, hasFilters }) {
  return (
    <div className={styles.toolbar}>
      <div className={styles.controls}>{children}</div>
      {hasFilters && (
        <button type="button" className={styles.reset} onClick={onReset}>
          Clear filters
        </button>
      )}
    </div>
  )
}

/**
 * One labelled filter control.
 *
 * The label is always rendered and visible, never replaced by placeholder text. A
 * placeholder disappears the moment a value is entered, leaving a row of inputs whose
 * meaning has to be inferred from their contents.
 */
export function ToolbarField({ label, children, htmlFor, grow = false }) {
  return (
    <div className={[styles.field, grow ? styles.grow : ''].filter(Boolean).join(' ')}>
      <label className={styles.label} htmlFor={htmlFor}>
        {label}
      </label>
      {children}
    </div>
  )
}
