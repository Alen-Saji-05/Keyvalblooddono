import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Every /api call is proxied to Flask rather than sent cross-origin.
    //
    // The alternative - the browser calling http://localhost:5000 directly - works, but
    // it puts development on a different code path than production, where the SPA is
    // served from the same origin as the API. Cookie attributes, SameSite behaviour, and
    // CORS preflights would then all be exercised only in one environment. Proxying keeps
    // the refresh cookie same-origin in both, so a cookie problem cannot hide until
    // deployment.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: false,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
