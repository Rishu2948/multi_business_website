import { useState, useCallback, useEffect } from 'react';
import { useChatContext } from '../../context/ChatContext';
import { useAuth } from '../../context/AuthContext';

// In production the chatbot is served through the same CloudFront distribution
// under /chat/* — so we default to the same origin rather than localhost.
const CHATBOT_URL =
  process.env.REACT_APP_CHATBOT_URL ||
  (typeof window !== 'undefined' ? window.location.origin : '');

/**
 * useChatSession — manages chat state and API communication for a single business chatbot session.
 *
 * @param {Object} params
 * @param {string} params.businessId — the business_id scoping all catalog queries
 *
 * Exposes:
 *   sessionId      — current UUID session ID (or null before first message)
 *   messages       — ordered array of { role, content, timestamp }
 *   products       — latest Product_Result array from the service
 *   activeFilters  — current filter state object
 *   intent         — last extracted intent string
 *   isLoading      — true while a request is in-flight
 *   sendMessage(text)  — POST a user message; handles 401/403 as in-chat error messages
 *   clearSession()     — DELETE the server-side session and wipe sessionStorage
 *   removeFilter(key)  — convenience wrapper that sends "remove {key} filter" via sendMessage
 *
 * Requirements: 5.4, 5.5, 5.7, 3.5, 3.7, 10.6
 */
