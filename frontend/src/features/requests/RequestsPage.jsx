import { useState } from 'react'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/AppShell'
import { BloodGroupBadge, RequestStatusBadge } from '../../components/ui/Badge'
import { Button, LinkButton } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Select, TextInput } from '../../components/ui/Field'
import { UnitsProgress } from '../../components/ui/Stat'
import { EmptyState, ErrorState, LoadingState } from '../../components/ui/States'
import { Pagination, Table, Td, Th } from '../../components/ui/Table'
import { Toolbar, ToolbarField } from '../../components/ui/Toolbar'
import { useRequests } from '../../api/hooks'
import { useMeta } from '../../api/meta'
import { useAuth } from '../../auth/AuthProvider'
import styles from './Requests.module.css'

const EMPTY = { status: '', blood_group: '', place: '', include_expired: false }

/**
 * The request list, used by administrators and patients alike.
 *
 * The same screen serves both because the server already scopes the rows: an
 * administrator's query returns every request and a patient's returns only their own. The
 * only difference here is the wording and where a row links to.
 */
export function RequestsPage({ scope = 'admin' }) {
  const { data: meta } = useMeta()
  const { role } = useAuth()
  const [filters, setFilters] = useState(EMPTY)
  const [page, setPage] = useState(1)

  const isPatient = role === 'patient'
  const detailBase = isPatient ? '/my-requests' : '/requests'

  const { data, isPending, isError, error, refetch } = useRequests({
    page,
    page_size: 25,
    status: filters.status || undefined,
    blood_group: filters.blood_group || undefined,
    place: filters.place || undefined,
    include_expired: filters.include_expired || undefined,
  })

  function update(name, value) {
    setFilters((current) => ({ ...current, [name]: value }))
    setPage(1)
  }

  const hasFilters = Object.entries(filters).some(([key, value]) => value !== EMPTY[key])

  return (
    <>
      <PageHeader
        title={isPatient ? 'My requests' : 'Blood requests'}
        description={
          isPatient
            ? 'Requests you have filed, and how many units have arrived against each.'
            : 'Every request in the network. Broadcast to eligible donors and record units as they arrive.'
        }
        actions={
          isPatient ? (
            <LinkButton to="/request/new" variant="primary">
              New request
            </LinkButton>
          ) : null
        }
      />

      <Card>
        <Toolbar hasFilters={hasFilters} onReset={() => { setFilters(EMPTY); setPage(1) }}>
          <ToolbarField label="Status" htmlFor="req-status">
            <Select
              id="req-status"
              value={filters.status}
              onChange={(event) => update('status', event.target.value)}
            >
              <option value="">Any</option>
              {(meta?.request_statuses ?? []).map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </ToolbarField>

          <ToolbarField label="Blood group" htmlFor="req-group">
            <Select
              id="req-group"
              value={filters.blood_group}
              onChange={(event) => update('blood_group', event.target.value)}
            >
              <option value="">Any</option>
              {(meta?.blood_groups ?? []).map((group) => (
                <option key={group} value={group}>
                  {group}
                </option>
              ))}
            </Select>
          </ToolbarField>

          <ToolbarField label="Place" htmlFor="req-place">
            <TextInput
              id="req-place"
              placeholder="Town or city"
              value={filters.place}
              onChange={(event) => update('place', event.target.value)}
            />
          </ToolbarField>

          <ToolbarField label=" " htmlFor="req-expired">
            <label className={styles.checkbox} htmlFor="req-expired">
              <input
                id="req-expired"
                type="checkbox"
                checked={filters.include_expired}
                onChange={(event) => update('include_expired', event.target.checked)}
              />
              Include past their date
            </label>
          </ToolbarField>
        </Toolbar>

        {isPending && <LoadingState label="Loading requests" />}
        {isError && <ErrorState error={error} onRetry={refetch} />}

        {data && data.items.length === 0 && (
          <EmptyState
            title={hasFilters ? 'No requests match these filters' : 'No open requests'}
            description={
              hasFilters
                ? 'Requests whose date has passed are hidden unless you ask for them.'
                : isPatient
                  ? 'When you file a request it will appear here with its progress.'
                  : 'Requests filed by patients appear here for broadcasting.'
            }
            action={
              hasFilters ? (
                <Button onClick={() => { setFilters(EMPTY); setPage(1) }}>Clear filters</Button>
              ) : isPatient ? (
                <LinkButton to="/request/new" variant="primary">
                  File a request
                </LinkButton>
              ) : null
            }
          />
        )}

        {data && data.items.length > 0 && (
          <>
            <Table caption="Blood requests">
              <thead>
                <tr>
                  <Th>Patient and hospital</Th>
                  <Th width="72px">Group</Th>
                  <Th width="200px">Units received</Th>
                  <Th>Status</Th>
                  <Th width="120px">Needed by</Th>
                  <Th numeric width="110px">Outreach</Th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((request) => (
                  <tr key={request.id}>
                    <Td>
                      <Link className={styles.name} to={`${detailBase}/${request.id}`}>
                        {request.patient_name}
                      </Link>
                      <span className={styles.subtle}>
                        {request.hospital}, {request.place}
                      </span>
                    </Td>
                    <Td>
                      <BloodGroupBadge group={request.blood_group} size="sm" />
                    </Td>
                    <Td>
                      <UnitsProgress
                        fulfilled={request.units_fulfilled}
                        required={request.units_required}
                        size="sm"
                      />
                    </Td>
                    <Td>
                      <RequestStatusBadge
                        status={request.status}
                        isExpired={request.is_expired}
                      />
                    </Td>
                    <Td muted>{request.needed_by_date}</Td>
                    <Td numeric muted>
                      {/* Notified and responded together. Either number alone is
                          uninformative: 40 notified means nothing without knowing how
                          many replied. */}
                      {request.responded_count} of {request.notified_count}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>

            <Pagination
              page={data.page}
              pageSize={data.page_size}
              total={data.total}
              pages={data.pages}
              onPageChange={setPage}
            />
          </>
        )}
      </Card>
    </>
  )
}
