import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { Button } from '../../components/ui/Button'
import { Field, TextInput } from '../../components/ui/Field'
import { FormAlert } from '../../components/ui/States'
import { HOME_FOR_ROLE } from '../../auth/guards'
import { useAuth } from '../../auth/AuthProvider'
import { AuthLayout } from './AuthLayout'
import styles from './AuthForms.module.css'

export function LoginPage() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)

    try {
      const user = await signIn(email, password)
      // Return the user to wherever they were heading before being asked to sign in.
      const target = location.state?.from?.pathname
      navigate(target || HOME_FOR_ROLE[user.role] || '/', { replace: true })
    } catch (err) {
      setError(err.message || 'Sign in failed.')
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout
      title="Sign in"
      description="Donors, patients, and network administrators use the same sign-in."
      footer={
        <>
          Do not have an account? <Link to="/register">Register as a donor or patient</Link>.
        </>
      }
    >
      <form className={styles.form} onSubmit={handleSubmit} noValidate>
        {/* The server returns one message for a wrong password, an unknown address, and a
            deactivated account, so this is shown once above the form rather than being
            attributed to a field the user might then "correct". */}
        <FormAlert>{error}</FormAlert>

        <Field label="Email address" required>
          {({ id, describedBy, invalid }) => (
            <TextInput
              id={id}
              aria-describedby={describedBy}
              invalid={invalid}
              type="email"
              name="email"
              autoComplete="username"
              autoFocus
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          )}
        </Field>

        <Field label="Password" required>
          {({ id, describedBy, invalid }) => (
            <TextInput
              id={id}
              aria-describedby={describedBy}
              invalid={invalid}
              type="password"
              name="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          )}
        </Field>

        <Button type="submit" variant="primary" size="lg" fullWidth loading={submitting}>
          Sign in
        </Button>
      </form>
    </AuthLayout>
  )
}
