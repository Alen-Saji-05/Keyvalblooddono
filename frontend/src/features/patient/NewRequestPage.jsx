import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { PageHeader } from '../../components/layout/AppShell'
import { Button } from '../../components/ui/Button'
import { Card, CardFooter, CardHeader } from '../../components/ui/Card'
import { Field, FieldGrid, Select, TextInput, Textarea } from '../../components/ui/Field'
import { FormAlert } from '../../components/ui/States'
import { fieldErrorsFrom, useAvailability, useCreateRequest } from '../../api/hooks'
import { useMeta } from '../../api/meta'
import { useAuth } from '../../auth/AuthProvider'
import styles from './Patient.module.css'

const TODAY = new Date().toISOString().slice(0, 10)

export function NewRequestPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const { data: meta } = useMeta()
  const createRequest = useCreateRequest()

  const [form, setForm] = useState({
    patient_name: user?.full_name ?? '',
    blood_group: '',
    hospital: '',
    place: '',
    contact_phone: '',
    units_required: '1',
    needed_by_date: '',
    notes: '',
  })
  const [fieldErrors, setFieldErrors] = useState({})
  const [error, setError] = useState(null)

  // Live feedback on whether anyone can actually help, updated as the group is chosen.
  // A patient filing a request for a group with no eligible donors should learn that now,
  // not after three days of silence.
  const { data: availability } = useAvailability(form.place || undefined)
  const supply = (availability?.items ?? []).find(
    (row) => row.blood_group === form.blood_group,
  )

  function update(name, value) {
    setForm((current) => ({ ...current, [name]: value }))
    setFieldErrors((current) => {
      if (!current[name]) return current
      const next = { ...current }
      delete next[name]
      return next
    })
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setFieldErrors({})

    try {
      const created = await createRequest.mutateAsync({
        patient_name: form.patient_name,
        blood_group: form.blood_group,
        hospital: form.hospital,
        place: form.place,
        contact_phone: form.contact_phone,
        units_required: Number(form.units_required),
        needed_by_date: form.needed_by_date,
        ...(form.notes ? { notes: form.notes } : {}),
      })
      navigate(`/my-requests/${created.id}`)
    } catch (err) {
      const fields = fieldErrorsFrom(err)
      setFieldErrors(fields)
      setError(Object.keys(fields).length ? null : err.message)
    }
  }

  return (
    <>
      <PageHeader
        title="Request blood"
        description="A network administrator reviews each request and contacts eligible donors on your behalf."
      />

      <form onSubmit={handleSubmit} noValidate className={styles.formWidth}>
        <Card>
          <CardHeader title="Who the blood is for" />
          <FormAlert>{error}</FormAlert>

          <FieldGrid columns={2}>
            <Field label="Patient name" required error={fieldErrors.patient_name}>
              {({ id, describedBy, invalid }) => (
                <TextInput
                  id={id}
                  aria-describedby={describedBy}
                  invalid={invalid}
                  required
                  value={form.patient_name}
                  onChange={(event) => update('patient_name', event.target.value)}
                />
              )}
            </Field>

            <Field label="Blood group needed" required error={fieldErrors.blood_group}>
              {({ id, describedBy, invalid }) => (
                <Select
                  id={id}
                  aria-describedby={describedBy}
                  invalid={invalid}
                  required
                  value={form.blood_group}
                  onChange={(event) => update('blood_group', event.target.value)}
                >
                  <option value="">Select</option>
                  {(meta?.blood_groups ?? []).map((group) => (
                    <option key={group} value={group}>
                      {group}
                    </option>
                  ))}
                </Select>
              )}
            </Field>

            <Field
              label="Units required"
              required
              error={fieldErrors.units_required}
              hint="One donor normally gives one unit"
            >
              {({ id, describedBy, invalid }) => (
                <TextInput
                  id={id}
                  aria-describedby={describedBy}
                  invalid={invalid}
                  type="number"
                  min="1"
                  max="20"
                  required
                  value={form.units_required}
                  onChange={(event) => update('units_required', event.target.value)}
                />
              )}
            </Field>

            <Field label="Needed by" required error={fieldErrors.needed_by_date}>
              {({ id, describedBy, invalid }) => (
                <TextInput
                  id={id}
                  aria-describedby={describedBy}
                  invalid={invalid}
                  type="date"
                  required
                  min={TODAY}
                  value={form.needed_by_date}
                  onChange={(event) => update('needed_by_date', event.target.value)}
                />
              )}
            </Field>
          </FieldGrid>

          {form.blood_group && supply && (
            <div className={supply.eligible_donors > 0 ? styles.supplyGood : styles.supplyThin}>
              {supply.eligible_donors > 0 ? (
                <>
                  <strong>{supply.eligible_donors}</strong> {form.blood_group} donors can give
                  right now{form.place ? ` near ${form.place}` : ''}, out of{' '}
                  {supply.total_donors} registered.
                </>
              ) : (
                <>
                  No {form.blood_group} donor can give right now
                  {form.place ? ` near ${form.place}` : ''}. File the request anyway - an
                  administrator can widen the search to compatible blood groups.
                </>
              )}
            </div>
          )}
        </Card>

        <div style={{ marginTop: 'var(--space-5)' }}>
          <Card>
            <CardHeader title="Where and how to reach you" />

            <FieldGrid columns={2}>
              <Field label="Hospital" required error={fieldErrors.hospital}>
                {({ id, describedBy, invalid }) => (
                  <TextInput
                    id={id}
                    aria-describedby={describedBy}
                    invalid={invalid}
                    required
                    value={form.hospital}
                    onChange={(event) => update('hospital', event.target.value)}
                  />
                )}
              </Field>

              <Field label="Town or city" required error={fieldErrors.place}>
                {({ id, describedBy, invalid }) => (
                  <TextInput
                    id={id}
                    aria-describedby={describedBy}
                    invalid={invalid}
                    required
                    value={form.place}
                    onChange={(event) => update('place', event.target.value)}
                  />
                )}
              </Field>

              <Field
                label="Contact number"
                required
                error={fieldErrors.contact_phone}
                hint="Given to donors who offer to help"
              >
                {({ id, describedBy, invalid }) => (
                  <TextInput
                    id={id}
                    aria-describedby={describedBy}
                    invalid={invalid}
                    type="tel"
                    required
                    value={form.contact_phone}
                    onChange={(event) => update('contact_phone', event.target.value)}
                  />
                )}
              </Field>
            </FieldGrid>

            <div style={{ marginTop: 'var(--space-4)' }}>
              <Field label="Anything else donors should know" hint="Optional">
                {({ id, describedBy }) => (
                  <Textarea
                    id={id}
                    aria-describedby={describedBy}
                    value={form.notes}
                    onChange={(event) => update('notes', event.target.value)}
                  />
                )}
              </Field>
            </div>

            <CardFooter>
              <Button onClick={() => navigate('/my-requests')}>Cancel</Button>
              <Button type="submit" variant="primary" loading={createRequest.isPending}>
                File request
              </Button>
            </CardFooter>
          </Card>
        </div>
      </form>
    </>
  )
}
