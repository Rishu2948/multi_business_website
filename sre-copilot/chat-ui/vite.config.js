import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    // Output static build to dist/ for S3 static website hosting (Requirement 6.8)
    outDir: 'dist',
    emptyOutDir: true,
  },
  define: {
    // VITE_API_URL is read from the environment at build time.
    // Set it in a .env file: VITE_API_URL=https://<api-gateway-url>
    // Falls back to empty string so the app boots without crashing in dev mode.
    'import.meta.env.VITE_API_URL': JSON.stringify(process.env.VITE_API_URL ?? ''),
  },
  test: {
    // Vitest configuration — use jsdom for browser-like environment
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/tests/setup.js',
  },
});
