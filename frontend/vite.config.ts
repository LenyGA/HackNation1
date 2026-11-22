import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  // MapLibre alone is ~1 MB minified; it is loaded only with the pages that show a map.
  build: { chunkSizeWarningLimit: 1200 },
  server: {
    // API_PROXY lets a second dev pair run next to the usual one (e.g. backend on another port).
    proxy: { '/api': process.env.API_PROXY ?? 'http://localhost:8000' },
  },
})
