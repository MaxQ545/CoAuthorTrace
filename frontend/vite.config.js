import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const serverHost = process.env.COAUTHOR_FRONTEND_HOST || '0.0.0.0'
const serverPort = Number(process.env.COAUTHOR_FRONTEND_PORT) || 3000
const apiTarget = process.env.COAUTHOR_API_URL || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: serverHost,  // Listen on all interfaces (IPv4 + IPv6)
    port: serverPort,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      }
    }
  },
  // Pre-bundle dependencies for faster cold start
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-router-dom',
    ],
  },
  // Build optimization
  build: {
    commonjsOptions: {
      include: [/node_modules/],
    },
  },
})
