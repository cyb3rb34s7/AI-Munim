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
      // Dev proxy: /api/* on the frontend forwards to the FastAPI backend.
      // Production deploys hit the API host directly via VITE_API_URL.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (incoming) => incoming.replace(/^\/api/, ''),
      },
    },
  },
});
