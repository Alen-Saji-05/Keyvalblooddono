import { useQuery } from '@tanstack/react-query'

import { api } from './client'

/**
 * Enumerations, labels, and eligibility thresholds, fetched from the server.
 *
 * Duplicating the blood group list and the status labels in the frontend would guarantee
 * they eventually disagree with the database: someone adds a status server side and the
 * dropdown silently omits it. Fetching them means the vocabulary has one source.
 *
 * Cached indefinitely. This data changes only when the application is redeployed, so
 * refetching it on every window focus would be pure noise.
 */
export function useMeta() {
  return useQuery({
    queryKey: ['meta'],
    queryFn: () => api.get('/meta'),
    staleTime: Infinity,
    gcTime: Infinity,
  })
}

/** Turn a `{value, label}` list into a lookup, for rendering a stored value. */
export function labelMap(options) {
  return Object.fromEntries((options ?? []).map((option) => [option.value, option.label]))
}
