import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Send, X } from 'lucide-react';
import FilterPill from './FilterPill';
import ProductCard from './ProductCard';
import ComparisonTable from './ComparisonTable';
import useChatSession from './useChatSession';

/**
 * ChatPanel — expanded chatbot UI rendered inside Chat_Widget.
 *
 * Responsibilities:
 *   - Scrollable message list with user/assistant bubbles + loading indicator
 *   - Active FilterPill row above product results (Req 3.6)
 *   - Product card list / horizontal scroll row depending on count (Req 2.6, 4.5)
 *   - ComparisonTable when intent === 'compare' (Req 7.4)
 *   - "Browse in Catalog" deep-link with active filter params (Req 2.7)
 *   - Input bar: textarea + send button, Enter-to-send (no Shift), disabled while loading
 *   - role="dialog" with aria-labelledby for accessibility (Req 1.4)
 *
 * Props:
 *   businessId   {string}   — scopes chat session and catalog links
 *   businessName {string}   — displayed in header and welcome text
 *   onClose      {function} — called when the user closes the panel
 *
 * Requirements: 1.2, 1.4, 2.6, 2.7, 3.6, 4.5, 7.4
 */
const ChatPanel = ({ businessId, businessName, onClose }) => {
  const {
    messages,
    products,
    activeFilters,
    intent,
    isLoading,
    sendMessage,
    removeFilter,
  } = useChatSession({ businessId });

  const [inputText, setInputText] = useState('');
  const inputRef = useRef(null);
  const messagesEndRef = useRef(null);

  // Focus the input when the panel mounts (Req 1.4)
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Auto-scroll to the latest message whenever messages or loading state changes
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleSend = () => {
    const text = inputText.trim();
    if (!text || isLoading) return;
    setInputText('');
    sendMessage(text);
  };

  const handleKeyDown = (e) => {
    // Submit on Enter without Shift; allow Shift+Enter for newlines
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // ── Derived values ────────────────────────────────────────────────────────

  const filterEntries = Object.entries(activeFilters);
  const hasFilters = filterEntries.length > 0;
  const hasProducts = products.length > 0;
  const isCompare = intent === 'compare';

  // Build catalog deep-link URL (Req 2.7)
  const catalogUrl = `/business/${businessId}/catalog${
    hasFilters ? `?${new URLSearchParams(activeFilters).toString()}` : ''
  }`;

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div
      role="dialog"
      aria-labelledby="chat-panel-title"
      aria-modal="true"
      className="flex flex-col h-full bg-[#FAF8F5] overflow-hidden"
      data-testid="chat-panel"
    >
      {/* ── Header ── */}
      <div className="flex items-center justify-between px-4 py-3 bg-[#2C2420] flex-shrink-0">
        <h2
          id="chat-panel-title"
          className="font-serif text-sm font-semibold text-[#FAF8F5] leading-tight"
        >
          {businessName} AI Assistant
        </h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close chat panel"
          className="text-[#E8E0D5] hover:text-white transition-colors duration-200 focus:outline-none focus:ring-1 focus:ring-[#D4A373] rounded-sm p-0.5"
          data-testid="chat-panel-close"
        >
          <X size={18} strokeWidth={2} aria-hidden="true" />
        </button>
      </div>

      {/* ── Message list ── */}
      <div
        className="flex-1 overflow-y-auto px-4 py-4 space-y-3"
        aria-live="polite"
        aria-label="Chat messages"
        data-testid="chat-messages"
      >
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            data-testid={`chat-message-${msg.role}-${idx}`}
          >
            <div
              className={[
                'max-w-[80%] px-3 py-2 text-sm leading-relaxed rounded-sm',
                msg.role === 'user'
                  ? 'bg-[#4A3B32] text-white'
                  : 'bg-[#F3EFEA] text-[#2C2420]',
              ].join(' ')}
              // Allow the assistant to surface simple HTML links (e.g. upgrade link)
              // The content is controlled — it comes from the Chat_Service, not raw user input
              {...(msg.role === 'assistant' && msg.content.includes('<a ')
                ? { dangerouslySetInnerHTML: { __html: msg.content } }
                : { children: msg.content }
              )}
            />
          </div>
        ))}

        {/* Pulsing dots loading indicator */}
        {isLoading && (
          <div
            className="flex justify-start"
            aria-label="Assistant is typing"
            data-testid="chat-loading-indicator"
          >
            <div className="bg-[#F3EFEA] px-4 py-3 rounded-sm flex items-center gap-1.5">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="w-2 h-2 rounded-full bg-[#786A60] animate-bounce"
                  style={{ animationDelay: `${i * 0.15}s` }}
                />
              ))}
            </div>
          </div>
        )}

        {/* Scroll anchor */}
        <div ref={messagesEndRef} />
      </div>

      {/* ── Results area (filters + products / comparison + browse link) ── */}
      {(hasFilters || hasProducts) && (
        <div
          className="px-4 pb-3 flex flex-col gap-3 border-t border-[#E8E0D5] pt-3 bg-[#FAF8F5] flex-shrink-0 max-h-[45%] overflow-y-auto"
          data-testid="chat-results-area"
        >
          {/* Active filter pills (Req 3.6) */}
          {hasFilters && (
            <div
              className="flex flex-wrap gap-2"
              aria-label="Active filters"
              data-testid="chat-filter-pills"
            >
              {filterEntries.map(([key, value]) => (
                <FilterPill
                  key={key}
                  filterKey={key}
                  filterValue={value}
                  onRemove={removeFilter}
                />
              ))}
            </div>
          )}

          {/* Product results */}
          {hasProducts && (
            <>
              {isCompare ? (
                /* ComparisonTable for compare intent (Req 7.4) */
                <ComparisonTable
                  products={products}
                  attributes={['base_price', 'avg_rating', 'description', 'category_id']}
                  missing_product_names={[]}
                />
              ) : products.length > 3 ? (
                /* Horizontal scroll row for > 3 products (Req 4.5) */
                <div
                  className="overflow-x-auto flex gap-3 pb-2"
                  aria-label="Product results"
                  data-testid="chat-product-scroll-row"
                >
                  {products.map((product) => (
                    <div key={product.product_id} className="flex-shrink-0 w-64">
                      <ProductCard product={product} businessId={businessId} onNavigate={onClose} />
                    </div>
                  ))}
                </div>
              ) : (
                /* Column list for ≤ 3 products (Req 2.6) */
                <div
                  className="flex flex-col gap-2"
                  aria-label="Product results"
                  data-testid="chat-product-list"
                >
                  {products.map((product) => (
                    <ProductCard
                      key={product.product_id}
                      product={product}
                      businessId={businessId}
                      onNavigate={onClose}
                    />
                  ))}
                </div>
              )}

              {/* "Browse in Catalog" deep-link (Req 2.7) */}
              <Link
                to={catalogUrl}
                onClick={onClose}
                className="self-start text-xs font-semibold text-[#4A3B32] underline underline-offset-2 hover:text-[#D4A373] transition-colors duration-200"
                data-testid="chat-browse-catalog-link"
              >
                Browse in Catalog →
              </Link>
            </>
          )}
        </div>
      )}

      {/* ── Input bar ── */}
      <div
        className="flex items-end gap-2 px-3 py-3 border-t border-[#E8E0D5] bg-[#FAF8F5] flex-shrink-0"
        data-testid="chat-input-bar"
      >
        <textarea
          ref={inputRef}
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about products…"
          rows={1}
          aria-label="Chat message input"
          disabled={isLoading}
          className={[
            'flex-1 resize-none bg-[#F3EFEA] border border-[#E8E0D5] rounded-sm',
            'px-3 py-2 text-sm text-[#2C2420] placeholder-[#786A60]',
            'focus:outline-none focus:border-[#4A3B32] focus:ring-1 focus:ring-[#4A3B32]',
            'transition-colors duration-200 leading-snug',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'max-h-28 overflow-y-auto',
          ].join(' ')}
          data-testid="chat-input"
        />

        <button
          type="button"
          onClick={handleSend}
          disabled={isLoading || !inputText.trim()}
          aria-label="Send message"
          className={[
            'flex-shrink-0 flex items-center justify-center w-9 h-9',
            'bg-[#4A3B32] text-white rounded-sm',
            'hover:bg-[#2C2420] transition-colors duration-200',
            'focus:outline-none focus:ring-1 focus:ring-[#D4A373]',
            'disabled:opacity-40 disabled:cursor-not-allowed',
          ].join(' ')}
          data-testid="chat-send-button"
        >
          <Send size={16} strokeWidth={2} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
};

export default ChatPanel;
