import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// En desarrollo (npm run dev), las llamadas a /api van a la app de Docker.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8080',
    },
  },
});
