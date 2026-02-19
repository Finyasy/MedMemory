import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

const backendUrl = process.env.API_PROXY_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: backendUrl,
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path,
        configure: (proxy) => {
          proxy.on('error', (err) => console.log('Proxy error:', err));
          proxy.on('proxyReq', (proxyReq, req) => {
            console.log('Proxying:', req.method, req.url, '→', proxyReq.path);
          });
          proxy.on('proxyRes', (proxyRes, req) => {
            console.log('Proxy response:', proxyRes.statusCode, req.url);
          });
        },
      },
      '/health': {
        target: backendUrl,
        changeOrigin: true,
        secure: false,
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    exclude: ['**/node_modules/**', '**/e2e/**'],
  },
})
