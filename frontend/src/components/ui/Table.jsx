import { Button } from './Button'
import styles from './Table.module.css'

/**
 * A data table.
 *
 * The wrapper scrolls horizontally rather than the page. A dense table on a narrow screen
 * has to overflow somewhere, and a page that scrolls sideways makes the whole layout,
 * including the navigation, drift off screen.
 */
export function Table({ children, caption }) {
  return (
    <div className={styles.scroll} tabIndex={0} role="region" aria-label={caption}>
      <table className={styles.table}>
        {caption && <caption className="sr-only">{caption}</caption>}
        {children}
      </table>
    </div>
  )
}

export function Th({ children, numeric = false, width }) {
  return (
    <th scope="col" className={numeric ? styles.numeric : undefined} style={width ? { width } : undefined}>
      {children}
    </th>
  )
}

export function Td({ children, numeric = false, muted = false, className = '' }) {
  return (
    <td
      className={[numeric ? styles.numeric : '', muted ? styles.muted : '', className]
        .filter(Boolean)
        .join(' ')}
    >
      {children}
    </td>
  )
}

/**
 * Page controls.
 *
 * Reports the range and the total rather than only the page number. "Showing 26 to 50 of
 * 312" tells a coordinator how much of the directory they have looked at; "page 2 of 13"
 * does not.
 */
export function Pagination({ page, pageSize, total, pages, onPageChange }) {
  if (!total) return null

  const first = (page - 1) * pageSize + 1
  const last = Math.min(page * pageSize, total)

  return (
    <nav className={styles.pagination} aria-label="Pagination">
      <p className={styles.paginationCount}>
        Showing <strong>{first}</strong> to <strong>{last}</strong> of{' '}
        <strong>{total}</strong>
      </p>
      {pages > 1 && (
        <div className={styles.paginationControls}>
          <Button size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
            Previous
          </Button>
          <span className={styles.paginationPage}>
            Page {page} of {pages}
          </span>
          <Button size="sm" disabled={page >= pages} onClick={() => onPageChange(page + 1)}>
            Next
          </Button>
        </div>
      )}
    </nav>
  )
}
