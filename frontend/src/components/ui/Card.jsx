import styles from './Card.module.css'

export function Card({ children, className = '', padded = true, ...rest }) {
  return (
    <section
      className={[styles.card, padded ? styles.padded : '', className].filter(Boolean).join(' ')}
      {...rest}
    >
      {children}
    </section>
  )
}

export function CardHeader({ title, description, actions, level = 2 }) {
  const Heading = `h${level}`
  return (
    <header className={styles.header}>
      <div className={styles.headerText}>
        <Heading className={styles.title}>{title}</Heading>
        {description && <p className={styles.description}>{description}</p>}
      </div>
      {actions && <div className={styles.actions}>{actions}</div>}
    </header>
  )
}

export function CardBody({ children, className = '' }) {
  return <div className={[styles.body, className].filter(Boolean).join(' ')}>{children}</div>
}

export function CardFooter({ children }) {
  return <footer className={styles.footer}>{children}</footer>
}

/** A labelled value, for detail panels. */
export function DataItem({ label, children, wide = false }) {
  return (
    <div className={[styles.dataItem, wide ? styles.dataItemWide : ''].filter(Boolean).join(' ')}>
      <dt className={styles.dataLabel}>{label}</dt>
      <dd className={styles.dataValue}>{children ?? <span className={styles.empty}>Not recorded</span>}</dd>
    </div>
  )
}

export function DataList({ children, columns = 2 }) {
  return (
    <dl className={styles.dataList} data-columns={columns}>
      {children}
    </dl>
  )
}
