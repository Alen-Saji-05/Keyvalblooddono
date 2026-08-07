import { useEffect, useState } from 'react'

import { Button } from '../../components/ui/Button'
import { Field, Select, Textarea } from '../../components/ui/Field'
import { Modal } from '../../components/ui/Modal'
import { FormAlert } from '../../components/ui/States'
import { useSetDonorStatus } from '../../api/hooks'
import { useMeta } from '../../api/meta'

/**
 * Change a donor's availability.
 *
 * The reason is the status, not a free-text field. The note is additional detail and is
 * only offered when the donor is being marked unavailable, because a note attached to an
 * available donor is rejected by the server and would never be displayed anywhere.
 */
export function DonorStatusModal({ donor, onClose }) {
  const { data: meta } = useMeta()
  const setStatus = useSetDonorStatus()
  const [status, setStatusValue] = useState('available')
  const [note, setNote] = useState('')
  const [error, setError] = useState(null)

  // Seed from the donor being edited each time the dialog opens, so it does not show the
  // previous donor's values for a moment.
  useEffect(() => {
    if (donor) {
      setStatusValue(donor.status)
      setNote(donor.status_note ?? '')
      setError(null)
    }
  }, [donor])

  const unavailable = status !== 'available'

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    try {
      await setStatus.mutateAsync({
        id: donor.id,
        status,
        note: unavailable ? note : undefined,
      })
      onClose()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <Modal
      open={Boolean(donor)}
      onClose={onClose}
      title="Change availability"
      description={donor ? `${donor.name}, ${donor.blood_group}, ${donor.place}` : undefined}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" form="status-form" variant="primary" loading={setStatus.isPending}>
            Save
          </Button>
        </>
      }
    >
      <form id="status-form" onSubmit={handleSubmit} noValidate>
        <FormAlert>{error}</FormAlert>

        <Field
          label="Availability"
          required
          hint="An unavailable donor is never included in a broadcast."
        >
          {({ id, describedBy }) => (
            <Select
              id={id}
              aria-describedby={describedBy}
              value={status}
              onChange={(event) => setStatusValue(event.target.value)}
            >
              {(meta?.donor_statuses ?? []).map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          )}
        </Field>

        {unavailable && (
          <div style={{ marginTop: 'var(--space-4)' }}>
            <Field
              label="Note"
              hint="Optional detail, such as when they expect to return."
            >
              {({ id, describedBy }) => (
                <Textarea
                  id={id}
                  aria-describedby={describedBy}
                  maxLength={255}
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                />
              )}
            </Field>
          </div>
        )}
      </form>
    </Modal>
  )
}