const useChatSession = ({ businessId }) => {
  const { preference_summary } = useChatContext();
  const { user } = useAuth();

  // sessionStorage keys scoped per business
  const storageKey = `chatbot_session_id_${businessId}`;
  const messagesKey = `chatbot_messages_${businessId}`;
  const filtersKey  = `chatbot_filters_${businessId}`;
  const productsKey = `chatbot_products_${businessId}`;

  // Restore sessionId from sessionStorage
  const [sessionId, setSessionId] = useState(() => {
    try { return sessionStorage.getItem(storageKey) || null; } catch { return null; }
  });

  // Restore last 10 messages from sessionStorage so they survive panel close/reopen
  const [messages, setMessages] = useState(() => {
    try {
      const saved = sessionStorage.getItem(messagesKey);
      return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });

  // Restore last active filters
  const [activeFilters, setActiveFilters] = useState(() => {
    try {
      const saved = sessionStorage.getItem(filtersKey);
      return saved ? JSON.parse(saved) : {};
    } catch { return {}; }
  });

  // Restore last products
  const [products, setProducts] = useState(() => {
    try {
      const saved = sessionStorage.getItem(productsKey);
      return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });

  const [intent, setIntent] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Keep sessionStorage in sync whenever sessionId changes
  useEffect(() => {
    try {
      if (sessionId) { sessionStorage.setItem(storageKey, sessionId); }
      else { sessionStorage.removeItem(storageKey); }
    } catch { /* ignore */ }
  }, [sessionId, storageKey]);

  // Persist messages to sessionStorage (keep last 20 for display, cap storage)
  useEffect(() => {
    try {
      const toStore = messages.slice(-20);
      sessionStorage.setItem(messagesKey, JSON.stringify(toStore));
    } catch { /* ignore */ }
  }, [messages, messagesKey]);

  // Persist filters
  useEffect(() => {
    try { sessionStorage.setItem(filtersKey, JSON.stringify(activeFilters)); }
    catch { /* ignore */ }
  }, [activeFilters, filtersKey]);

  // Persist products
  useEffect(() => {
    try { sessionStorage.setItem(productsKey, JSON.stringify(products)); }
    catch { /* ignore */ }
  }, [products, productsKey]);

  /**
   * Append a message to the local messages array.
   */
  const addMessage = useCallback((role, content) => {
    setMessages((prev) => [
      ...prev,
      { role, content, timestamp: new Date().toISOString() },
    ]);
  }, []);

  /**
   * sendMessage — POST { session_id, business_id, message, user_id?, preference_summary? }
   * to the chat service and update all local state from the response.
   *
   * Handles:
   *   401 → in-chat "Session expired" message (Req 10.6)
   *   403 → in-chat "Upgrade to Prime" message with /prime link (Req 10.6)
   *
   * @param {string} text — the raw user message text
   */
  const sendMessage = useCallback(
    async (text) => {
      if (!text || !text.trim()) return;

      // Optimistically append the user's message immediately.
      addMessage('user', text);
      setIsLoading(true);

      const body = {
        business_id: businessId,
        message: text,
      };

      // Include session_id only when we already have one. (Req 5.5)
      if (sessionId) {
        body.session_id = sessionId;
      }

      // Include user_id for personalisation when the user is authenticated. (Req 4.4)
      if (user?.user_id) {
        body.user_id = user.user_id;
      }

      // Forward preference_summary from ChatContext so the service can personalise
      // recommendations even before the user_preferences DB document is written. (Req 4.4)
      if (preference_summary && Object.keys(preference_summary).length > 0) {
        body.preference_summary = preference_summary;
      }

      try {
        const response = await fetch(`${CHATBOT_URL}/chat/message`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          // credentials: 'include' sends the session_token cookie automatically,
          // satisfying the "session cookie or Authorization: Bearer" requirement. (Req 10.1)
          credentials: 'include',
          body: JSON.stringify(body),
        });

        // --- Error status handling ---

        if (response.status === 401) {
          // Session expired or token invalid — surface as in-chat message. (Req 10.6)
          addMessage(
            'assistant',
            'Session expired — please log in again.',
          );
          return;
        }

        if (response.status === 403) {
          // Non-prime customer — surface upgrade prompt as in-chat message. (Req 10.6)
          addMessage(
            'assistant',
            'Upgrade to Prime to use the AI assistant. <a href="/prime">Upgrade now</a>',
          );
          return;
        }

        if (!response.ok) {
          // Generic server error — surface a friendly fallback message.
          addMessage(
            'assistant',
            'Something went wrong. Please try again.',
          );
          return;
        }

        // --- Happy path ---

        const data = await response.json();

        // Persist the (possibly new) session_id so subsequent messages continue
        // the same server-side session. (Req 5.4, 5.7)
        if (data.session_id) {
          setSessionId(data.session_id);
        }

        // Append the assistant's reply to the message list.
        if (data.reply) {
          addMessage('assistant', data.reply);
        }

        // Update product results, active filters, and intent from the response.
        setProducts(data.products ?? []);
        setActiveFilters(data.active_filters ?? {});
        setIntent(data.intent ?? '');
      } catch (error) {
        // Network error or JSON parse failure — surface a friendly fallback.
        addMessage(
          'assistant',
          'Unable to reach the chat service. Please check your connection and try again.',
        );
      } finally {
        setIsLoading(false);
      }
    },
    [addMessage, businessId, preference_summary, sessionId, user],
  );

  /**
   * clearSession — DELETE the server-side session document and wipe local state.
   * (Req 3.5, 5.5)
   */
  const clearSession = useCallback(async () => {
    if (sessionId) {
      try {
        await fetch(`${CHATBOT_URL}/chat/session/${sessionId}`, {
          method: 'DELETE',
          credentials: 'include',
        });
      } catch {
        // Best-effort — even if the request fails, clear local state.
      }
    }

    try {
      sessionStorage.removeItem(storageKey);
      sessionStorage.removeItem(messagesKey);
      sessionStorage.removeItem(filtersKey);
      sessionStorage.removeItem(productsKey);
    } catch { /* ignore */ }

    setSessionId(null);
    setMessages([]);
    setProducts([]);
    setActiveFilters({});
    setIntent('');
  }, [sessionId, storageKey, messagesKey, filtersKey, productsKey]);

  /**
   * removeFilter — sends "remove {key} filter" as a chat message so the service
   * updates active_filters and returns refreshed results. (Req 3.7)
   *
   * @param {string} key — the filter key to remove (e.g. "price_max", "flavor")
   */
  const removeFilter = useCallback(
    (key) => {
      sendMessage(`remove ${key} filter`);
    },
    [sendMessage],
  );

  return {
    sessionId,
    messages,
    products,
    activeFilters,
    intent,
    isLoading,
    sendMessage,
    clearSession,
    removeFilter,
  };
};

export default useChatSession;
