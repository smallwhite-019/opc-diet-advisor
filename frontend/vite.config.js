import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 本地开发：将 /api 代理到后端 8000
// 生产(部署)：通过 VITE_API_BASE 指向后端公网地址
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:8000' }
  },
  build: { outDir: 'dist' }
})
