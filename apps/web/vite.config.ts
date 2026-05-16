import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const projectDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(projectDir, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Dev proxy: /api/* on the frontend forwards to the FastAPI backend
      // WITHOUT stripping the prefix — the backend now mounts every router
      // under /api so dev and prod routes match without conditional logic.
      // Phase 7 IPv4 fix preserved: 127.0.0.1, not 'localhost', dodges the
      // Windows ::1 → wrong-service collision.
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
