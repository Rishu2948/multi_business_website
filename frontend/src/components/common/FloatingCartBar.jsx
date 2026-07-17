/**
 * FloatingCartBar
 * Sticky bottom bar shown on mobile when cart has items.
 * Hidden on lg+ (cart icon is in the navbar instead).
 * Safe-area aware for iPhone notch / home indicator.
 */

import { Link } from 'react-router-dom';
import { ShoppingCart, ArrowRight } from 'lucide-react';
import { useCart } from '../../context/CartContext';

const FloatingCartBar = () => {
  const { cart } = useCart();

  if (!cart?.items?.length) return null;

  const itemCount = cart.items.reduce((sum, item) => sum + item.quantity, 0);
  const total = cart.total_amount || 0;

  return (
    <div
      className="lg:hidden fixed bottom-0 left-0 right-0 z-50
                 bg-[#4A3B32] text-white shadow-lg
                 pb-[env(safe-area-inset-bottom)]"
      data-testid="floating-cart-bar"
    >
      <Link
        to="/cart"
        className="flex items-center justify-between px-4 py-3 min-h-[56px]"
        aria-label={`View cart — ${itemCount} item${itemCount > 1 ? 's' : ''}, ₹${total}`}
      >
        <div className="flex items-center gap-3">
          <div className="relative">
            <ShoppingCart size={20} />
            <span
              className="absolute -top-2 -right-2 bg-[#D4A373] text-white text-[9px]
                         font-bold w-4 h-4 rounded-full flex items-center justify-center"
              aria-hidden="true"
            >
              {itemCount > 9 ? '9+' : itemCount}
            </span>
          </div>
          <span className="text-sm font-medium">
            {itemCount} item{itemCount > 1 ? 's' : ''} in cart
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">₹{total.toLocaleString()}</span>
          <ArrowRight size={16} />
        </div>
      </Link>
    </div>
  );
};

export default FloatingCartBar;
