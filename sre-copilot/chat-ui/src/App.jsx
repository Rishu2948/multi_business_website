/**
 * App.jsx — top-level ChatPage for the SRE Copilot Chat UI.
 *
 * Composes ChatWindow, InputBar, and ErrorBanner into a single-page SRE-themed
 * interface with a dark background and green/blue operational accents
 * (Requirements 6.1 – 6.7).
 *
 * Error handling (Requirement 6.6):
 *   - When `error` is set, the ErrorBanner shows the error message.
 *   - The inputValue is pre-populated with the original question so the user
 *     can resubmit without retyping.
 *   - Dismissing the banner calls `clearError` from useChat.
 *
 * Inline validation (Requirement 6.7):
 *   - When `error` is a validation error (empty / over-limit), it is shown
 *     inside the InputBar rather than in the ErrorBanner.
 */

import { useCallback } from 'react';
import { useChat } from './hooks/useChat.js';
import ChatWindow from './components/ChatWindow.jsx';
import InputBar from './components/InputBar.jsx';
import './App.css';

// ── ErrorBanner ───────────────────────────────────────────────────────────────
/**
 * Dismissable error banner for API/network errors.
 *
 * @param {{ error: {message: string} | null, onDismiss: () => void }} props
 */
function ErrorBanner({ error, onDismiss }) {
  if (!error) return null;

  return (
    <div
      className="error-banner"
      role="alert"
      aria-live="assertive"
      aria-atomic="true"
    >
      <span className="error-banner__icon" aria-hidden="true">⚠️</span>
      <p className="error-banner__message">{error.message}</p>
      <button
        type="button"
        className="error-banner__dismiss"
        onClick={onDismiss}
        aria-label="Dismiss error"
      >
        ✕
      </button>
    </div>
  );
}

// ── ChatPage ──────────────────────────────────────────────────────────────────
/**
 * The main chat page.  Drives all state from the `useChat` hook.
 */
function ChatPage() {
  const {
    messages,
    isLoading,
    inputDisabled,
    inputValue,
    error,
    setInputValue,
    submitQuestion,
    clearError,
  } = useChat();

  // Distinguish validation errors (empty / length) from API errors.
  // Validation errors originate from client-side checks in useChat and are
  // shown inline inside the InputBar rather than in the ErrorBanner.
  const isValidationError =
    error &&
    (error.message === 'Message cannot be empty.' ||
      error.message.startsWith('Maximum'));

  const apiError = error && !isValidationError ? error : null;
  const validationError = isValidationError ? error.message : null;

  const handleDismissError = useCallback(() => {
    clearError();
  }, [clearError]);

  return (
    <div className="chat-page">
      {/* ── App header ───────────────────────────────────────────────────── */}
      <header className="chat-page__header" role="banner">
        <div className="chat-page__header-inner">
          <span className="chat-page__logo" aria-hidden="true">🛡️</span>
          <h1 className="chat-page__title">SRE Copilot</h1>
          <p className="chat-page__subtitle">AI-Powered Operational Assistant</p>
        </div>
      </header>

      {/* ── Error banner (API/network errors only) ───────────────────────── */}
      <ErrorBanner error={apiError} onDismiss={handleDismissError} />

      {/* ── Message history ──────────────────────────────────────────────── */}
      <main className="chat-page__main" id="main-content">
        <ChatWindow messages={messages} isLoading={isLoading} />
      </main>

      {/* ── Input bar ────────────────────────────────────────────────────── */}
      <footer className="chat-page__footer" role="contentinfo">
        <InputBar
          inputValue={inputValue}
          setInputValue={setInputValue}
          submitQuestion={submitQuestion}
          isLoading={isLoading}
          inputDisabled={inputDisabled}
          validationError={validationError}
        />
      </footer>
    </div>
  );
}

// Default export so Vite's entry point (main.jsx) can render <App />.
export default ChatPage;
