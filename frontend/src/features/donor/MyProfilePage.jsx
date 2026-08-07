import { useEffect, useState } from 'react'

import { PageHeader } from '../../components/layout/AppShell'
import { BloodGroupBadge, DonorStatusBadge, EligibilityBadge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card, CardFooter, CardHeader, DataItem, DataList } from '../../components/ui/Card'
import { Textarea } from '../../components/ui/Field'
import { ErrorState, FormAlert, LoadingState } from '../../components/ui/States'
import { useMyDonorRecord, useSetMyStatus } from '../../api/hooks'
import { useMeta } from '../../api/meta'
import styles from './Donor.module.css'

/**
 * A donor's own record, and the availability control.
 *
 * Letting donors maintain their own availability is most of the reason donors have
 * accounts at all. The person who knows they are travelling next month is the donor, not
 * the administrator who would otherwise have to be told.
 */
export function MyProfilePage() {
  const { data: donor, isPending, isError, error, refetch } = useMyDonorRecord()
  const { data: meta } = useMeta()
  const setStatus = useSetMyStatus()

  const [status, setStatusValue] = useState('available')
  const [note, setNote] = useState('')
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState(null)

  useEffect(() => {
    if (donor) {
      setStatusValue(donor.status)
      setNote(donor.status_note ?? '')
    }
  }, [donor])

  if (isPending) return <LoadingState label="Loading your record" />
  if (isError) return <ErrorState error={error} onRetry={refetch} />

  const unavailable = status !== 'available'
  const dirty = status !== donor.status || (unavailable && note !== (donor.status_note ?? ''))

  async function handleSubmit(event) {
    event.preventDefault()
    setSaveError(null)
    setSaved(false)
    try {
      await setStatus.mutateAsync({ status, note: unavailable ? note : undefined })
      setSaved(true)
    } catch (err) {
      setSaveError(err.message)
    }
  }

  return (
    <>
      <PageHeader
        title="My donor record"
        meta={
          <>
            <BloodGroupBadge group={donor.blood_group} />
            <DonorStatusBadge status={donor.status} />
            <EligibilityBadge eligible={donor.is_eligible} />
          </>
        }
      />

      <div className={styles.profileGrid}>
        <Card>
          <CardHeader
            title="Availability"
            description="The network only contacts donors who are marked available. Keeping this accurate saves an appeal being wasted on someone who cannot come."
          />

          <form onSubmit={handleSubmit}>
            <FormAlert>{saveError}</FormAlert>
            {saved && !dirty && <FormAlert tone="positive">Availability updated.</FormAlert>}

            <fieldset className={styles.statusOptions}>
              <legend className="sr-only">Set your availability</legend>
              {(meta?.donor_statuses ?? []).map((option) => (
                <label key={option.value} className={styles.statusOption}>
                  <input
                    type="radio"
                    name="status"
                    value={option.value}
                    checked={status === option.value}
                    onChange={(event) => {
                      setStatusValue(event.target.value)
                      setSaved(false)
                    }}
                  />
                  <span className={styles.statusText}>
                    <span className={styles.statusTitle}>{option.label}</span>
                    <span className={styles.statusHint}>{HINTS[option.value]}</span>
                  </span>
                </label>
              ))}
            </fieldset>

            {unavailable && (
              <div style={{ marginTop: 'var(--space-4)' }}>
                <label
                  htmlFor="status-note"
                  style={{
                    display: 'block',
                    fontSize: 'var(--text-sm)',
                    fontWeight: 'var(--weight-medium)',
                    color: 'var(--text-secondary)',
                    marginBottom: 'var(--space-2)',
                  }}
                >
                  Anything the network should know
                </label>
                <Textarea
                  id="status-note"
                  rows={2}
                  maxLength={255}
                  placeholder="For example, when you expect to be back."
                  value={note}
                  onChange={(event) => {
                    setNote(event.target.value)
                    setSaved(false)
                  }}
                />
              </div>
            )}

            <CardFooter>
              <Button
                type="submit"
                variant="primary"
                loading={setStatus.isPending}
                disabled={!dirty}
              >
                Save availability
              </Button>
            </CardFooter>
          </form>
        </Card>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>
          <Card>
            <CardHeader title="Can you give today?" />
            {donor.is_eligible ? (
              <p className={styles.eligibleNote}>
                Yes. You will be included in appeals for {donor.blood_group} blood.
              </p>
            ) : (
              <ul className={styles.reasonList}>
                {donor.ineligibility_reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            )}
          </Card>

          <Card>
            <CardHeader title="Your details" />
            <DataList columns={1}>
              <DataItem label="Name">{donor.name}</DataItem>
              <DataItem label="Blood group">{donor.blood_group}</DataItem>
              <DataItem label="Phone">{donor.phone}</DataItem>
              <DataItem label="Email">{donor.email}</DataItem>
              <DataItem label="Place">{donor.place}</DataItem>
              <DataItem label="Last donation">
                {donor.last_donation_date ?? 'Never donated'}
              </DataItem>
              {donor.next_eligible_date && (
                <DataItem label="Eligible again on">{donor.next_eligible_date}</DataItem>
              )}
            </DataList>
          </Card>
        </div>
      </div>
    </>
  )
}

const HINTS = {
  available: 'You are willing to be contacted when your blood group is needed.',
  unavailable_moved: 'You have moved away from this area.',
  unavailable_traveling: 'You are away and cannot attend a hospital.',
  unavailable_medical: 'A medical reason means you should not give at the moment.',
}
