import styles from './Stat.module.css'

/**
 * A headline figure.
 *
 * `caption` is not decoration. A bare "1" under "Eligible donors" invites the reader to
 * assume the network has one donor, when it may have hundreds who are simply inside their
 * cooldown. The caption is where that gets said.
 */
export function Stat({ label, value, caption, tone = 'neutral' }) {
  return (
    <div className={styles.stat}>
      <p className={styles.label}>{label}</p>
      <p className={[styles.value, styles[tone]].join(' ')}>{value}</p>
      {caption && <p className={styles.caption}>{caption}</p>}
    </div>
  )
}

export function StatGrid({ children, columns = 4 }) {
  return (
    <div className={styles.grid} data-columns={columns}>
      {children}
    </div>
  )
}

/**
 * A labelled progress bar for units received against units required.
 *
 * The numbers are stated in text as well as drawn, because a bar alone cannot say
 * "2 of 4" and a screen reader would announce nothing useful from a coloured rectangle.
 */
export function UnitsProgress({ fulfilled, required, size = 'md' }) {
  const percent = required > 0 ? Math.min(100, Math.round((fulfilled / required) * 100)) : 0
  const complete = fulfilled >= required

  return (
    <div className={styles.progressWrap}>
      <div className={[styles.progressText, styles[`progress-${size}`]].join(' ')}>
        <span className={styles.progressNumbers}>
          <strong>{fulfilled}</strong> of {required} units
        </span>
        {!complete && (
          <span className={styles.progressRemaining}>{required - fulfilled} still needed</span>
        )}
      </div>
      <div
        className={styles.track}
        role="progressbar"
        aria-valuenow={fulfilled}
        aria-valuemin={0}
        aria-valuemax={required}
        aria-label={`${fulfilled} of ${required} units received`}
      >
        <div
          className={[styles.fill, complete ? styles.fillComplete : ''].filter(Boolean).join(' ')}
          style={{ transform: `scaleX(${percent / 100})` }}
        />
      </div>
    </div>
  )
}
