import { useState } from 'react'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/AppShell'
import { BloodGroupBadge, DonorStatusBadge, EligibilityBadge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Select, TextInput } from '../../components/ui/Field'
import { EmptyState, ErrorState, LoadingState } from '../../components/ui/States'
import { Pagination, Table, Td, Th } from '../../components/ui/Table'
import { Toolbar, ToolbarField } from '../../components/ui/Toolbar'
import { useDonors } from '../../api/hooks'
import { useMeta } from '../../api/meta'
import { useDebounced } from '../../hooks/useDebounced'
import { DonorFormModal } from './DonorFormModal'
import { DonorStatusModal } from './DonorStatusModal'
import styles from './Donors.module.css'

const EMPTY_FILTERS = {
  q: '',
  blood_group: '',
  place: '',
  status: '',
  eligible_only: false,
}

export function DonorsPage() {
  const { data: meta } = useMeta()
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [page, setPage] = useState(1)
  const [registering, setRegistering] = useState(false)
  const [statusTarget, setStatusTarget] = useState(null)

  // The free-text box is debounced; the dropdowns are not. Typing fires a request per
  // keystroke without it, while selecting from a dropdown is a single deliberate act that
  // should take effect immediately.
  const debouncedQuery = useDebounced(filters.q, 300)

  const params = {
    page,
    page_size: 25,
    q: debouncedQuery || undefined,
    blood_group: filters.blood_group || undefined,
    place: filters.place || undefined,
    status: filters.status || undefined,
    eligible_only: filters.eligible_only || undefined,
  }

  const { data, isPending, isError, error, refetch } = useDonors(params)

  function update(name, value) {
    setFilters((current) => ({ ...current, [name]: value }))
    // Any filter change returns to page one. Staying on page four of a result set that
    // now has two pages shows an empty table and looks like a fault.
    setPage(1)
  }

  const hasFilters = Object.entries(filters).some(
    ([key, value]) => value !== EMPTY_FILTERS[key],
  )

  return (
    <>
      <PageHeader
        title="Donor registry"
        description="Everyone registered with the network. Contact details are visible to administrators only."
        actions={
          <Button variant="primary" onClick={() => setRegistering(true)}>
            Register donor
          </Button>
        }
      />

      <Card>
        <Toolbar hasFilters={hasFilters} onReset={() => { setFilters(EMPTY_FILTERS); setPage(1) }}>
          <ToolbarField label="Search" htmlFor="donor-search" grow>
            <TextInput
              id="donor-search"
              type="search"
              placeholder="Name, place, phone, or email"
              value={filters.q}
              onChange={(event) => update('q', event.target.value)}
            />
          </ToolbarField>

          <ToolbarField label="Blood group" htmlFor="donor-group">
            <Select
              id="donor-group"
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

          <ToolbarField label="Place" htmlFor="donor-place">
            <TextInput
              id="donor-place"
              value={filters.place}
              placeholder="Town or city"
              onChange={(event) => update('place', event.target.value)}
            />
          </ToolbarField>

          <ToolbarField label="Availability" htmlFor="donor-status">
            <Select
              id="donor-status"
              value={filters.status}
              onChange={(event) => update('status', event.target.value)}
            >
              <option value="">Any</option>
              {(meta?.donor_statuses ?? []).map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </ToolbarField>

          <ToolbarField label=" " htmlFor="donor-eligible">
            <label className={styles.checkbox} htmlFor="donor-eligible">
              <input
                id="donor-eligible"
                type="checkbox"
                checked={filters.eligible_only}
                onChange={(event) => update('eligible_only', event.target.checked)}
              />
              Can donate today
            </label>
          </ToolbarField>
        </Toolbar>

        {isPending && <LoadingState label="Loading donors" />}
        {isError && <ErrorState error={error} onRetry={refetch} />}

        {data && data.items.length === 0 && (
          <EmptyState
            title={hasFilters ? 'No donors match these filters' : 'No donors registered yet'}
            description={
              hasFilters
                ? 'Try widening the blood group or place, or clear the filters to see everyone.'
                : 'Register the first donor to start building the network.'
            }
            action={
              hasFilters ? (
                <Button onClick={() => { setFilters(EMPTY_FILTERS); setPage(1) }}>
                  Clear filters
                </Button>
              ) : (
                <Button variant="primary" onClick={() => setRegistering(true)}>
                  Register donor
                </Button>
              )
            }
          />
        )}

        {data && data.items.length > 0 && (
          <>
            <Table caption="Registered donors">
              <thead>
                <tr>
                  <Th>Donor</Th>
                  <Th width="72px">Group</Th>
                  <Th>Place</Th>
                  <Th>Contact</Th>
                  <Th>Availability</Th>
                  <Th>Can donate</Th>
                  <Th width="120px">Last gave</Th>
                  <Th width="1%"> </Th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((donor) => (
                  <tr key={donor.id}>
                    <Td>
                      <Link className={styles.name} to={`/donors/${donor.id}`}>
                        {donor.name}
                      </Link>
                      <span className={styles.subtle}>
                        {donor.age} years, {donor.weight_kg} kg
                      </span>
                    </Td>
                    <Td>
                      <BloodGroupBadge group={donor.blood_group} size="sm" />
                    </Td>
                    <Td>{donor.place}</Td>
                    <Td muted>
                      <span className={styles.contact}>{donor.phone}</span>
                    </Td>
                    <Td>
                      <DonorStatusBadge status={donor.status} />
                    </Td>
                    <Td>
                      <EligibilityBadge eligible={donor.is_eligible} />
                      {/* The reason is shown inline rather than hidden behind a tooltip.
                          A coordinator scanning for someone to call needs to know that a
                          donor is two weeks from eligible without hovering each row. */}
                      {!donor.is_eligible && donor.ineligibility_reasons[0] && (
                        <span className={styles.reason}>{donor.ineligibility_reasons[0]}</span>
                      )}
                    </Td>
                    <Td muted>{donor.last_donation_date ?? 'Never'}</Td>
                    <Td>
                      <Button size="sm" onClick={() => setStatusTarget(donor)}>
                        Availability
                      </Button>
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

      <DonorFormModal open={registering} onClose={() => setRegistering(false)} />
      <DonorStatusModal donor={statusTarget} onClose={() => setStatusTarget(null)} />
    </>
  )
}
