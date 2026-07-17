/**
 * ProductItemModal
 * Add-on / combo selector modal.
 * Mobile: bottom sheet (slides up from bottom, drag handle).
 * Desktop: centered overlay modal.
 * Add-on groups come from product.addons (API-driven — zero frontend changes needed
 * when admin adds a new group like "Dips & Sauces").
 */

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Share2, Package } from 'lucide-react';
import VegNonVegBadge from './VegNonVegBadge';

// ── Addon group renderer ───────────────────────────────────────────────────

const AddonGroup = ({ group, selections, onToggle }) => {
  const selected = selections[group.group_id] || [];
  const atMax = selected.length >= group.max_select;

  return (
    <div className="py-4 border-t border-[#E8E0D5]">
      <div className="flex items-center gap-2 mb-1">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#2C2420]">
          {group.group_name}
        </p>
        {group.type === 'optional' && (
          <span className="text-[10px] bg-[#F3EFEA] text-[#786A60] px-1.5 py-0.5 font-medium">
            OPTIONAL
          </span>
        )}
        {group.type === 'required' && (
          <span className="text-[10px] bg-[#4A3B32] text-white px-1.5 py-0.5 font-medium">
            REQUIRED
          </span>
        )}
      </div>
      {group.display_label && (
        <p className="text-xs text-[#786A60] mb-2">{group.display_label}</p>
      )}
      {!group.display_label && group.max_select > 1 && (
        <p className="text-xs text-[#786A60] mb-2">
          You can choose up to {group.max_select} option{group.max_select > 1 ? 's' : ''}
        </p>
      )}

      <div className="space-y-2">
        {group.items.map(item => {
          const isSelected = selected.includes(item.addon_item_id);
          const isDisabled = !item.is_available || (!isSelected && atMax);

          return (
            <label
              key={item.addon_item_id}
              className={`flex items-center gap-3 cursor-pointer group
                ${isDisabled ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <input
                type={group.max_select === 1 ? 'radio' : 'checkbox'}
                name={group.group_id}
                checked={isSelected}
                disabled={isDisabled}
                onChange={() => !isDisabled && onToggle(group.group_id, item, group.max_select)}
                className="w-4 h-4 rounded-none accent-[#4A3B32]"
                aria-label={item.name}
              />
              {item.image_url && (
                <img src={item.image_url} alt={item.name}
                  className="w-8 h-8 object-cover rounded-sm flex-shrink-0" />
              )}
              <div className="flex-1 flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5">
                  <VegNonVegBadge isVeg={item.is_veg} size="sm" />
                  <span className="text-sm text-[#2C2420]">{item.name}</span>
                </div>
                {item.price > 0 && (
                  <span className="text-sm text-[#786A60] flex-shrink-0">+₹{item.price}</span>
                )}
              </div>
            </label>
          );
        })}
      </div>
    </div>
  );
};

// ── Main modal ─────────────────────────────────────────────────────────────

const useMediaQuery = (query) => {
  const [matches, setMatches] = useState(
    () => typeof window !== 'undefined' && window.matchMedia(query).matches
  );
  useEffect(() => {
    const mq = window.matchMedia(query);
    const handler = e => setMatches(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [query]);
  return matches;
};

const ProductItemModal = ({ product, isOpen, onClose, onAddToCart }) => {
  const isMobile = useMediaQuery('(max-width: 768px)');

  // selections: { group_id: [addon_item_id, ...] }
  const [selections, setSelections] = useState({});
  const [totalPrice, setTotalPrice] = useState(0);

  // Reset when product changes
  useEffect(() => {
    setSelections({});
    setTotalPrice(product?.base_price || 0);
  }, [product]);

  // Recalculate total when selections change
  useEffect(() => {
    if (!product) return;
    let extra = 0;
    for (const [groupId, itemIds] of Object.entries(selections)) {
      const group = product.addons?.find(g => g.group_id === groupId);
      if (!group) continue;
      itemIds.forEach(itemId => {
        const item = group.items.find(i => i.addon_item_id === itemId);
        if (item) extra += item.price;
      });
    }
    setTotalPrice((product.base_price || 0) + extra);
  }, [selections, product]);

  const handleToggle = useCallback((groupId, item, maxSelect) => {
    setSelections(prev => {
      const current = prev[groupId] || [];
      if (current.includes(item.addon_item_id)) {
        return { ...prev, [groupId]: current.filter(id => id !== item.addon_item_id) };
      }
      if (maxSelect === 1) {
        return { ...prev, [groupId]: [item.addon_item_id] };
      }
      if (current.length >= maxSelect) return prev;
      return { ...prev, [groupId]: [...current, item.addon_item_id] };
    });
  }, []);

  const handleAdd = () => {
    if (!product) return;
    const selectedAddons = Object.entries(selections).map(([groupId, itemIds]) => {
      const group = product.addons?.find(g => g.group_id === groupId);
      return {
        group_id: groupId,
        group_name: group?.group_name || '',
        selected_items: itemIds.map(itemId => {
          const item = group?.items.find(i => i.addon_item_id === itemId);
          return { addon_item_id: itemId, name: item?.name || '', price: item?.price || 0 };
        }),
      };
    }).filter(g => g.selected_items.length > 0);

    onAddToCart(product, selectedAddons, totalPrice);
    onClose();
  };

  const handleShare = () => {
    if (navigator.share) {
      navigator.share({ title: product?.product_name, text: product?.description });
    }
  };

  // Animation variants
  const mobileVariants = {
    hidden: { y: '100%' },
    visible: { y: 0 },
    exit: { y: '100%' },
  };
  const desktopVariants = {
    hidden: { opacity: 0, scale: 0.96 },
    visible: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 0.96 },
  };

  if (!product) return null;

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 bg-black/50 z-40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            aria-hidden="true"
          />

          {/* Modal */}
          <motion.div
            className={`fixed z-50 bg-white overflow-hidden flex flex-col
              ${isMobile
                ? 'bottom-0 left-0 right-0 max-h-[92vh] rounded-t-2xl'
                : 'top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-lg max-h-[90vh] rounded-lg'
              }`}
            variants={isMobile ? mobileVariants : desktopVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            transition={{ type: 'spring', damping: 30, stiffness: 300 }}
            role="dialog"
            aria-modal="true"
            aria-label={product.product_name}
            data-testid="product-item-modal"
          >
            {/* Drag handle — mobile only */}
            {isMobile && (
              <div className="pt-3 pb-1 flex justify-center flex-shrink-0">
                <div className="w-10 h-1 bg-[#E8E0D5] rounded-full" />
              </div>
            )}

            {/* Header controls — desktop close button */}
            {!isMobile && (
              <button
                onClick={onClose}
                className="absolute top-3 right-3 z-10 p-2 rounded-full bg-white/80 hover:bg-[#F3EFEA]"
                aria-label="Close modal"
                data-testid="modal-close"
              >
                <X size={18} className="text-[#4A3B32]" />
              </button>
            )}

            {/* Scrollable content */}
            <div className="overflow-y-auto flex-1">
              {/* Product image */}
              {product.images?.[0]?.url ? (
                <div className="w-full h-48 md:h-56 flex-shrink-0 overflow-hidden">
                  <img
                    src={product.images[0].url}
                    alt={product.product_name}
                    className="w-full h-full object-cover"
                  />
                </div>
              ) : (
                <div className="w-full h-40 bg-[#F3EFEA] flex items-center justify-center flex-shrink-0">
                  <Package size={48} className="text-[#786A60]" strokeWidth={1} aria-hidden="true" />
                </div>
              )}

              {/* Product info */}
              <div className="px-4 pt-4 pb-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <VegNonVegBadge isVeg={product.is_veg} size="lg" />
                    </div>
                    <h2 className="font-serif text-xl text-[#2C2420] leading-snug">
                      {product.product_name}
                    </h2>
                  </div>
                  {navigator.share && (
                    <button
                      onClick={handleShare}
                      className="p-2 text-[#786A60] hover:text-[#4A3B32] flex-shrink-0"
                      aria-label="Share product"
                    >
                      <Share2 size={18} />
                    </button>
                  )}
                </div>

                {product.description && (
                  <p className="text-sm text-[#786A60] mt-2 leading-relaxed">
                    {product.description}
                  </p>
                )}

                {product.allergens?.length > 0 && (
                  <p className="text-xs text-[#786A60] mt-1">
                    Allergens: {product.allergens.join(', ')}
                  </p>
                )}

                <p className="text-base font-semibold text-[#2C2420] mt-2">
                  ₹{product.base_price?.toLocaleString()}
                </p>
              </div>

              {/* Add-on groups — fully API-driven */}
              {product.addons && product.addons.length > 0 && (
                <div className="px-4 pb-2">
                  {product.addons.map(group => (
                    <AddonGroup
                      key={group.group_id}
                      group={group}
                      selections={selections}
                      onToggle={handleToggle}
                    />
                  ))}
                </div>
              )}

              {/* Bottom padding so sticky bar doesn't overlap content */}
              <div className="h-20" />
            </div>

            {/* Sticky bottom bar */}
            <div className="sticky bottom-0 bg-white border-t border-[#E8E0D5] px-4 py-3
                            flex items-center justify-between gap-4 flex-shrink-0
                            pb-[calc(12px+env(safe-area-inset-bottom))]">
              <div>
                <p className="text-xs text-[#786A60]">Total</p>
                <p className="text-base font-semibold text-[#2C2420]">
                  ₹{totalPrice.toFixed(2)}
                </p>
              </div>
              <button
                onClick={handleAdd}
                className="bg-[#4A3B32] text-white px-8 py-2.5 text-sm font-semibold
                           hover:bg-[#332822] transition-colors flex-shrink-0 min-h-[44px]"
                data-testid="modal-add-to-cart"
              >
                Add to Cart
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

export default ProductItemModal;
