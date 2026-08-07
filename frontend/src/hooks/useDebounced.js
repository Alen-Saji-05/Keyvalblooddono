import { useEffect, useState } from 'react'

/**
 * Delay a rapidly changing value.
 *
 * Used for search boxes. Without it every keystroke is a request: typing a nine character
 * name fires nine queries, eight of which are discarded, and the results flicker as they
 * land out of order.
 */
export function useDebounced(value, delay = 300) {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return debounced
}
