import { PageHeader } from '../../components/layout/AppShell'
import { Card } from '../../components/ui/Card'
import { Stat, StatGrid } from '../../components/ui/Stat'
import { EmptyState, ErrorState, LoadingState } from '../../components/ui/States'
import { Table, Td, Th } from '../../components/ui/Table'
import { useMyDonations, useMyDonorRecord } from '../../api/hooks'

export function MyDonationsPage() {
  const { data, isPending, isError, error, refetch } = useMyDonations()
  const { data: donor } = useMyDonorRecord()

  const donations = data?.items ?? []
  const totalUnits = donations.reduce((sum, donation) => sum + donation.units_given, 0)

  return (
    <>
      <PageHeader
        title="Donation history"
        description="Every donation the network has recorded against your name."
      />

      {isPending && <LoadingState label="Loading your history" />}
      {isError && <ErrorState error={error} onRetry={refetch} />}

      {data && (
        <>
          <StatGrid columns={3}>
            <Stat label="Donations given" value={donations.length} />
            <Stat
              label="Units contributed"
              value={totalUnits}
              tone="accent"
              caption="Roughly one unit helps one patient"
            />
            <Stat
              label="Eligible again"
              value={donor?.next_eligible_date ?? (donor?.is_eligible ? 'Now' : '-')}
              caption={
                donor?.is_eligible
                  ? 'You can give today'
                  : 'The interval between donations protects your own health'
              }
            />
          </StatGrid>

          <div style={{ marginTop: 'var(--space-5)' }}>
            <Card padded={donations.length === 0}>
              {donations.length === 0 ? (
                <EmptyState
                  title="No donations recorded yet"
                  description="When you give blood against an appeal, an administrator records it and it appears here."
                />
              ) : (
                <div style={{ padding: 'var(--space-5)' }}>
                  <Table caption="Your donations">
                    <thead>
                      <tr>
                        <Th width="140px">Date</Th>
                        <Th numeric width="90px">Units</Th>
                        <Th>Notes</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {donations.map((donation) => (
                        <tr key={donation.id}>
                          <Td>{donation.donation_date}</Td>
                          <Td numeric>{donation.units_given}</Td>
                          <Td muted>{donation.notes ?? '-'}</Td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </>
  )
}
