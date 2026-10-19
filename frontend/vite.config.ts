import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// Servidor de desarrollo (npm run dev o el servicio "vite" de docker compose).
// Las llamadas a /api van a la app: en Docker, http://app:8000; fuera, http://localhost:8080.
const apiTarget = process.env.VITE_API_TARGET ?? 'http://localhost:8080';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': apiTarget,
    },
    // En Docker sobre Windows los cambios de archivos no siempre llegan: se comprueban cada poco
    watch:
      process.env.VITE_USE_POLLING === 'true' ? { usePolling: true, interval: 300 } : undefined,
  },
});
