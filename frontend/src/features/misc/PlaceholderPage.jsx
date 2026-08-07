import { PageHeader } from '../../components/layout/AppShell'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/States'

/**
 * A route that exists but whose screen is built in a later phase.
 *
 * Present so that every navigation destination is reachable now and the shell, the role
 * guards, and the redirects can be exercised end to end. It states plainly that the
 * screen is unbuilt rather than showing an empty table, which would be indistinguishable
 * from a screen that is broken.
 */
export function PlaceholderPage({ title, phase }) {
  return (
    <>
      <PageHeader title={title} />
      <Card padded={false}>
        <EmptyState
          title="This screen is not built yet"
          description={`Reachable, authorised, and reserved. The interface for this route is scheduled for ${phase}.`}
        />
      </Card>
    </>
  )
}
