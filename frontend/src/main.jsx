import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { App } from './App'
import { AuthProvider } from './auth/AuthProvider'
import './styles/tokens.css'
import './styles/base.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Retrying a 4xx is pointless: a 403 will still be a 403, and a 422 will still be
      // invalid. Only transient failures are worth a second attempt.
      retry: (failureCount, error) => {
        if (error?.status >= 400 && error?.status < 500) return false
        return failureCount < 2
      },
      // Coordinators work with several tabs open and switch constantly. Refetching on
      // every focus would hammer the API; thirty seconds is long enough to make tab
      // switching quiet and short enough that a donor list is never meaningfully stale.
      staleTime: 30_000,
      refetchOnWindowFocus: true,
    },
    mutations: {
      // A failed write is never retried automatically. Recording a donation twice
      // because a response was slow would corrupt a request's fulfilment total.
      retry: false,
    },
  },
})

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {/* AuthProvider sits inside QueryClientProvider because signing out clears the
          query cache, so it needs the client. */}
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
