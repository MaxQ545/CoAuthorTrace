import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

const serverHost = process.env.COAUTHOR_FRONTEND_HOST || '0.0.0.0'
const serverPort = Number(process.env.COAUTHOR_FRONTEND_PORT) || 3000
const apiTarget = process.env.COAUTHOR_API_URL || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: serverHost,  // Listen on all interfaces (IPv4 + IPv6)
    port: serverPort,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        // Forward real client IP to backend
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req) => {
            const clientIp = req.socket.remoteAddress?.replace('::ffff:', '') || ''
            if (clientIp) {
              proxyReq.setHeader('X-Forwarded-For', clientIp)
            }
          })
        },
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
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-tanstack': ['@tanstack/react-query', '@tanstack/react-table'],
          'vendor-ui': ['framer-motion', 'sonner', 'lucide-react'],
        },
      },
    },
  },
})
