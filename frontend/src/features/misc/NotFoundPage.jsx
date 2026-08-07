import { LinkButton } from '../../components/ui/Button'
import { EmptyState } from '../../components/ui/States'
import { HOME_FOR_ROLE } from '../../auth/guards'
import { useAuth } from '../../auth/AuthProvider'
import styles from './NotFoundPage.module.css'

export function NotFoundPage() {
  const { isAuthenticated, role } = useAuth()
  // Send people somewhere they can actually use, rather than to a root path that would
  // only redirect them again.
  const home = isAuthenticated ? (HOME_FOR_ROLE[role] ?? '/login') : '/login'

  return (
    <div className={styles.wrapper}>
      <EmptyState
        title="Page not found"
        description="The address you followed does not match anything in this application."
        action={
          <LinkButton to={home} variant="primary">
            {isAuthenticated ? 'Back to your home page' : 'Go to sign in'}
          </LinkButton>
        }
      />
    </div>
  )
}
