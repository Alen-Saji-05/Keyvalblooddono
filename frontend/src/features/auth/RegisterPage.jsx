import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { Button } from '../../components/ui/Button'
import { Field, FieldGrid, Select, TextInput } from '../../components/ui/Field'
import { FormAlert } from '../../components/ui/States'
import { HOME_FOR_ROLE } from '../../auth/guards'
import { useAuth } from '../../auth/AuthProvider'
import { useMeta } from '../../api/meta'
import { AuthLayout } from './AuthLayout'
import styles from './AuthForms.module.css'

const EMPTY_DONOR = {
  blood_group: '',
  sex: '',
  date_of_birth: '',
  weight_kg: '',
  phone: '',
  place: '',
  last_donation_date: '',
}

export function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const { data: meta } = useMeta()

  const [role, setRole] = useState('donor')
  const [form, setForm] = useState({
    email: '',
    password: '',
    full_name: '',
    ...EMPTY_DONOR,
  })
  const [fieldErrors, setFieldErrors] = useState({})
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const rules = meta?.eligibility_rules

  function update(name, value) {
    setForm((current) => ({ ...current, [name]: value }))
    // Clear the message for a field as soon as it is edited. Leaving a stale error under
    // a field the user has just fixed reads as though the fix was rejected.
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
    setSubmitting(true)

    const payload =
      role === 'patient'
        ? {
            role: 'patient',
            email: form.email,
            password: form.password,
            full_name: form.full_name,
          }
        : {
            role: 'donor',
            email: form.email,
            password: form.password,
            full_name: form.full_name,
            blood_group: form.blood_group,
            sex: form.sex,
            date_of_birth: form.date_of_birth,
            weight_kg: form.weight_kg,
            phone: form.phone,
            place: form.place,
            // Omitted entirely rather than sent as an empty string, which the server
            // would reject as an invalid date rather than reading as "never donated".
            ...(form.last_donation_date
              ? { last_donation_date: form.last_donation_date }
              : {}),
          }

    try {
      const user = await register(payload)
      navigate(HOME_FOR_ROLE[user.role] || '/', { replace: true })
    } catch (err) {
      // The server keys validation messages by plain field name, so each one can be
      // attached to the input it belongs to rather than dumped in a list at the top.
      const fields = err.fieldErrors || {}
      setFieldErrors(
        Object.fromEntries(Object.entries(fields).map(([key, messages]) => [key, messages[0]])),
      )
      setError(Object.keys(fields).length ? null : err.message)
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout
      title="Create an account"
      description="Register to give blood, or to request it for a patient."
      footer={
        <>
          Already registered? <Link to="/login">Sign in</Link>.
        </>
      }
    >
      <form className={styles.form} onSubmit={handleSubmit} noValidate>
        <FormAlert>{error}</FormAlert>

        <fieldset className={styles.roleChoice}>
          <legend className={styles.roleLegend}>I am registering as</legend>

          <label className={styles.roleOption}>
            <input
              className={styles.roleInput}
              type="radio"
              name="role"
              value="donor"
              checked={role === 'donor'}
              onChange={() => setRole('donor')}
            />
            <span className={styles.roleTitle}>A donor</span>
            <span className={styles.roleHint}>
              I am willing to give blood and want to be contacted when it is needed.
            </span>
          </label>

          <label className={styles.roleOption}>
            <input
              className={styles.roleInput}
              type="radio"
              name="role"
              value="patient"
              checked={role === 'patient'}
              onChange={() => setRole('patient')}
            />
            <span className={styles.roleTitle}>A patient</span>
            <span className={styles.roleHint}>
              I need to request blood for myself or someone I am caring for.
            </span>
          </label>
        </fieldset>

        <Field label="Full name" required error={fieldErrors.full_name}>
          {({ id, describedBy, invalid }) => (
            <TextInput
              id={id}
              aria-describedby={describedBy}
              invalid={invalid}
              name="full_name"
              autoComplete="name"
              required
              value={form.full_name}
              onChange={(event) => update('full_name', event.target.value)}
            />
          )}
        </Field>

        <Field label="Email address" required error={fieldErrors.email}>
          {({ id, describedBy, invalid }) => (
            <TextInput
              id={id}
              aria-describedby={describedBy}
              invalid={invalid}
              type="email"
              name="email"
              autoComplete="username"
              required
              value={form.email}
              onChange={(event) => update('email', event.target.value)}
            />
          )}
        </Field>

        <Field
          label="Password"
          required
          error={fieldErrors.password}
          hint="At least 12 characters. Length matters more than mixing symbols, so a short phrase you can remember is a good choice."
        >
          {({ id, describedBy, invalid }) => (
            <TextInput
              id={id}
              aria-describedby={describedBy}
              invalid={invalid}
              type="password"
              name="password"
              autoComplete="new-password"
              required
              minLength={12}
              value={form.password}
              onChange={(event) => update('password', event.target.value)}
            />
          )}
        </Field>

        {role === 'donor' && (
          <>
            <div>
              <p className={styles.sectionHeading}>Donor details</p>
              <p className={styles.sectionNote}>
                Used to work out when you can safely give. Falling outside the criteria
                does not stop you registering, it only means you are not contacted until
                you qualify.
              </p>
            </div>

            <FieldGrid columns={2}>
              <Field label="Blood group" required error={fieldErrors.blood_group}>
                {({ id, describedBy, invalid }) => (
                  <Select
                    id={id}
                    aria-describedby={describedBy}
                    invalid={invalid}
                    name="blood_group"
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

              <Field label="Sex" required error={fieldErrors.sex}>
                {({ id, describedBy, invalid }) => (
                  <Select
                    id={id}
                    aria-describedby={describedBy}
                    invalid={invalid}
                    name="sex"
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
                    name="date_of_birth"
                    required
                    max={new Date().toISOString().slice(0, 10)}
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
                    name="weight_kg"
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
                    name="phone"
                    autoComplete="tel"
                    required
                    value={form.phone}
                    onChange={(event) => update('phone', event.target.value)}
                  />
                )}
              </Field>

              <Field
                label="Town or city"
                required
                error={fieldErrors.place}
                hint="Used to find donors near a hospital"
              >
                {({ id, describedBy, invalid }) => (
                  <TextInput
                    id={id}
                    aria-describedby={describedBy}
                    invalid={invalid}
                    name="place"
                    autoComplete="address-level2"
                    required
                    value={form.place}
                    onChange={(event) => update('place', event.target.value)}
                  />
                )}
              </Field>
            </FieldGrid>

            <Field
              label="Date you last gave blood"
              error={fieldErrors.last_donation_date}
              hint={
                rules
                  ? `Leave blank if you have never donated. The interval is ${rules.cooldown_days_male} days for male donors and ${rules.cooldown_days_female} for others.`
                  : 'Leave blank if you have never donated.'
              }
            >
              {({ id, describedBy, invalid }) => (
                <TextInput
                  id={id}
                  aria-describedby={describedBy}
                  invalid={invalid}
                  type="date"
                  name="last_donation_date"
                  max={new Date().toISOString().slice(0, 10)}
                  value={form.last_donation_date}
                  onChange={(event) => update('last_donation_date', event.target.value)}
                />
              )}
            </Field>
          </>
        )}

        <div className={styles.submitRow}>
          <Button type="submit" variant="primary" size="lg" fullWidth loading={submitting}>
            Create account
          </Button>
        </div>
      </form>
    </AuthLayout>
  )
}
