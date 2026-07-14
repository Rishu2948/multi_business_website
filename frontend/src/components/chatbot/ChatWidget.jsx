import { useState, useEffect, useRef } from 'react';
import { MessageCircle, X, Lock } from 'lucide-react';
import { useChatContext } from '../../context/ChatContext';
import { useAuth } from '../../context/AuthContext';
import ChatPanel from './ChatPanel';

/**
 * ChatWidget — floating action button (FAB) + chat panel root component.
 *
 * Responsibilities:
 *   - Reads auth state from AuthContext and prime status from ChatContext
 *   - Renders nothing for unauthenticated users (Req 10.7)
 *   - Renders a locked FAB with upgrade link for non-prime customers (Req 10.8)
 *   - Renders a standard FAB for authorized users (Req 1.1)
 *   - Expands into a full-screen overlay (<768px) or side panel (≥768px) (Req 1.5)
 *   - Manages open/close toggle with accessible aria-labels (Req 1.4)
 *   - Restores focus to the FAB when the panel closes (Req 1.4)
 *   - Mounts ChatPanel when expanded (Req 1.2)
 *
 * Props:
 *   businessId   {string} — scopes the chat session and catalog links
 *   businessName {string} — displayed in ChatPanel header and welcome message
 *
 * Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 10.7, 10.8
 */
const ChatWidget = ({ businessId, businessName }) => {
  const { is_prime } = useChatContext();
  const { user, isAuthenticated } = useAuth();

  const [isOpen, setIsOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(
    typeof window !== 'undefined' ? window.innerWidth < 768 : false
  );

  const fabRef = useRef(null);

  // ── Responsive viewport detection ─────────────────────────────────────────

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth < 768);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // ── Focus management (Req 1.4) ────────────────────────────────────────────
  // When the panel closes, restore focus to the FAB button.

  useEffect(() => {
    if (!isOpen) {
      fabRef.current?.focus();
    }
  }, [isOpen]);

  // ── Access rules ─────────────────────────────────────────────────────────

  // Not authenticated → render nothing
  if (!isAuthenticated || !user) {
    return null;
  }

  const authorizedRoles = ['super_admin', 'business_admin', 'staff'];
  const isAuthorized =
    authorizedRoles.includes(user.role) ||
    (user.role === 'customer' && is_prime === true);
  const isLocked = user.role === 'customer' && is_prime !== true;

  // ── Shared FAB styles ─────────────────────────────────────────────────────

  const fabBaseStyle = {
    position: 'fixed',
    bottom: '1.5rem',
    right: '1.5rem',
    zIndex: 50,
  };

  // ── Panel container styles ────────────────────────────────────────────────

  const panelStyle = isMobile
    ? {
        position: 'fixed',
        inset: 0,
        zIndex: 40,
      }
    : {
        position: 'fixed',
        right: 0,
        bottom: 0,
        width: '420px',
        height: '80vh',
        zIndex: 40,
      };

  // ── Locked FAB (non-prime customer) ──────────────────────────────────────

  if (isLocked) {
    return (
      <div style={fabBaseStyle}>
        <a
          href="/prime"
          aria-label="Upgrade to Prime to use the AI assistant"
          title="Upgrade to Prime to use the AI assistant"
          className={[
            'flex items-center justify-center w-14 h-14',
            'bg-[#786A60] text-white rounded-full shadow-lg',
            'hover:bg-[#4A3B32] transition-colors duration-200',
            'focus:outline-none focus:ring-2 focus:ring-[#D4A373] focus:ring-offset-2',
          ].join(' ')}
          data-testid="chat-fab-locked"
        >
          <Lock size={22} strokeWidth={2} aria-hidden="true" />
        </a>
      </div>
    );
  }

  // ── Authorized users: standard FAB + optional panel ───────────────────────

  if (!isAuthorized) {
    // Catches any remaining edge cases (e.g. unknown role)
    return null;
  }

  return (
    <>
      {/* Chat panel — mounted only when open */}
      {isOpen && (
        <div style={panelStyle} data-testid="chat-panel-container">
          <ChatPanel
            businessId={businessId}
            businessName={businessName}
            onClose={() => setIsOpen(false)}
          />
        </div>
      )}

      {/* Standard FAB */}
      <div style={fabBaseStyle}>
        <button
          ref={fabRef}
          type="button"
          onClick={() => setIsOpen((prev) => !prev)}
          aria-label={isOpen ? 'Close chat' : 'Open chat'}
          aria-expanded={isOpen}
          aria-haspopup="dialog"
          className={[
            'flex items-center justify-center w-14 h-14',
            'bg-[#4A3B32] text-white rounded-full shadow-lg',
            'hover:bg-[#2C2420] transition-colors duration-200',
            'focus:outline-none focus:ring-2 focus:ring-[#D4A373] focus:ring-offset-2',
          ].join(' ')}
          data-testid="chat-fab"
        >
          {isOpen ? (
            <X size={22} strokeWidth={2} aria-hidden="true" />
          ) : (
            <MessageCircle size={22} strokeWidth={2} aria-hidden="true" />
          )}
        </button>
      </div>
    </>
  );
};

export default ChatWidget;
