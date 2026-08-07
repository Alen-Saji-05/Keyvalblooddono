import { useState } from 'react'

import { PageHeader } from '../../components/layout/AppShell'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Field, FieldGrid, Select, TextInput } from '../../components/ui/Field'
import { Modal } from '../../components/ui/Modal'
import { ErrorState, FormAlert, LoadingState } from '../../components/ui/States'
import { Table, Td, Th } from '../../components/ui/Table'
import { fieldErrorsFrom, useCreateUser, useUpdateUser, useUsers } from '../../api/hooks'
import { useAuth } from '../../auth/AuthProvider'

const ROLE_TONE = { admin: 'critical', patient: 'info', donor: 'positive' }

export function UsersPage() {
  const { user: me } = useAuth()
  const { data, isPending, isError, error, refetch } = useUsers()
  const updateUser = useUpdateUser()
  const [creating, setCreating] = useState(false)

  return (
    <>
      <PageHeader
        title="Accounts"
        description="Administrator accounts are never created by public sign-up. Deactivating an account takes effect immediately, not when its current session expires."
        actions={
          <Button variant="primary" onClick={() => setCreating(true)}>
            Create account
          </Button>
        }
      />

      <Card>
        {isPending && <LoadingState label="Loading accounts" />}
        {isError && <ErrorState error={error} onRetry={refetch} />}

        {data && (
          <Table caption="User accounts">
            <thead>
              <tr>
                <Th>Name</Th>
                <Th>Email</Th>
                <Th width="110px">Role</Th>
                <Th width="110px">Status</Th>
                <Th width="140px">Last signed in</Th>
                <Th width="1%"> </Th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((account) => {
                const isMe = account.id === me?.id
                return (
                  <tr key={account.id}>
                    <Td>
                      {account.full_name}
                      {isMe && (
                        <span style={{ marginLeft: 'var(--space-2)' }}>
                          <Badge tone="neutral">You</Badge>
                        </span>
                      )}
                    </Td>
                    <Td muted>{account.email}</Td>
                    <Td>
                      <Badge tone={ROLE_TONE[account.role] ?? 'neutral'}>{account.role}</Badge>
                    </Td>
                    <Td>
                      {account.is_active ? (
                        <Badge tone="positive">Active</Badge>
                      ) : (
                        <Badge tone="neutral">Deactivated</Badge>
                      )}
                    </Td>
                    <Td muted>
                      {account.last_login_at ? account.last_login_at.slice(0, 10) : 'Never'}
                    </Td>
                    <Td>
                      {/* An administrator cannot deactivate themselves. The server
                          refuses it so the last admin cannot lock the network out of
                          broadcasting; the button is hidden so nobody tries. */}
                      {!isMe && (
                        <Button
                          size="sm"
                          variant={account.is_active ? 'danger' : 'secondary'}
                          loading={
                            updateUser.isPending && updateUser.variables?.id === account.id
                          }
                          onClick={() =>
                            updateUser.mutate({ id: account.id, is_active: !account.is_active })
                          }
                        >
                          {account.is_active ? 'Deactivate' : 'Reactivate'}
                        </Button>
                      )}
                    </Td>
                  </tr>
                )
              })}
            </tbody>
          </Table>
        )}
      </Card>

      <CreateUserModal open={creating} onClose={() => setCreating(false)} />
    </>
  )
}

function CreateUserModal({ open, onClose }) {
  const createUser = useCreateUser()
  const [form, setForm] = useState({ email: '', password: '', full_name: '', role: 'admin' })
  const [fieldErrors, setFieldErrors] = useState({})
  const [error, setError] = useState(null)

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
    setForm({ email: '', password: '', full_name: '', role: 'admin' })
    setFieldErrors({})
    setError(null)
    onClose()
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setFieldErrors({})
    try {
      await createUser.mutateAsync(form)
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
      title="Create an account"
      description="Donor accounts are created from the donor registry, because they must be linked to an existing donor record."
      footer={
        <>
          <Button onClick={close}>Cancel</Button>
          <Button type="submit" form="user-form" variant="primary" loading={createUser.isPending}>
            Create account
          </Button>
        </>
      }
    >
      <form id="user-form" onSubmit={handleSubmit} noValidate>
        <FormAlert>{error}</FormAlert>

        <FieldGrid columns={2}>
          <Field label="Full name" required error={fieldErrors.full_name}>
            {({ id, describedBy, invalid }) => (
              <TextInput
                id={id}
                aria-describedby={describedBy}
                invalid={invalid}
                required
                value={form.full_name}
                onChange={(event) => update('full_name', event.target.value)}
              />
            )}
          </Field>

          <Field label="Role" required error={fieldErrors.role}>
            {({ id, describedBy, invalid }) => (
              <Select
                id={id}
                aria-describedby={describedBy}
                invalid={invalid}
                value={form.role}
                onChange={(event) => update('role', event.target.value)}
              >
                <option value="admin">Administrator</option>
                <option value="patient">Patient</option>
              </Select>
            )}
          </Field>
        </FieldGrid>

        <div style={{ marginTop: 'var(--space-4)' }}>
          <Field label="Email address" required error={fieldErrors.email}>
            {({ id, describedBy, invalid }) => (
              <TextInput
                id={id}
                aria-describedby={describedBy}
                invalid={invalid}
                type="email"
                required
                value={form.email}
                onChange={(event) => update('email', event.target.value)}
              />
            )}
          </Field>
        </div>

        <div style={{ marginTop: 'var(--space-4)' }}>
          <Field
            label="Temporary password"
            required
            error={fieldErrors.password}
            hint="At least 12 characters. Share it with them directly and ask them to change it after signing in."
          >
            {({ id, describedBy, invalid }) => (
              <TextInput
                id={id}
                aria-describedby={describedBy}
                invalid={invalid}
                type="text"
                required
                minLength={12}
                value={form.password}
                onChange={(event) => update('password', event.target.value)}
              />
            )}
          </Field>
        </div>
      </form>
    </Modal>
  )
}
