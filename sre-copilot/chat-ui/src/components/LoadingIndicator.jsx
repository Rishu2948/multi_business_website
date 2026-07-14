/**
 * LoadingIndicator — animated spinner shown while the agent is responding.
 *
 * Renders three pulsing dots with an accessible live region so screen readers
 * announce that the assistant is thinking (Requirement 6.2).
 *
 * @param {{ isLoading: boolean }} props
 */
export default function LoadingIndicator({ isLoading }) {
  if (!isLoading) return null;

  return (
    <div
      className="loading-indicator"
      role="status"
      aria-live="polite"
      aria-label="Agent is thinking"
    >
      <span className="loading-dot" />
      <span className="loading-dot" />
      <span className="loading-dot" />
      <span className="loading-text">Agent is thinking…</span>
    </div>
  );
}
