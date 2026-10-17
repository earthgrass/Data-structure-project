import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Phase 5 Dashboard — Vite 配置
// - 后端默认 http://127.0.0.1:8000（与 FastAPI factory 默认端口一致）
// - 开发期通过 proxy 转发 /api，避免 CORS 麻烦
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5172,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});