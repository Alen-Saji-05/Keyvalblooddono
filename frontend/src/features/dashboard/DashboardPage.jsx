import { PageHeader } from '../../components/layout/AppShell'
import { BloodGroupBadge } from '../../components/ui/Badge'
import { LinkButton } from '../../components/ui/Button'
import { Card, CardHeader } from '../../components/ui/Card'
import { Stat, StatGrid } from '../../components/ui/Stat'
import { ErrorState, LoadingState } from '../../components/ui/States'
import { Table, Td, Th } from '../../components/ui/Table'
import { useSummary } from '../../api/hooks'
import styles from './Dashboard.module.css'

/**
 * The network summary.
 *
 * The four figures the brief asks for, each presented with the context needed to read it.
 * A bare number on a dashboard invites a wrong conclusion: "1 eligible donor" reads as a
 * dying network unless it also says that most donors are inside their cooldown.
 */
export function DashboardPage() {
  const { data, isPending, isError, error, refetch } = useSummary()

  if (isPending) return <LoadingState label="Calculating network summary" />
  if (isError) return <ErrorState error={error} onRetry={refetch} />

  const responseRate = data.donor_response_rate
  const inCooldown = data.donors_available - data.donors_eligible_now

  return (
    <>
      <PageHeader
        title="Network summary"
        description="How the network is performing across every request, donor, and broadcast."
      />

      <StatGrid columns={4}>
        <Stat
          label="Donations arranged"
          value={data.total_donations}
          tone="accent"
          caption={`${data.total_units_donated} units in total`}
        />
        <Stat
          label="Requests fulfilled"
          value={data.requests_fulfilled}
          tone="positive"
          caption={`of ${data.requests_total} filed`}
        />
        <Stat
          label="Still needing blood"
          value={data.requests_unfulfilled}
          tone={data.requests_unfulfilled > 0 ? 'caution' : 'neutral'}
          caption={`${data.requests_open} not yet started, ${data.requests_partially_fulfilled} part met`}
        />
        <Stat
          label="Donor response rate"
          value={`${responseRate}%`}
          caption={`${data.notifications_responded} of ${data.notifications_sent} notified donors answered`}
        />
      </StatGrid>

      <div className={styles.grid}>
        <Card>
          <CardHeader
            title="Donor pool"
            description="Registered, available, and able to give right now are three different numbers."
          />

          <div className={styles.funnel}>
            <FunnelRow
              label="Registered donors"
              value={data.donors_registered}
              total={data.donors_registered}
              note="Everyone on the register"
            />
            <FunnelRow
              label="Marked available"
              value={data.donors_available}
              total={data.donors_registered}
              note={`${data.donors_registered - data.donors_available} have moved away, are travelling, or are medically unable`}
            />
            <FunnelRow
              label="Can give today"
              value={data.donors_eligible_now}
              total={data.donors_registered}
              note={
                inCooldown > 0
                  ? `${inCooldown} more are available but inside the interval since their last donation, or outside the age or weight criteria`
                  : 'Every available donor also meets the medical criteria'
              }
              emphasis
            />
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Demand against supply"
            description="Outstanding units needed, next to the donors who could actually give them."
            actions={
              <LinkButton to="/requests" size="sm">
                View requests
              </LinkButton>
            }
          />

          <Table caption="Outstanding demand by blood group">
            <thead>
              <tr>
                <Th width="80px">Group</Th>
                <Th numeric>Units needed</Th>
                <Th numeric>Donors able to give</Th>
                <Th width="120px">Position</Th>
              </tr>
            </thead>
            <tbody>
              {data.demand_by_blood_group.map((row) => {
                // Short only counts as short when blood is actually being asked for. A
                // group with no eligible donors and no outstanding requests is not a
                // problem, and flagging it would train people to ignore the flag.
                const short = row.open_units_needed > row.eligible_donors
                const noDemand = row.open_units_needed === 0
                return (
                  <tr key={row.blood_group}>
                    <Td>
                      <BloodGroupBadge group={row.blood_group} size="sm" />
                    </Td>
                    <Td numeric>{row.open_units_needed}</Td>
                    <Td numeric>{row.eligible_donors}</Td>
                    <Td>
                      {noDemand ? (
                        <span className={styles.neutralNote}>No demand</span>
                      ) : short ? (
                        <span className={styles.shortNote}>Short</span>
                      ) : (
                        <span className={styles.coveredNote}>Covered</span>
                      )}
                    </Td>
                  </tr>
                )
              })}
            </tbody>
          </Table>
        </Card>
      </div>
    </>
  )
}

function FunnelRow({ label, value, total, note, emphasis }) {
  const percent = total > 0 ? Math.round((value / total) * 100) : 0
  return (
    <div className={styles.funnelRow}>
      <div className={styles.funnelHeader}>
        <span className={styles.funnelLabel}>{label}</span>
        <span className={[styles.funnelValue, emphasis ? styles.funnelEmphasis : ''].filter(Boolean).join(' ')}>
          {value}
        </span>
      </div>
      <div className={styles.funnelTrack}>
        <div
          className={[styles.funnelFill, emphasis ? styles.funnelFillEmphasis : '']
            .filter(Boolean)
            .join(' ')}
          style={{ transform: `scaleX(${percent / 100})` }}
        />
      </div>
      <p className={styles.funnelNote}>{note}</p>
    </div>
  )
}
