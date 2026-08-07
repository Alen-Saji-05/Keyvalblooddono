import { useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'

import styles from './Modal.module.css'

/**
 * A modal dialog.
 *
 * Three things a hand-rolled overlay usually gets wrong and this does not: Escape closes
 * it, focus moves into it on open and returns to whatever opened it on close, and the
 * page behind does not scroll. Without the last one, scrolling a dialog on a phone
 * scrolls the page underneath instead and the dialog appears frozen.
 *
 * Focus is not fully trapped. A full trap is more code than is warranted here, and the
 * dialog is rendered in a portal at the end of the body, so tabbing past the last control
 * leaves through the browser chrome rather than into the page behind it.
 */
export function Modal({ open, onClose, title, description, children, footer, width = 520 }) {
  const titleId = useId()
  const descriptionId = useId()
  const panelRef = useRef(null)
  const previouslyFocused = useRef(null)

  useEffect(() => {
    if (!open) return undefined

    previouslyFocused.current = document.activeElement

    function onKeyDown(event) {
      if (event.key === 'Escape') onClose()
    }

    document.addEventListener('keydown', onKeyDown)

    const { overflow } = document.body.style
    document.body.style.overflow = 'hidden'

    // Focus the panel rather than the first control. Focusing the first input would make
    // a screen reader start reading mid-form, past the title explaining what the dialog
    // is for.
    panelRef.current?.focus()

    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = overflow
      previouslyFocused.current?.focus?.()
    }
  }, [open, onClose])

  if (!open) return null

  return createPortal(
    <div className={styles.overlay}>
      <div
        className={styles.backdrop}
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        ref={panelRef}
        className={styles.panel}
        style={{ maxWidth: width }}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        tabIndex={-1}
      >
        <header className={styles.header}>
          <div>
            <h2 className={styles.title} id={titleId}>
              {title}
            </h2>
            {description && (
              <p className={styles.description} id={descriptionId}>
                {description}
              </p>
            )}
          </div>
          <button type="button" className={styles.close} onClick={onClose}>
            <span className="sr-only">Close</span>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </header>

        <div className={styles.body}>{children}</div>

        {footer && <footer className={styles.footer}>{footer}</footer>}
      </div>
    </div>,
    document.body,
  )
}
