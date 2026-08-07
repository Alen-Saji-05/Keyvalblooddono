import styles from './Logo.module.css'

/**
 * The identity mark.
 *
 * Three nodes joined by two links, with the centre node filled. It says "network", which
 * is what this system is, rather than reaching for the blood droplet that every other
 * site in the category already uses.
 *
 * Deliberately contains no emblem, insignia, flag, or any official symbol of any kind.
 * The eRaktKosh portal was studied only for which screens a blood network needs and how
 * densely it presents them; none of its branding appears here.
 *
 * Drawn in currentColor so it inherits from whatever it sits in, and works unchanged in
 * both themes.
 */
export function LogoMark({ size = 24 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={styles.mark}
    >
      <path
        d="M6.8 8.6 12 5.6l5.2 3M6.8 15.4 12 18.4l5.2-3"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
      <circle cx="12" cy="12" r="3.4" fill="currentColor" />
      <circle cx="4.4" cy="7.2" r="2.2" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="19.6" cy="7.2" r="2.2" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="4.4" cy="16.8" r="2.2" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="19.6" cy="16.8" r="2.2" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  )
}

export function Logo({ size = 24, showText = true }) {
  return (
    <span className={styles.logo}>
      <span className={styles.markWrap}>
        <LogoMark size={size} />
      </span>
      {showText && (
        <span className={styles.text}>
          <span className={styles.name}>Blood Donation</span>
          <span className={styles.suffix}>Network</span>
        </span>
      )}
    </span>
  )
}
