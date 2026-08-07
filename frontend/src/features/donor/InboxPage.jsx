import { useState } from 'react'

import { PageHeader } from '../../components/layout/AppShell'
import { Badge, BloodGroupBadge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card, CardHeader } from '../../components/ui/Card'
import { UnitsProgress } from '../../components/ui/Stat'
import { EmptyState, ErrorState, LoadingState } from '../../components/ui/States'
import { Pagination } from '../../components/ui/Table'
import { useInbox, useMyDonorRecord, useRespond } from '../../api/hooks'
import styles from './Donor.module.css'

/**
 * A donor's appeals.
 *
 * Presented as cards rather than a table. Each one is a request for help from a person in
 * a hospital, and it carries a hospital, a contact number, and how much blood is still
 * needed. A table row would compress that into columns and lose the point of it.
 */
export function InboxPage() {
  const [page, setPage] = useState(1)
  const { data, isPending, isError, error, refetch } = useInbox({ page, page_size: 10 })
  const { data: donor } = useMyDonorRecord()
  const respond = useRespond()

  return (
    <>
      <PageHeader
        title="Appeals for blood"
        description="Requests you have been notified about. Answering tells the network to expect you."
      />

      {donor && !donor.is_eligible && (
        <div className={styles.noticeCaution}>
          <strong>You cannot give right now.</strong>
          <span>
            {donor.ineligibility_reasons.join(' ')} You will stop receiving appeals until
            this changes.
          </span>
        </div>
      )}

      {isPending && <LoadingState label="Loading your appeals" />}
      {isError && <ErrorState error={error} onRetry={refetch} />}

      {data && data.items.length === 0 && (
        <Card padded={false}>
          <EmptyState
            title="No appeals yet"
            description="When a patient needs your blood group nearby, the appeal will appear here. Keep your availability up to date so the network knows when to ask."
          />
        </Card>
      )}

      {data && data.items.length > 0 && (
        <>
          <div className={styles.inboxList}>
            {data.items.map((item) => {
              const met = item.request_status === 'fulfilled'
              return (
                <Card key={item.id} className={item.responded ? styles.answered : undefined}>
                  <CardHeader
                    title={`${item.blood_group} needed at ${item.hospital}`}
                    description={`${item.place}. Needed by ${item.needed_by_date}.`}
                    level={2}
                    actions={
                      <div className={styles.inboxBadges}>
                        <BloodGroupBadge group={item.blood_group} />
                        {met ? (
                          <Badge tone="positive">Request met</Badge>
                        ) : item.responded ? (
                          <Badge tone="positive">You answered</Badge>
                        ) : (
                          <Badge tone="critical">Needs an answer</Badge>
                        )}
                      </div>
                    }
                  />

                  <UnitsProgress
                    fulfilled={item.units_fulfilled}
                    required={item.units_required}
                  />

                  <div className={styles.inboxFooter}>
                    <div className={styles.contact}>
                      <span className={styles.contactLabel}>Contact</span>
                      {/* A real tel: link. On a phone this is the whole interaction, and
                          making somebody copy a number by hand in an emergency is a
                          failure of the interface. */}
                      <a className={styles.contactValue} href={`tel:${item.contact_phone}`}>
                        {item.contact_phone}
                      </a>
                    </div>

                    {!item.responded && !met && (
                      <Button
                        variant="primary"
                        loading={respond.isPending && respond.variables?.notificationId === item.id}
                        onClick={() => respond.mutate({ notificationId: item.id })}
                      >
                        I can help
                      </Button>
                    )}
                  </div>
                </Card>
              )
            })}
          </div>

          <Pagination
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            pages={data.pages}
            onPageChange={setPage}
          />
        </>
      )}
    </>
  )
}
