/**
 * ChatWindow — scrollable message history panel.
 *
 * Renders the full list of MessageBubble components and auto-scrolls to the
 * newest message whenever the `messages` array changes (Requirements 6.1, 6.3).
 *
 * @param {{
 *   messages: Array<{role: 'user'|'agent', content: string, timestamp: string}>,
 *   isLoading: boolean,
 * }} props
 */

import { useEffect, useRef } from 'react';
import MessageBubble from './MessageBubble.jsx';
import LoadingIndicator from './LoadingIndicator.jsx';

export default function ChatWindow({ messages, isLoading }) {
  const bottomRef = useRef(null);

  // Auto-scroll to the latest message whenever messages or loading state changes.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  return (
    <section
      className="chat-window"
      aria-label="Conversation history"
      aria-live="polite"
      aria-relevant="additions"
    >
      {messages.length === 0 && !isLoading && (
        <div className="chat-window__empty" role="status">
          <p>Ask the SRE Copilot an operational question to get started.</p>
          <p className="chat-window__examples">
            Try: <em>"Why is checkout-service failing?"</em> or{' '}
            <em>"Show me the last 6 hours of errors for payment-service."</em>
          </p>
        </div>
      )}

      <ol className="chat-window__list" aria-label="Messages">
        {messages.map((msg, index) => (
          <li key={`${msg.role}-${msg.timestamp}-${index}`} className="chat-window__item">
            <MessageBubble message={msg} />
          </li>
        ))}
      </ol>

      {/* Loading indicator sits below the last message */}
      <LoadingIndicator isLoading={isLoading} />

      {/* Invisible sentinel element that we scroll into view */}
      <div ref={bottomRef} className="chat-window__bottom" aria-hidden="true" />
    </section>
  );
}
