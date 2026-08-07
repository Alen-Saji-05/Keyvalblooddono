import styles from './Badge.module.css'

/**
 * A small status chip.
 *
 * Every tone pairs a background, a border, and a foreground that meet contrast together,
 * so a badge cannot be assembled into an unreadable combination.
 */
export function Badge({ tone = 'neutral', children, className = '' }) {
  return (
    <span className={[styles.badge, styles[tone], className].filter(Boolean).join(' ')}>
      {children}
    </span>
  )
}

/**
 * A blood group, rendered as data rather than as a warning.
 *
 * Deliberately neutral. Colouring blood groups red would spend the loudest colour in the
 * palette on the single most repeated element in the interface, and leave nothing louder
 * for a request that is actually overdue. The sign is set in a monospaced face so that
 * plus and minus are unmistakable at a glance, which matters more here than almost
 * anywhere else in the application.
 */
export function BloodGroupBadge({ group, size = 'md' }) {
  return (
    <span className={[styles.bloodGroup, styles[`bg-${size}`]].join(' ')}>
      <span className="sr-only">Blood group </span>
      {group}
    </span>
  )
}

/** Maps a request status onto a tone and readable words. */
export function RequestStatusBadge({ status, isExpired }) {
  const config = {
    open: { tone: 'neutral', label: 'Open' },
    partially_fulfilled: { tone: 'caution', label: 'Partially fulfilled' },
    fulfilled: { tone: 'positive', label: 'Fulfilled' },
  }[status] ?? { tone: 'neutral', label: status }

  // An overdue request that is still short of blood is the one thing in this interface
  // that genuinely warrants the alarm colour.
  if (isExpired && status !== 'fulfilled') {
    return <Badge tone="critical">Overdue</Badge>
  }

  return <Badge tone={config.tone}>{config.label}</Badge>
}

const DONOR_STATUS = {
  available: { tone: 'positive', label: 'Available' },
  unavailable_moved: { tone: 'neutral', label: 'Moved away' },
  unavailable_traveling: { tone: 'neutral', label: 'Travelling' },
  unavailable_medical: { tone: 'caution', label: 'Medically unable' },
}

export function DonorStatusBadge({ status }) {
  const config = DONOR_STATUS[status] ?? { tone: 'neutral', label: status }
  return <Badge tone={config.tone}>{config.label}</Badge>
}

/**
 * Whether a donor can give right now.
 *
 * Separate from the availability badge because they are different facts and are
 * routinely confused: a donor can be marked available and still be ineligible because
 * they gave blood three weeks ago. Showing both side by side is what makes the
 * distinction visible.
 */
export function EligibilityBadge({ eligible }) {
  return eligible ? (
    <Badge tone="positive">Eligible now</Badge>
  ) : (
    <Badge tone="neutral">Not eligible</Badge>
  )
}
