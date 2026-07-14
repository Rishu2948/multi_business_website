/**
 * main.jsx — Vite entry point for the SRE Copilot Chat UI.
 *
 * Mounts the top-level ChatPage (exported as default from App.jsx) into the
 * `#root` DOM element defined in index.html.  React 18 concurrent mode is
 * used via `createRoot` for future-proof rendering.
 */

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error(
    'Could not find #root element. Check that index.html contains <div id="root"></div>.'
  );
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>
);
