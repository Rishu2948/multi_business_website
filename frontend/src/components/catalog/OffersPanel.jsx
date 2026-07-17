/**
 * OffersPanel
 * Displays active offers from GET /api/offers/:businessId.
 * Mobile: bottom sheet. Desktop: dropdown panel.
 * Fully API-driven — admin creates offers in dashboard, they appear here.
 */

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Tag, Copy, Check, X } from 'lucide-react';
import apiClient from '../../utils/api';

const OfferCard = ({ offer }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!offer.promo_code) return;
    try {
      await navigator.clipboard.writeText(offer.promo_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback — select input trick
    }
  };

  return (
    <div className="border border-[#E8E0D5] p-3 bg-[#FAF8F5]">
      <p className="text-sm font-semibold text-[#2C2420] leading-snug">{offer.title}</p>
      {offer.description && (
        <p className="text-xs text-[#786A60] mt-0.5">{offer.description}</p>
      )}
      {offer.min_order_amount > 0 && (
        <p className="text-xs text-[#786A60] mt-0.5">
          Min order ₹{offer.min_order_amount.toLocaleString()}
        </p>
      )}

      {offer.promo_code && (
        <div className="flex items-center gap-2 mt-2">
          <code className="text-xs font-mono bg-white border border-[#D4A373] text-[#4A3B32] px-2 py-1 tracking-wider">
            {offer.promo_code}
          </code>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 text-xs text-[#D4A373] hover:text-[#4A3B32] transition-colors min-h-[32px] min-w-[60px]"
            aria-label={`Copy promo code ${offer.promo_code}`}
            data-testid={`copy-code-${offer.promo_code}`}
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
            {copied ? 'Copied!' : 'Copy'}
          </button>
        </div>
      )}
    </div>
  );
};

const OffersPanel = ({ businessId, trigger }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [offers, setOffers] = useState([]);
  const [loading, setLoading] = useState(false);
  const panelRef = useRef(null);
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768;

  useEffect(() => {
    if (!isOpen || offers.length > 0) return;
    setLoading(true);
    apiClient.get(`/offers/${businessId}`)
      .then(res => setOffers(res.data.offers || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [isOpen, businessId, offers.length]);

  // Close on outside click (desktop dropdown only)
  useEffect(() => {
    if (!isOpen || isMobile) return;
    const handleClick = e => {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [isOpen, isMobile]);

  return (
    <div className="relative" ref={panelRef}>
      {/* Trigger button — rendered by caller, wrapped here for toggle */}
      <button
        onClick={() => setIsOpen(prev => !prev)}
        className="flex items-center gap-1.5 text-sm font-medium text-[#D4A373] hover:text-[#4A3B32]
                   transition-colors min-h-[44px]"
        aria-expanded={isOpen}
        aria-label={`View offers`}
        data-testid="offers-trigger"
      >
        <Tag size={14} />
        {trigger}
      </button>

      <AnimatePresence>
        {isOpen && (
          <>
            {/* Mobile backdrop */}
            {isMobile && (
              <motion.div
                className="fixed inset-0 bg-black/40 z-40"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={() => setIsOpen(false)}
                aria-hidden="true"
              />
            )}

            {/* Panel */}
            <motion.div
              className={`z-50 bg-white shadow-lg
                ${isMobile
                  ? 'fixed bottom-0 left-0 right-0 rounded-t-2xl max-h-[80vh] overflow-y-auto'
                  : 'absolute right-0 top-full mt-2 w-80 border border-[#E8E0D5] rounded-none'
                }`}
              initial={isMobile ? { y: '100%' } : { opacity: 0, y: -8 }}
              animate={isMobile ? { y: 0 } : { opacity: 1, y: 0 }}
              exit={isMobile ? { y: '100%' } : { opacity: 0, y: -8 }}
              transition={{ type: 'spring', damping: 30, stiffness: 300 }}
              role="dialog"
              aria-label="Available offers"
              data-testid="offers-panel"
            >
              {/* Drag handle */}
              {isMobile && (
                <div className="pt-3 pb-1 flex justify-center">
                  <div className="w-10 h-1 bg-[#E8E0D5] rounded-full" />
                </div>
              )}

              <div className="flex items-center justify-between px-4 py-3 border-b border-[#E8E0D5]">
                <div className="flex items-center gap-2">
                  <Tag size={16} className="text-[#D4A373]" />
                  <p className="font-semibold text-[#2C2420] text-sm">
                    {offers.length > 0 ? `${offers.length} Available Offer${offers.length > 1 ? 's' : ''}` : 'Offers'}
                  </p>
                </div>
                <button
                  onClick={() => setIsOpen(false)}
                  className="p-1 text-[#786A60] hover:text-[#2C2420]"
                  aria-label="Close offers panel"
                >
                  <X size={16} />
                </button>
              </div>

              <div className="p-4 space-y-3 pb-[calc(16px+env(safe-area-inset-bottom))]">
                {loading && (
                  <p className="text-sm text-[#786A60] text-center py-4">Loading offers...</p>
                )}
                {!loading && offers.length === 0 && (
                  <p className="text-sm text-[#786A60] text-center py-4">No active offers right now</p>
                )}
                {offers.map(offer => (
                  <OfferCard key={offer.offer_id} offer={offer} />
                ))}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
};

export default OffersPanel;
