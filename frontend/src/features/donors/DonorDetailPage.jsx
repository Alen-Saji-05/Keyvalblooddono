import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/AppShell'
import { BloodGroupBadge, DonorStatusBadge, EligibilityBadge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card, CardHeader, DataItem, DataList } from '../../components/ui/Card'
import { ErrorState, LoadingState } from '../../components/ui/States'
import { useDonor } from '../../api/hooks'
import { DonorStatusModal } from './DonorStatusModal'
import styles from './Donors.module.css'

export function DonorDetailPage() {
  const { id } = useParams()
  const { data: donor, isPending, isError, error, refetch } = useDonor(id)
  const [editingStatus, setEditingStatus] = useState(false)

  if (isPending) return <LoadingState label="Loading donor" />
  if (isError) return <ErrorState error={error} onRetry={refetch} />

  return (
    <>
      <Link to="/donors" className={styles.backLink}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M15 5l-7 7 7 7" />
        </svg>
        Donor registry
      </Link>

      <PageHeader
        title={donor.name}
        meta={
          <>
            <BloodGroupBadge group={donor.blood_group} />
            <DonorStatusBadge status={donor.status} />
            <EligibilityBadge eligible={donor.is_eligible} />
          </>
        }
        actions={
          <Button variant="primary" onClick={() => setEditingStatus(true)}>
            Change availability
          </Button>
        }
      />

      <div className={styles.detailGrid}>
        <Card>
          <CardHeader title="Donor details" />
          <DataList columns={2}>
            <DataItem label="Phone">{donor.phone}</DataItem>
            <DataItem label="Email">{donor.email}</DataItem>
            <DataItem label="Place">{donor.place}</DataItem>
            <DataItem label="Age">{donor.age} years</DataItem>
            <DataItem label="Weight">{donor.weight_kg} kg</DataItem>
            <DataItem label="Date of birth">{donor.date_of_birth}</DataItem>
            <DataItem label="Last donation">{donor.last_donation_date ?? 'Never donated'}</DataItem>
            <DataItem label="Registered">{donor.created_at.slice(0, 10)}</DataItem>
            {donor.status_note && (
              <DataItem label="Availability note" wide>
                {donor.status_note}
              </DataItem>
            )}
          </DataList>
        </Card>

        <Card>
          <CardHeader
            title="Can this donor give today?"
            description={
              donor.is_eligible
                ? 'Yes. This donor is included in broadcasts for their blood group.'
                : 'No. This donor is excluded from broadcasts until every point below is resolved.'
            }
          />

          {donor.is_eligible ? (
            <p className={styles.reasonList}>
              Available, within the age and weight criteria, and outside the interval since
              their last donation.
            </p>
          ) : (
            <ul className={styles.reasonList}>
              {donor.ineligibility_reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <DonorStatusModal
        donor={editingStatus ? donor : null}
        onClose={() => setEditingStatus(false)}
      />
    </>
  )
}
