/**
 * useChat — core chat state management hook (Requirements 6.2, 6.3, 6.6, 6.7)
 *
 * Manages the full lifecycle of a chat conversation:
 *   - Holds the `messages` array (capped at 100 per Requirement 6.3)
 *   - Validates and submits questions via `postChat`
 *   - Controls loading / input-disabled state with timing guarantees
 *   - Handles API errors by preserving the original question for resubmission
 */

import { useState, useCallback } from 'react';
import { postChat } from '../utils/api.js';
import { useSession } from './useSession.js';

/** Maximum number of messages retained in the session (Requirement 6.3). */
export const MAX_MESSAGES = 100;

/** Maximum allowed question length in characters (Requirement 6.7). */
export const MAX_QUESTION_LENGTH = 2000;

/**
 * Append a message to the list, trimming to MAX_MESSAGES if necessary.
 * Oldest messages are dropped when the cap is exceeded.
 *
 * @param {Array} prev   - Current messages array.
 * @param {Object} msg   - New message object to append.
 * @returns {Array}
 */
function appendMessage(prev, msg) {
  const next = [...prev, msg];
  return next.length > MAX_MESSAGES ? next.slice(next.length - MAX_MESSAGES) : next;
}

/**
 * useChat hook.
 *
 * @returns {{
 *   messages: Array<{role: 'user'|'agent', content: string, timestamp: string}>,
 *   isLoading: boolean,
 *   inputDisabled: boolean,
 *   inputValue: string,
 *   error: {message: string, originalQuestion: string} | null,
 *   sessionId: string,
 *   setInputValue: (value: string) => void,
 *   submitQuestion: () => Promise<void>,
 *   clearError: () => void,
 * }}
 */
export function useChat() {
  const sessionId = useSession();

  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [inputDisabled, setInputDisabled] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [error, setError] = useState(null);

  /** Clear any displayed error banner. */
  const clearError = useCallback(() => setError(null), []);

  /**
   * Validate and submit the current `inputValue` as a user question.
   *
   * Timing guarantees (Requirements 6.2, 6.3):
   *   - `isLoading` and `inputDisabled` are set to `true` within 200 ms of call.
   *   - On success, both are reset within 500 ms of receiving the response.
   *   - On error, both are reset immediately and `inputValue` is restored.
   */
  const submitQuestion = useCallback(async () => {
    const question = inputValue.trim();

    // ── Validation (Requirement 6.7) ─────────────────────────────────────────
    if (!question) {
      // Empty / whitespace-only — do not submit; caller can surface the message.
      setError({ message: 'Message cannot be empty.', originalQuestion: inputValue });
      return;
    }

    if (question.length > MAX_QUESTION_LENGTH) {
      setError({
        message: `Maximum ${MAX_QUESTION_LENGTH} characters allowed.`,
        originalQuestion: inputValue,
      });
      return;
    }

    // ── Loading state — must be set within 200 ms (Requirement 6.2) ──────────
    // React's synchronous setState batching means these are applied before the
    // next paint, well within the 200 ms window.
    setIsLoading(true);
    setInputDisabled(true);
    setError(null);

    // Append the user's message immediately so the UI feels responsive.
    const userMessage = {
      role: 'user',
      content: question,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => appendMessage(prev, userMessage));

    // Clear the input field so the user knows the question was captured.
    setInputValue('');

    try {
      const data = await postChat(question, sessionId);

      // ── Success path (Requirement 6.3) ────────────────────────────────────
      // Append the agent response and reset loading state.
      // The entire block runs synchronously within the same microtask so the
      // state transitions complete well within 500 ms of receipt.
      const agentMessage = {
        role: 'agent',
        content: data.response,
        timestamp: new Date().toISOString(),
        dataFreshness: data.dataFreshness,
      };
      setMessages((prev) => appendMessage(prev, agentMessage));
      setIsLoading(false);
      setInputDisabled(false);
    } catch (err) {
      // ── Error path (Requirement 6.6) ──────────────────────────────────────
      // Re-populate the input with the original question so the user can retry,
      // and surface a user-friendly error message.
      setError({ message: err.message, originalQuestion: question });
      setInputValue(question);
      setIsLoading(false);
      setInputDisabled(false);
    }
  }, [inputValue, sessionId]);

  return {
    messages,
    isLoading,
    inputDisabled,
    inputValue,
    error,
    sessionId,
    setInputValue,
    submitQuestion,
    clearError,
  };
}
