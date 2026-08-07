import {
  getAccessToken,
  notifyUnauthenticated,
  setAccessToken,
} from './tokenStore'

/**
 * An error carrying everything the API's error envelope provides.
 *
 * The backend returns one shape for every failure -
 * `{ error: { code, message, details } }` - so the client parses it once here and every
 * caller gets a typed object instead of re-reading a response body.
 */
export class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details || {}
  }

  /** Per-field validation messages, keyed by field name, for attaching to form inputs. */
  get fieldErrors() {
    return this.details.fields || {}
  }

  get isValidation() {
    return this.status === 422
  }

  get isForbidden() {
    return this.status === 403
  }

  get isNotFound() {
    return this.status === 404
  }
}

const BASE = '/api'

/*
 * A single in-flight refresh, shared by every request that gets a 401.
 *
 * Without this, a dashboard that fires five queries at once on a stale token sends five
 * refresh requests. Because refresh tokens rotate and the presented one is blocklisted,
 * the first would succeed and the other four would arrive with a token the server has
 * just revoked - logging the user out purely because their dashboard was busy.
 */
let refreshPromise = null

/**
 * Exchange the refresh cookie for a new access token, at most once at a time.
 *
 * Exported because session restore on page load must go through this same single flight,
 * not issue its own call. Refresh tokens rotate: the first request to arrive revokes the
 * token the others are carrying, so two independent refreshes mean the second is rejected
 * and the user is signed out for no reason. React's StrictMode double-invokes effects in
 * development and surfaced exactly this, but two browser tabs would do the same in
 * production.
 *
 * Resolves to the response body, or null if the session could not be recovered.
 */
export async function refreshSession() {
  if (!refreshPromise) {
    refreshPromise = fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    })
      .then(async (response) => {
        if (!response.ok) return null
        const body = await response.json()
        setAccessToken(body.access_token)
        return body
      })
      .catch(() => null)
      .finally(() => {
        // Cleared once settled so the next expiry starts a fresh attempt rather than
        // reusing a resolved promise forever.
        refreshPromise = null
      })
  }
  return refreshPromise
}

async function parseError(response) {
  let payload = null
  try {
    payload = await response.json()
  } catch {
    payload = null
  }
  const envelope = payload?.error || {}
  return new ApiError(
    response.status,
    envelope.code || 'error',
    envelope.message || `Request failed with status ${response.status}.`,
    envelope.details,
  )
}

/**
 * Perform an API call, refreshing the access token once if it has expired.
 *
 * `_isRetry` guards against a loop: if the retried request also comes back 401, the
 * session is genuinely gone and the user is signed out rather than the client refreshing
 * forever.
 */
export async function apiFetch(path, { method = 'GET', body, signal, headers = {} } = {}, _isRetry = false) {
  const token = getAccessToken()

  const response = await fetch(`${BASE}${path}`, {
    method,
    signal,
    // Sends the refresh cookie on the auth routes it is scoped to. Ordinary API calls
    // carry no cookie, because the cookie's path does not match them.
    credentials: 'include',
    headers: {
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (response.status === 401 && !_isRetry && !path.startsWith('/auth/')) {
    const refreshed = await refreshSession()
    if (refreshed) {
      return apiFetch(path, { method, body, signal, headers }, true)
    }
    notifyUnauthenticated()
    throw await parseError(response)
  }

  if (!response.ok) {
    throw await parseError(response)
  }

  if (response.status === 204) return null
  return response.json()
}

export const api = {
  get: (path, options) => apiFetch(path, { ...options, method: 'GET' }),
  post: (path, body, options) => apiFetch(path, { ...options, method: 'POST', body }),
  patch: (path, body, options) => apiFetch(path, { ...options, method: 'PATCH', body }),
  del: (path, options) => apiFetch(path, { ...options, method: 'DELETE' }),
}

/** Build a query string from a filter object, dropping empty values. */
export function queryString(params) {
  const search = new URLSearchParams()
  Object.entries(params || {}).forEach(([key, value]) => {
    // An empty filter must not become `?place=`, which the server would read as a filter
    // on the empty string and match nothing.
    if (value === undefined || value === null || value === '' || value === false) return
    search.set(key, String(value))
  })
  const query = search.toString()
  return query ? `?${query}` : ''
}
