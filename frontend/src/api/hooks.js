import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, queryString } from './client'

/*
 * Every server interaction in one file.
 *
 * Query keys are structured so that invalidating a prefix invalidates everything below
 * it. Recording a donation, for example, has to invalidate the request detail, the
 * request list, the donor who gave, and the summary - because it changes all four. Naming
 * the keys consistently is what makes that a three-line mutation rather than a list of
 * individually remembered cache entries that someone eventually forgets to update.
 */

export const keys = {
  donors: (params) => ['donors', params],
  donor: (id) => ['donor', id],
  requests: (params) => ['requests', params],
  request: (id) => ['request', id],
  summary: () => ['summary'],
  availability: (place) => ['availability', place ?? ''],
  users: () => ['users'],
  inbox: (params) => ['inbox', params],
  myDonor: () => ['my-donor'],
  myDonations: () => ['my-donations'],
}

/** Invalidate everything a write to a request could have changed. */
function invalidateRequestGraph(queryClient, requestId) {
  queryClient.invalidateQueries({ queryKey: ['requests'] })
  queryClient.invalidateQueries({ queryKey: ['summary'] })
  queryClient.invalidateQueries({ queryKey: ['inbox'] })
  if (requestId) queryClient.invalidateQueries({ queryKey: ['request', requestId] })
}

// --- Donors -----------------------------------------------------------------

export function useDonors(params) {
  return useQuery({
    queryKey: keys.donors(params),
    queryFn: () => api.get(`/donors${queryString(params)}`),
    // Keeps the previous page on screen while the next one loads, so paging through the
    // directory does not blank the table and jump the scroll position on every click.
    placeholderData: (previous) => previous,
  })
}

export function useDonor(id) {
  return useQuery({
    queryKey: keys.donor(id),
    queryFn: () => api.get(`/donors/${id}`),
    enabled: Boolean(id),
  })
}

export function useCreateDonor() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload) => api.post('/donors', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['donors'] })
      queryClient.invalidateQueries({ queryKey: ['summary'] })
      queryClient.invalidateQueries({ queryKey: ['availability'] })
    },
  })
}

export function useSetDonorStatus() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, status, note }) =>
      api.patch(`/donors/${id}/status`, { status, ...(note ? { note } : {}) }),
    onSuccess: (donor) => {
      queryClient.setQueryData(keys.donor(donor.id), donor)
      queryClient.invalidateQueries({ queryKey: ['donors'] })
      queryClient.invalidateQueries({ queryKey: ['summary'] })
      queryClient.invalidateQueries({ queryKey: ['availability'] })
      queryClient.invalidateQueries({ queryKey: ['my-donor'] })
    },
  })
}

export function useUpdateDonor() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...payload }) => api.patch(`/donors/${id}`, payload),
    onSuccess: (donor) => {
      queryClient.setQueryData(keys.donor(donor.id), donor)
      queryClient.invalidateQueries({ queryKey: ['donors'] })
      queryClient.invalidateQueries({ queryKey: ['my-donor'] })
    },
  })
}

// --- Requests ---------------------------------------------------------------

export function useRequests(params) {
  return useQuery({
    queryKey: keys.requests(params),
    queryFn: () => api.get(`/requests${queryString(params)}`),
    placeholderData: (previous) => previous,
  })
}

export function useRequest(id) {
  return useQuery({
    queryKey: keys.request(id),
    queryFn: () => api.get(`/requests/${id}`),
    enabled: Boolean(id),
  })
}

export function useCreateRequest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload) => api.post('/requests', payload),
    onSuccess: () => invalidateRequestGraph(queryClient),
  })
}

export function useBroadcast() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...options }) => api.post(`/requests/${id}/broadcast`, options),
    onSuccess: (_result, variables) => invalidateRequestGraph(queryClient, variables.id),
  })
}

export function useRecordDonation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...payload }) => api.post(`/requests/${id}/donations`, payload),
    onSuccess: (updated, variables) => {
      queryClient.setQueryData(keys.request(variables.id), updated)
      invalidateRequestGraph(queryClient, variables.id)
      // The donor who gave is now inside their cooldown, so their eligibility has
      // changed everywhere it is shown.
      queryClient.invalidateQueries({ queryKey: ['donors'] })
      queryClient.invalidateQueries({ queryKey: ['donor', variables.donor_id] })
      queryClient.invalidateQueries({ queryKey: ['availability'] })
    },
  })
}

// --- Notifications ----------------------------------------------------------

export function useInbox(params) {
  return useQuery({
    queryKey: keys.inbox(params),
    queryFn: () => api.get(`/me/notifications${queryString(params)}`),
    placeholderData: (previous) => previous,
  })
}

export function useRespond() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ notificationId, willing = true }) =>
      api.post(`/notifications/${notificationId}/respond`, { willing }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inbox'] })
      queryClient.invalidateQueries({ queryKey: ['requests'] })
      queryClient.invalidateQueries({ queryKey: ['summary'] })
    },
  })
}

// --- Donor self-service -----------------------------------------------------

export function useMyDonorRecord() {
  return useQuery({ queryKey: keys.myDonor(), queryFn: () => api.get('/me/donor') })
}

export function useSetMyStatus() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ status, note }) =>
      api.patch('/me/donor/status', { status, ...(note ? { note } : {}) }),
    onSuccess: (donor) => {
      queryClient.setQueryData(keys.myDonor(), donor)
      queryClient.invalidateQueries({ queryKey: ['availability'] })
    },
  })
}

export function useMyDonations() {
  return useQuery({ queryKey: keys.myDonations(), queryFn: () => api.get('/me/donations') })
}

// --- Summary and availability ------------------------------------------------

export function useSummary() {
  return useQuery({ queryKey: keys.summary(), queryFn: () => api.get('/summary') })
}

export function useAvailability(place) {
  return useQuery({
    queryKey: keys.availability(place),
    queryFn: () => api.get(`/availability${queryString({ place })}`),
  })
}

// --- Accounts ---------------------------------------------------------------

export function useUsers() {
  return useQuery({ queryKey: keys.users(), queryFn: () => api.get('/users') })
}

export function useCreateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload) => api.post('/users', payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useUpdateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...payload }) => api.patch(`/users/${id}`, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  })
}

/** Pull per-field messages out of an ApiError for attaching to inputs. */
export function fieldErrorsFrom(error) {
  const fields = error?.fieldErrors ?? {}
  return Object.fromEntries(Object.entries(fields).map(([key, messages]) => [key, messages[0]]))
}
