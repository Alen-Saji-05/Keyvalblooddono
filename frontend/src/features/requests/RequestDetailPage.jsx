import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/AppShell'
import { Badge, BloodGroupBadge, RequestStatusBadge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card, CardHeader, DataItem, DataList } from '../../components/ui/Card'
import { Stat, StatGrid, UnitsProgress } from '../../components/ui/Stat'
import { EmptyState, ErrorState, LoadingState } from '../../components/ui/States'
import { useRequest } from '../../api/hooks'
import { useAuth } from '../../auth/AuthProvider'
import { BroadcastModal } from './BroadcastModal'
import { RecordDonationModal } from './RecordDonationModal'
import styles from './Requests.module.css'

export function RequestDetailPage() {
  const { id } = useParams()
  const { role } = useAuth()
  const { data: request, isPending, isError, error, refetch } = useRequest(id)
  const [broadcasting, setBroadcasting] = useState(false)
  const [recording, setRecording] = useState(false)

  const isAdmin = role === 'admin'
  const backTo = isAdmin ? '/requests' : '/my-requests'

  if (isPending) return <LoadingState label="Loading request" />
  if (isError) return <ErrorState error={error} onRetry={refetch} />

  const fulfilled = request.status === 'fulfilled'

  return (
    <>
      <Link to={backTo} className={styles.backLink}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M15 5l-7 7 7 7" />
        </svg>
        {isAdmin ? 'Blood requests' : 'My requests'}
      </Link>

      <PageHeader
        title={request.patient_name}
        description={`${request.hospital}, ${request.place}`}
        meta={
          <>
            <BloodGroupBadge group={request.blood_group} />
            <RequestStatusBadge status={request.status} isExpired={request.is_expired} />
            <Badge tone="neutral">Needed by {request.needed_by_date}</Badge>
          </>
        }
        actions={
          isAdmin ? (
            <>
              <Button onClick={() => setBroadcasting(true)} disabled={fulfilled}>
                Broadcast
              </Button>
              <Button variant="primary" onClick={() => setRecording(true)} disabled={fulfilled}>
                Record donation
              </Button>
            </>
          ) : null
        }
      />

      <div className={styles.detailGrid}>
        <div className={styles.stack}>
          <Card>
            <CardHeader
              title="Fulfilment"
              description={
                fulfilled
                  ? 'This request has received everything it asked for.'
                  : 'A request stays open until the units received meet the units required, however many donors that takes.'
              }
            />
            <div className={styles.progressPanel}>
              <UnitsProgress
                fulfilled={request.units_fulfilled}
                required={request.units_required}
              />
            </div>

            <StatGrid columns={3}>
              <Stat label="Donors who gave" value={request.donation_count} />
              <Stat label="Donors notified" value={request.notified_count} />
              <Stat
                label="Donors who responded"
                value={request.responded_count}
                caption={
                  request.notified_count
                    ? `${Math.round((request.responded_count / request.notified_count) * 100)} per cent of those notified`
                    : 'Not broadcast yet'
                }
              />
            </StatGrid>
          </Card>

          <Card>
            <CardHeader
              title="Donations received"
              description={
                isAdmin
                  ? 'Every donor who has given towards this request.'
                  : 'Units received so far. Donor identities are not shared with patients.'
              }
            />

            {request.donations.length === 0 ? (
              <EmptyState
                title="No units yet"
                description={
                  isAdmin
                    ? 'Broadcast the request to reach eligible donors, then record each donation as it arrives.'
                    : 'The network is working on this request. Units will appear here as they arrive.'
                }
                action={
                  isAdmin && !fulfilled ? (
                    <Button variant="primary" onClick={() => setBroadcasting(true)}>
                      Broadcast to eligible donors
                    </Button>
                  ) : null
                }
              />
            ) : (
              <ul className={styles.timeline}>
                {request.donations.map((donation) => (
                  <li key={donation.id} className={styles.timelineItem}>
                    <span className={styles.timelineUnits}>{donation.units_given}</span>
                    <div className={styles.timelineBody}>
                      <p className={styles.timelineTitle}>
                        {/* Null for a patient by design: the server withholds the
                            identity rather than the client hiding it. */}
                        {donation.donor_name ?? 'A donor'}
                        {donation.units_given === 1 ? ' gave 1 unit' : ` gave ${donation.units_given} units`}
                      </p>
                      <p className={styles.timelineMeta}>{donation.donation_date}</p>
                      {donation.notes && <p className={styles.timelineMeta}>{donation.notes}</p>}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {isAdmin && request.notifications && request.notifications.length > 0 && (
            <Card>
              <CardHeader
                title="Outreach"
                description="Donors notified about this request, and whether they answered."
              />
              {request.notifications.map((notification) => (
                <div key={notification.id} className={styles.notifyRow}>
                  <span>
                    Donor {notification.donor_id}
                    <span className={styles.subtle}>
                      Sent {notification.sent_at.slice(0, 16).replace('T', ' ')}
                      {notification.delivery_error ? ` - delivery failed` : ''}
                    </span>
                  </span>
                  {notification.responded ? (
                    <Badge tone="positive">Responded</Badge>
                  ) : (
                    <Badge tone="neutral">No reply yet</Badge>
                  )}
                </div>
              ))}
            </Card>
          )}
        </div>

        <Card>
          <CardHeader title="Request details" />
          <DataList columns={1}>
            <DataItem label="Patient">{request.patient_name}</DataItem>
            <DataItem label="Blood group">{request.blood_group}</DataItem>
            <DataItem label="Hospital">{request.hospital}</DataItem>
            <DataItem label="Place">{request.place}</DataItem>
            <DataItem label="Contact number">{request.contact_phone}</DataItem>
            <DataItem label="Units required">{request.units_required}</DataItem>
            <DataItem label="Needed by">{request.needed_by_date}</DataItem>
            <DataItem label="Filed">{request.created_at.slice(0, 10)}</DataItem>
            {request.notes && <DataItem label="Notes">{request.notes}</DataItem>}
          </DataList>
        </Card>
      </div>

      {broadcasting && (
        <BroadcastModal request={request} onClose={() => setBroadcasting(false)} />
      )}
      {recording && (
        <RecordDonationModal request={request} onClose={() => setRecording(false)} />
      )}
    </>
  )
}
