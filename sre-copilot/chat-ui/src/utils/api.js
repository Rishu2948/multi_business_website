/**
 * api.js — HTTP utility for the SRE Copilot Chat UI (Requirements 6.2, 6.3, 6.6)
 *
 * Provides a single `postChat` function that sends a question to the backend
 * API Gateway endpoint and returns the structured response.  The API base URL
 * is injected at build time via the `VITE_API_URL` environment variable so the
 * static build can be deployed to any environment without modification.
 */

/**
 * POST /chat with the given question and session ID.
 *
 * @param {string} question   - The SRE question to submit (non-empty, ≤ 2000 chars).
 * @param {string} sessionId  - The per-tab UUID used to correlate conversation turns.
 * @returns {Promise<{response: string, sessionId: string, dataFreshness: string}>}
 *   Resolves with the parsed JSON body on HTTP 2xx responses.
 * @throws {Error} Rejects with a descriptive error message on network failures or
 *   non-2xx HTTP responses so callers can surface a user-friendly error.
 */
export async function postChat(question, sessionId) {
  const apiUrl = import.meta.env.VITE_API_URL;

  if (!apiUrl) {
    throw new Error(
      'API endpoint is not configured. Set VITE_API_URL before building.'
    );
  }

  let response;
  try {
    response = await fetch(`${apiUrl}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ question, sessionId }),
    });
  } catch (networkError) {
    // Network-level failure (DNS, timeout, CORS preflight blocked, etc.)
    throw new Error(
      `Network error: unable to reach the API. Please check your connection and try again. (${networkError.message})`
    );
  }

  if (!response.ok) {
    // Parse the error body if available, otherwise use the HTTP status text.
    let errorMessage = `API returned ${response.status} ${response.statusText}`;
    try {
      const errorBody = await response.json();
      if (errorBody.message) {
        errorMessage = errorBody.message;
      } else if (errorBody.error) {
        errorMessage = `${errorBody.error}: ${errorBody.message ?? 'Unknown error'}`;
      }
    } catch {
      // Error body was not valid JSON — use the status line message above.
    }
    throw new Error(errorMessage);
  }

  // Happy path: parse and return the structured response payload.
  const data = await response.json();
  return {
    response: data.response,
    sessionId: data.sessionId,
    dataFreshness: data.dataFreshness,
  };
}
