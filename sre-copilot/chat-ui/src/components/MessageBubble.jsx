/**
 * MessageBubble — renders a single chat message with role-based styling.
 *
 * Agent messages are rendered with `react-markdown` to support bold text,
 * bullet lists, and fenced code blocks (Requirement 6.5).  User messages are
 * rendered as plain text to avoid unintended Markdown interpretation of
 * operational content (e.g. IP addresses, regex patterns).
 *
 * @param {{ message: { role: 'user'|'agent', content: string, timestamp: string, dataFreshness?: string } }} props
 */

import ReactMarkdown from 'react-markdown';

export default function MessageBubble({ message }) {
  const { role, content, timestamp, dataFreshness } = message;
  const isAgent = role === 'agent';

  // Format the timestamp as a human-readable time string (HH:MM).
  const formattedTime = timestamp
    ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : null;

  return (
    <article
      className={`message-bubble message-bubble--${role}`}
      aria-label={`${isAgent ? 'Agent' : 'You'}: ${content.slice(0, 60)}${content.length > 60 ? '…' : ''}`}
    >
      <div className="message-bubble__header">
        <span className="message-bubble__role" aria-hidden="true">
          {isAgent ? '🤖 SRE Copilot' : '👤 You'}
        </span>
        {formattedTime && (
          <time className="message-bubble__time" dateTime={timestamp}>
            {formattedTime}
          </time>
        )}
      </div>

      <div className="message-bubble__content">
        {isAgent ? (
          <ReactMarkdown
            components={{
              // Open external links in a new tab safely.
              a: ({ node, href, children, ...props }) => (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  {...props}
                >
                  {children}
                </a>
              ),
              // Code blocks get a distinctive monospace treatment.
              code: ({ node, inline, className, children, ...props }) => {
                if (inline) {
                  return (
                    <code className="message-bubble__inline-code" {...props}>
                      {children}
                    </code>
                  );
                }
                return (
                  <pre className="message-bubble__code-block">
                    <code className={className} {...props}>
                      {children}
                    </code>
                  </pre>
                );
              },
            }}
          >
            {content}
          </ReactMarkdown>
        ) : (
          <p className="message-bubble__text">{content}</p>
        )}
      </div>

      {isAgent && dataFreshness && (
        <footer className="message-bubble__footer">
          <span className="message-bubble__freshness">
            Data as of{' '}
            <time dateTime={dataFreshness}>
              {new Date(dataFreshness).toLocaleString()}
            </time>
          </span>
        </footer>
      )}
    </article>
  );
}
