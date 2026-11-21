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
    proxy: { '/api': 'http://localhost:8000' },
  },
})
