/**
 * useSession — session identifier hook (Requirement 6.4)
 *
 * Maintains a per-tab session ID stored in `sessionStorage` under the key
 * `sre_session_id`.  On the first visit to a browser tab the hook generates a
 * new UUID via `crypto.randomUUID()` and persists it so that the same ID is
 * returned for every subsequent call within that tab's lifetime.  Opening the
 * same page in a second tab produces a different UUID because each tab has its
 * own `sessionStorage` namespace.
 *
 * The session ID is included in every POST /chat request so that the Bedrock
 * Agent can correlate follow-up questions within the same conversation context.
 */

import { useState } from 'react';

/** Key used to store/retrieve the session ID in sessionStorage. */
export const SESSION_STORAGE_KEY = 'sre_session_id';

/**
 * Returns the stable session ID for the current browser tab.
 *
 * @returns {string} A UUID v4 string that is constant for the lifetime of the tab.
 */
export function useSession() {
  const [sessionId] = useState(() => {
    // Attempt to reuse an existing session ID from sessionStorage.
    const existing = sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (existing) {
      return existing;
    }

    // First visit in this tab — generate a new UUID and persist it.
    const newId = crypto.randomUUID();
    sessionStorage.setItem(SESSION_STORAGE_KEY, newId);
    return newId;
  });

  return sessionId;
}
