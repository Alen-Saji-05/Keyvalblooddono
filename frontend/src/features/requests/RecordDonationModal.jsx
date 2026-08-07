import { useState } from 'react'

import { Button } from '../../components/ui/Button'
import { Field, FieldGrid, Select, TextInput, Textarea } from '../../components/ui/Field'
import { Modal } from '../../components/ui/Modal'
import { FormAlert } from '../../components/ui/States'
import { fieldErrorsFrom, useDonors, useRecordDonation } from '../../api/hooks'
import { useDebounced } from '../../hooks/useDebounced'

const TODAY = new Date().toISOString().slice(0, 10)

/**
 * Record units received against a request.
 *
 * The donor picker searches the directory rather than listing every donor, because a real
 * network has thousands and a select element with thousands of options is unusable.
 *
 * It deliberately does not filter to eligible donors only. Somebody may have given at the
 * hospital before the system knew about them, and the units arrived regardless; refusing
 * to record a donation that physically happened would put the fulfilment total out of
 * step with reality, which is worse than recording it.
 */
export function RecordDonationModal({ request, onClose }) {
  const recordDonation = useRecordDonation()
  const [search, setSearch] = useState('')
  const [form, setForm] = useState({ donor_id: '', units_given: '1', donation_date: TODAY, notes: '' })
  const [fieldErrors, setFieldErrors] = useState({})
  const [error, setError] = useState(null)

  const debouncedSearch = useDebounced(search, 300)
  const { data: donors, isFetching } = useDonors({
    page: 1,
    page_size: 25,
    q: debouncedSearch || undefined,
    blood_group: request?.blood_group,
  })

  function update(name, value) {
    setForm((current) => ({ ...current, [name]: value }))
    setFieldErrors((current) => {
      if (!current[name]) return current
      const next = { ...current }
      delete next[name]
      return next
    })
  }

  function close() {
    setForm({ donor_id: '', units_given: '1', donation_date: TODAY, notes: '' })
    setSearch('')
    setFieldErrors({})
    setError(null)
    onClose()
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setFieldErrors({})

    try {
      await recordDonation.mutateAsync({
        id: request.id,
        donor_id: Number(form.donor_id),
        units_given: Number(form.units_given),
        donation_date: form.donation_date,
        ...(form.notes ? { notes: form.notes } : {}),
      })
      close()
    } catch (err) {
      const fields = fieldErrorsFrom(err)
      setFieldErrors(fields)
      setError(Object.keys(fields).length ? null : err.message)
    }
  }

  if (!request) return null

  return (
    <Modal
      open
      onClose={close}
      title="Record a donation"
      description={`${request.units_outstanding} of ${request.units_required} units still needed for ${request.patient_name}.`}
      width={560}
      footer={
        <>
          <Button onClick={close}>Cancel</Button>
          <Button
            type="submit"
            form="donation-form"
            variant="primary"
            loading={recordDonation.isPending}
            disabled={!form.donor_id}
          >
            Record donation
          </Button>
        </>
      }
    >
      <form id="donation-form" onSubmit={handleSubmit} noValidate>
        <FormAlert>{error}</FormAlert>

        <Field
          label="Find the donor"
          hint={`Searching ${request.blood_group} donors by name, phone, or place.`}
        >
          {({ id, describedBy }) => (
            <TextInput
              id={id}
              aria-describedby={describedBy}
              type="search"
              placeholder="Start typing a name"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          )}
        </Field>

        <div style={{ marginTop: 'var(--space-4)' }}>
          <Field label="Donor" required error={fieldErrors.donor_id}>
            {({ id, describedBy, invalid }) => (
              <Select
                id={id}
                aria-describedby={describedBy}
                invalid={invalid}
                required
                value={form.donor_id}
                onChange={(event) => update('donor_id', event.target.value)}
              >
                <option value="">
                  {isFetching ? 'Searching...' : `Select from ${donors?.total ?? 0} donors`}
                </option>
                {(donors?.items ?? []).map((donor) => (
                  <option key={donor.id} value={donor.id}>
                    {donor.name} - {donor.place} - {donor.phone}
                    {donor.is_eligible ? '' : ' (not currently eligible)'}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>

        <div style={{ marginTop: 'var(--space-4)' }}>
          <FieldGrid columns={2}>
            <Field
              label="Units given"
              required
              error={fieldErrors.units_given}
              hint="Usually one"
            >
              {({ id, describedBy, invalid }) => (
                <TextInput
                  id={id}
                  aria-describedby={describedBy}
                  invalid={invalid}
                  type="number"
                  min="1"
                  max="10"
                  required
                  value={form.units_given}
                  onChange={(event) => update('units_given', event.target.value)}
                />
              )}
            </Field>

            <Field label="Date of donation" required error={fieldErrors.donation_date}>
              {({ id, describedBy, invalid }) => (
                <TextInput
                  id={id}
                  aria-describedby={describedBy}
                  invalid={invalid}
                  type="date"
                  required
                  max={TODAY}
                  value={form.donation_date}
                  onChange={(event) => update('donation_date', event.target.value)}
                />
              )}
            </Field>
          </FieldGrid>
        </div>

        <div style={{ marginTop: 'var(--space-4)' }}>
          <Field label="Notes" hint="Optional">
            {({ id, describedBy }) => (
              <Textarea
                id={id}
                aria-describedby={describedBy}
                rows={2}
                value={form.notes}
                onChange={(event) => update('notes', event.target.value)}
              />
            )}
          </Field>
        </div>
      </form>
    </Modal>
  )
}
