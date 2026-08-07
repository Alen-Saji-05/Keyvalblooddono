import { useState } from 'react'

import { Button } from '../../components/ui/Button'
import { Field, FieldGrid, Select, TextInput } from '../../components/ui/Field'
import { Modal } from '../../components/ui/Modal'
import { FormAlert } from '../../components/ui/States'
import { fieldErrorsFrom, useCreateDonor } from '../../api/hooks'
import { useMeta } from '../../api/meta'

const BLANK = {
  name: '',
  blood_group: '',
  sex: '',
  date_of_birth: '',
  weight_kg: '',
  phone: '',
  email: '',
  place: '',
  last_donation_date: '',
}

const TODAY = new Date().toISOString().slice(0, 10)

/**
 * Register a donor without creating a login for them.
 *
 * Most donors are signed up at a drive by a member of staff and never use the portal, so
 * requiring an email address and inventing a password for them would be friction for no
 * benefit. A login can be attached later through the accounts screen.
 */
export function DonorFormModal({ open, onClose }) {
  const { data: meta } = useMeta()
  const createDonor = useCreateDonor()
  const [form, setForm] = useState(BLANK)
  const [fieldErrors, setFieldErrors] = useState({})
  const [error, setError] = useState(null)

  const rules = meta?.eligibility_rules

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
    setForm(BLANK)
    setFieldErrors({})
    setError(null)
    onClose()
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setFieldErrors({})

    const payload = {
      name: form.name,
      blood_group: form.blood_group,
      sex: form.sex,
      date_of_birth: form.date_of_birth,
      weight_kg: form.weight_kg,
      phone: form.phone,
      place: form.place,
      // Optional fields are omitted rather than sent empty. An empty string is not a
      // valid date or email and would be rejected as invalid rather than read as absent.
      ...(form.email ? { email: form.email } : {}),
      ...(form.last_donation_date ? { last_donation_date: form.last_donation_date } : {}),
    }

    try {
      await createDonor.mutateAsync(payload)
      close()
    } catch (err) {
      const fields = fieldErrorsFrom(err)
      setFieldErrors(fields)
      setError(Object.keys(fields).length ? null : err.message)
    }
  }

  return (
    <Modal
      open={open}
      onClose={close}
      title="Register a donor"
      description="No login is created. Contact details stay visible to administrators only."
      width={640}
      footer={
        <>
          <Button onClick={close}>Cancel</Button>
          <Button
            type="submit"
            form="donor-form"
            variant="primary"
            loading={createDonor.isPending}
          >
            Register donor
          </Button>
        </>
      }
    >
      <form id="donor-form" onSubmit={handleSubmit} noValidate>
        <FormAlert>{error}</FormAlert>

        <FieldGrid columns={2}>
          <Field label="Full name" required error={fieldErrors.name}>
            {({ id, describedBy, invalid }) => (
              <TextInput
                id={id}
                aria-describedby={describedBy}
                invalid={invalid}
                required
                value={form.name}
                onChange={(event) => update('name', event.target.value)}
              />
            )}
          </Field>

          <Field label="Blood group" required error={fieldErrors.blood_group}>
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

          <Field label="Sex" required error={fieldErrors.sex} hint="Determines the donation interval">
            {({ id, describedBy, invalid }) => (
              <Select
                id={id}
                aria-describedby={describedBy}
                invalid={invalid}
                required
                value={form.sex}
                onChange={(event) => update('sex', event.target.value)}
              >
                <option value="">Select</option>
                {(meta?.sexes ?? []).map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            )}
          </Field>

          <Field
            label="Date of birth"
            required
            error={fieldErrors.date_of_birth}
            hint={rules ? `Donors are ${rules.min_age} to ${rules.max_age}` : undefined}
          >
            {({ id, describedBy, invalid }) => (
              <TextInput
                id={id}
                aria-describedby={describedBy}
                invalid={invalid}
                type="date"
                required
                max={TODAY}
                value={form.date_of_birth}
                onChange={(event) => update('date_of_birth', event.target.value)}
              />
            )}
          </Field>

          <Field
            label="Weight in kilograms"
            required
            error={fieldErrors.weight_kg}
            hint={rules ? `Minimum ${rules.min_weight_kg} kg` : undefined}
          >
            {({ id, describedBy, invalid }) => (
              <TextInput
                id={id}
                aria-describedby={describedBy}
                invalid={invalid}
                type="number"
                inputMode="decimal"
                step="0.1"
                min="1"
                required
                value={form.weight_kg}
                onChange={(event) => update('weight_kg', event.target.value)}
              />
            )}
          </Field>

          <Field label="Phone number" required error={fieldErrors.phone}>
            {({ id, describedBy, invalid }) => (
              <TextInput
                id={id}
                aria-describedby={describedBy}
                invalid={invalid}
                type="tel"
                required
                value={form.phone}
                onChange={(event) => update('phone', event.target.value)}
              />
            )}
          </Field>

          <Field label="Email address" error={fieldErrors.email} hint="Optional">
            {({ id, describedBy, invalid }) => (
              <TextInput
                id={id}
                aria-describedby={describedBy}
                invalid={invalid}
                type="email"
                value={form.email}
                onChange={(event) => update('email', event.target.value)}
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
            label="Date they last gave blood"
            error={fieldErrors.last_donation_date}
            hint="Leave blank if they have never donated"
          >
            {({ id, describedBy, invalid }) => (
              <TextInput
                id={id}
                aria-describedby={describedBy}
                invalid={invalid}
                type="date"
                max={TODAY}
                value={form.last_donation_date}
                onChange={(event) => update('last_donation_date', event.target.value)}
              />
            )}
          </Field>
        </FieldGrid>
      </form>
    </Modal>
  )
}
