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
  // Vite automatically exposes VITE_* variables from .env files via import.meta.env.
  // Do NOT use `define` to override import.meta.env.VITE_API_URL — that bakes the
  // value at build time and breaks `npm run dev` where you want it read from .env.local.
  // Just set VITE_API_URL in chat-ui/.env.local (for local dev) or pass it at build time
  // for production: VITE_API_URL=https://... npm run build
  test: {
    // Vitest configuration — use jsdom for browser-like environment
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/tests/setup.js',
  },
});
