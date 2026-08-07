import { useState } from 'react'

import { Button } from '../../components/ui/Button'
import { Field, TextInput } from '../../components/ui/Field'
import { Modal } from '../../components/ui/Modal'
import { FormAlert } from '../../components/ui/States'
import { useBroadcast } from '../../api/hooks'
import { useMeta } from '../../api/meta'
import styles from './Requests.module.css'

/**
 * Send a request to eligible donors.
 *
 * Two options, and both are consequential enough to be explained rather than labelled.
 * Widening to compatible groups changes who receives a message about somebody's medical
 * emergency; narrowing by place is usually the difference between a useful appeal and a
 * mass one.
 *
 * The result is shown in place rather than as a toast that disappears. "Notified 0" needs
 * to be read alongside "already notified" and "eligible total" to be understood at all,
 * and those numbers decide what the administrator does next.
 */
export function BroadcastModal({ request, onClose }) {
  const { data: meta } = useMeta()
  const broadcast = useBroadcast()
  const [includeCompatible, setIncludeCompatible] = useState(false)
  const [place, setPlace] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const compatible = meta?.compatibility?.[request?.blood_group] ?? []

  function close() {
    setResult(null)
    setError(null)
    setIncludeCompatible(false)
    setPlace('')
    onClose()
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    try {
      const outcome = await broadcast.mutateAsync({
        id: request.id,
        include_compatible: includeCompatible,
        ...(place ? { place } : {}),
      })
      setResult(outcome)
    } catch (err) {
      setError(err.message)
    }
  }

  if (!request) return null

  return (
    <Modal
      open
      onClose={close}
      title="Broadcast this request"
      description={`${request.blood_group} needed at ${request.hospital}, ${request.units_outstanding} of ${request.units_required} units still outstanding.`}
      width={560}
      footer={
        result ? (
          <Button variant="primary" onClick={close}>
            Done
          </Button>
        ) : (
          <>
            <Button onClick={close}>Cancel</Button>
            <Button
              type="submit"
              form="broadcast-form"
              variant="primary"
              loading={broadcast.isPending}
            >
              Send notifications
            </Button>
          </>
        )
      }
    >
      {result ? (
        <>
          <p>
            Notifications sent. Donors already told about this request were skipped rather
            than messaged twice.
          </p>
          <div className={styles.broadcastResult}>
            <div className={styles.broadcastFigure}>
              <p className={styles.broadcastValue}>{result.notified}</p>
              <p className={styles.broadcastLabel}>Newly notified</p>
            </div>
            <div className={styles.broadcastFigure}>
              <p className={styles.broadcastValue}>{result.already_notified}</p>
              <p className={styles.broadcastLabel}>Already notified</p>
            </div>
            <div className={styles.broadcastFigure}>
              <p className={styles.broadcastValue}>{result.eligible_total}</p>
              <p className={styles.broadcastLabel}>Eligible in total</p>
            </div>
            {result.delivery_failures > 0 && (
              <div className={styles.broadcastFigure}>
                <p className={styles.broadcastValue}>{result.delivery_failures}</p>
                <p className={styles.broadcastLabel}>Delivery failures</p>
              </div>
            )}
          </div>

          {result.eligible_total === 0 && (
            <p style={{ marginTop: 'var(--space-4)', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
              No donor of this group can give right now. Widening to compatible groups, or
              removing the place filter, may reach someone.
            </p>
          )}
        </>
      ) : (
        <form id="broadcast-form" onSubmit={handleSubmit} noValidate>
          <FormAlert>{error}</FormAlert>

          <Field
            label="Restrict to a place"
            hint="Leave blank to notify eligible donors everywhere. A donor three hundred kilometres away cannot help with a request needed tomorrow."
          >
            {({ id, describedBy }) => (
              <TextInput
                id={id}
                aria-describedby={describedBy}
                placeholder={request.place}
                value={place}
                onChange={(event) => setPlace(event.target.value)}
              />
            )}
          </Field>

          <label className={styles.checkbox} style={{ marginTop: 'var(--space-4)', height: 'auto', alignItems: 'flex-start' }}>
            <input
              type="checkbox"
              checked={includeCompatible}
              onChange={(event) => setIncludeCompatible(event.target.checked)}
              style={{ marginTop: '3px' }}
            />
            <span>
              <span style={{ display: 'block', fontWeight: 'var(--weight-medium)' }}>
                Include compatible blood groups
              </span>
              <span style={{ display: 'block', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: '2px', whiteSpace: 'normal' }}>
                {includeCompatible
                  ? `Will notify donors of ${compatible.join(', ')}.`
                  : `Only ${request.blood_group} donors will be notified. Compatible groups are ${compatible.join(', ')}.`}
              </span>
            </span>
          </label>
        </form>
      )}
    </Modal>
  )
}
