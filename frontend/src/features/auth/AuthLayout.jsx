import { Logo } from '../../components/brand/Logo'
import styles from './AuthLayout.module.css'

/**
 * The signed-out shell.
 *
 * Two panes on a wide screen: the form on the left, and on the right a short explanation
 * of what the system does. Somebody arriving at a blood network for the first time is
 * usually in a bad situation and needs to know, in one glance, whether they are in the
 * right place. A bare login box on an empty page answers nothing.
 *
 * The right pane is hidden below the breakpoint rather than stacked, because on a phone
 * it would push the actual form below the fold.
 *
 * It is NOT aria-hidden. An earlier version marked it so on the grounds that it was
 * decorative, which was wrong: it is explanatory prose about how the system works, and
 * hiding it from assistive technology would give a screen reader user less information
 * than a sighted one on the same screen. Below the breakpoint it is removed with
 * display:none, which hides it from everybody equally.
 */
export function AuthLayout({ title, description, children, footer }) {
  return (
    <div className={styles.layout}>
      <div className={styles.formPane}>
        <div className={styles.formInner}>
          <div className={styles.brand}>
            <Logo size={28} />
          </div>

          <div className={styles.heading}>
            <h1 className={styles.title}>{title}</h1>
            {description && <p className={styles.description}>{description}</p>}
          </div>

          {children}

          {footer && <div className={styles.footer}>{footer}</div>}
        </div>
      </div>

      <aside className={styles.infoPane} aria-label="How this network works">
        <div className={styles.infoInner}>
          <p className={styles.infoLead}>
            One request is rarely met by one donor.
          </p>
          <p className={styles.infoBody}>
            A request for four units needs four people. This system keeps a request open
            until the units actually arrive, and only asks donors who are medically able
            to give today.
          </p>

          <dl className={styles.infoStats}>
            <div className={styles.infoStat}>
              <dt>Eligibility</dt>
              <dd>
                Checked against availability, age, weight, and the interval since the last
                donation before anyone is contacted.
              </dd>
            </div>
            <div className={styles.infoStat}>
              <dt>Fulfilment</dt>
              <dd>
                Tracked unit by unit across every donor who contributes, not as a single
                yes or no.
              </dd>
            </div>
            <div className={styles.infoStat}>
              <dt>Privacy</dt>
              <dd>
                Donor contact details are visible to network administrators only, never to
                the people making requests.
              </dd>
            </div>
          </dl>
        </div>
      </aside>
    </div>
  )
}
