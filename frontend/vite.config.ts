/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const API_ORIGIN = process.env.VITE_DEV_API_ORIGIN ?? 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Mirrors the Vercel rewrite, so development and production share one
    // origin model. Without this the dev server is on :5173 and the API on
    // :8000 -- which happens to work, because cookies ignore the port and
    // both are `localhost`, so document.cookie can still read the CSRF
    // token. That accident is exactly why the cross-origin failure reached
    // production without a local symptom.
    proxy: {
      '/api': { target: API_ORIGIN, changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/setupTests.ts',
    css: false,
    // The suite mocks an absolute origin, so it pins the base URL rather
    // than inheriting the relative default.
    env: { VITE_API_BASE_URL: 'http://localhost:8000/api/v1' },
  },
})
