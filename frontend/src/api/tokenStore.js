/*
 * The access token, held in a module variable.
 *
 * Not localStorage, and not sessionStorage. Both are readable by any script that gets
 * injected into the page, and this API returns donor phone numbers, home locations, and
 * medical reasons for unavailability. A stolen token here is a concrete harm to
 * identifiable people.
 *
 * A module variable is lost on page refresh, which is the usual objection. The refresh
 * cookie solves that: it is httpOnly, so no script can read it, and the client silently
 * exchanges it for a new access token on load. The user notices nothing.
 *
 * Kept outside React state on purpose. The fetch wrapper needs the current token from
 * inside callbacks that were created earlier, and reading it from a closure over React
 * state gives a stale value at exactly the wrong moment - during a retry after a refresh.
 */

let accessToken = null
let onUnauthenticated = null

export function getAccessToken() {
  return accessToken
}

export function setAccessToken(token) {
  accessToken = token
}

export function clearAccessToken() {
  accessToken = null
}

/**
 * Register what should happen when the session cannot be recovered.
 *
 * The client cannot navigate on its own without importing the router, which would make a
 * transport module depend on routing. Instead the auth provider registers a callback, and
 * the client reports the fact.
 */
export function setUnauthenticatedHandler(handler) {
  onUnauthenticated = handler
}

export function notifyUnauthenticated() {
  clearAccessToken()
  if (onUnauthenticated) onUnauthenticated()
}
