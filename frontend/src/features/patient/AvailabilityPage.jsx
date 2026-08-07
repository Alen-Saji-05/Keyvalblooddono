import { useState } from 'react'

import { PageHeader } from '../../components/layout/AppShell'
import { BloodGroupBadge } from '../../components/ui/Badge'
import { Card, CardHeader } from '../../components/ui/Card'
import { TextInput } from '../../components/ui/Field'
import { ErrorState, LoadingState } from '../../components/ui/States'
import { Toolbar, ToolbarField } from '../../components/ui/Toolbar'
import { useAvailability } from '../../api/hooks'
import { useDebounced } from '../../hooks/useDebounced'
import styles from './Patient.module.css'

/**
 * Aggregate donor supply, with no identities.
 *
 * This is what a patient sees in place of the donor directory. Because broadcasting is an
 * administrator action, a patient has no workflow reason to know who the donors are - but
 * they do need to know whether filing a request has any prospect of being met, and this
 * answers that without naming anybody.
 */
export function AvailabilityPage() {
  const [place, setPlace] = useState('')
  const debouncedPlace = useDebounced(place, 300)
  const { data, isPending, isError, error, refetch } = useAvailability(
    debouncedPlace || undefined,
  )

  return (
    <>
      <PageHeader
        title="Donor availability"
        description="How many donors of each blood group can give right now. Individual donors are not identified."
      />

      <Card>
        <Toolbar hasFilters={Boolean(place)} onReset={() => setPlace('')}>
          <ToolbarField label="Narrow to a place" htmlFor="avail-place" grow>
            <TextInput
              id="avail-place"
              placeholder="Town or city, or leave blank for everywhere"
              value={place}
              onChange={(event) => setPlace(event.target.value)}
            />
          </ToolbarField>
        </Toolbar>

        {isPending && <LoadingState label="Counting donors" />}
        {isError && <ErrorState error={error} onRetry={refetch} />}

        {data && (
          <>
            <CardHeader
              title={debouncedPlace ? `Donors near ${debouncedPlace}` : 'Donors across the network'}
              description="Eligible means available, within the age and weight criteria, and outside the interval since their last donation."
              level={3}
            />
            <div className={styles.availabilityGrid}>
              {/* Every group is shown, including those at zero. An absent card would read
                  as missing data rather than as an absence of donors, and zero is the most
                  important number on this screen. */}
              {data.items.map((row) => (
                <div key={row.blood_group} className={styles.groupCard}>
                  <div className={styles.groupHeader}>
                    <BloodGroupBadge group={row.blood_group} />
                  </div>
                  <p
                    className={[
                      styles.groupCount,
                      row.eligible_donors === 0 ? styles.groupZero : '',
                    ]
                      .filter(Boolean)
                      .join(' ')}
                  >
                    {row.eligible_donors}
                  </p>
                  <p className={styles.groupLabel}>
                    can give now, of {row.total_donors} registered
                  </p>
                </div>
              ))}
            </div>
          </>
        )}
      </Card>
    </>
  )
}
