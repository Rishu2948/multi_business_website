/**
 * OrderNavbar
 * Used on /business/:businessId/catalog and /catalog/:businessId.
 * Shows store status, location, order type switcher and offers count.
 * All data is fetched from GET /api/store/info/:businessId — fully config-driven.
 * Mobile: compact two-row layout. Desktop: full row.
 */

import { useState, useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import { MapPin, ChevronDown, ShoppingCart, Menu } from 'lucide-react';
import { useCart } from '../../context/CartContext';
import { useAuth } from '../../context/AuthContext';
import OffersPanel from '../catalog/OffersPanel';
import apiClient from '../../utils/api';

const OrderNavbar = ({ businessId: propBusinessId, business }) => {
  const params = useParams();
  const businessId = propBusinessId || params.businessId;

  const { cart } = useCart();
  const { user } = useAuth();

  const [storeInfo, setStoreInfo] = useState(null);
  const [orderType, setOrderType] = useState('delivery');
  const [offerCount, setOfferCount] = useState(0);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const cartCount = cart?.items?.reduce((sum, i) => sum + i.quantity, 0) || 0;

  useEffect(() => {
    if (!businessId) return;
    apiClient.get(`/store/info/${businessId}`)
      .then(res => {
        setStoreInfo(res.data);
        if (res.data.order_types?.length > 0) {
          setOrderType(res.data.order_types[0]);
        }
      })
      .catch(() => {});

    apiClient.get(`/offers/${businessId}`)
      .then(res => setOfferCount(res.data.count || 0))
      .catch(() => {});
  }, [businessId]);

  const displayName = storeInfo?.store_display_name || business?.business_name || 'Store';
  const location = storeInfo?.location_label || '';
  const isOpen = storeInfo?.is_open ?? true;
  const orderTypes = storeInfo?.order_types || ['delivery'];

  return (
    <header className="sticky top-0 z-40 bg-white border-b border-[#E8E0D5] shadow-sm"
            data-testid="order-navbar">
      {/* Top row: Logo + primary nav + auth */}
      <div className="flex items-center justify-between px-4 md:px-6 py-3">
        {/* Logo */}
        <Link
          to={`/business/${businessId}`}
          className="flex items-center gap-2 flex-shrink-0"
          data-testid="order-navbar-logo"
        >
          {business?.logo_url && (
            <img src={business.logo_url} alt={displayName}
              className="w-8 h-8 object-cover" />
          )}
          <span className="font-serif text-xl italic text-[#4A3B32] hidden sm:block">
            {displayName}
          </span>
        </Link>

        {/* Desktop nav links */}
        <nav className="hidden lg:flex items-center gap-6" aria-label="Main navigation">
          <Link to={`/business/${businessId}`}
            className="text-sm text-[#786A60] hover:text-[#2C2420] transition-colors">
            Home
          </Link>
          <Link to={`/business/${businessId}/catalog`}
            className="text-sm font-medium text-[#2C2420]">
            Order Now
          </Link>
          <Link to="/loyalty"
            className="text-sm text-[#786A60] hover:text-[#2C2420] transition-colors">
            Loyalty
          </Link>
          <Link to="/subscriptions"
            className="text-sm text-[#786A60] hover:text-[#2C2420] transition-colors">
            Subscriptions
          </Link>
          {/* Admin Dashboard link — only shown for admin roles */}
          {user && (user.role === 'super_admin' || user.role === 'business_admin') && (
            <Link
              to={user.role === 'super_admin' ? '/super-admin' : '/admin'}
              className="text-sm font-semibold text-[#D4A373] hover:text-[#4A3B32] transition-colors border border-[#D4A373] px-3 py-1 rounded-sm"
              data-testid="navbar-dashboard-link"
            >
              Dashboard
            </Link>
          )}
        </nav>

        {/* Right controls */}
        <div className="flex items-center gap-3">
          {/* Cart icon — hidden on mobile (FloatingCartBar handles it) */}
          <Link
            to="/cart"
            className="hidden lg:flex items-center gap-1.5 relative min-h-[44px] px-2"
            aria-label={`Cart with ${cartCount} items`}
            data-testid="navbar-cart"
          >
            <ShoppingCart size={20} className="text-[#4A3B32]" />
            {cartCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 bg-[#D4A373] text-white
                               text-[9px] font-bold w-4 h-4 rounded-full
                               flex items-center justify-center">
                {cartCount > 9 ? '9+' : cartCount}
              </span>
            )}
          </Link>

          {user ? (
            <Link to="/my-orders"
              className="hidden lg:block text-sm text-[#786A60] hover:text-[#2C2420]">
              {user.name?.split(' ')[0]}
            </Link>
          ) : (
            <Link to="/login"
              className="hidden lg:flex items-center gap-1.5 text-sm font-medium text-[#4A3B32]
                         border border-[#E8E0D5] px-3 py-2 hover:bg-[#FAF8F5] transition-colors">
              Login
            </Link>
          )}

          {/* Mobile hamburger */}
          <button
            onClick={() => setMobileMenuOpen(prev => !prev)}
            className="lg:hidden p-2 text-[#4A3B32] min-h-[44px] min-w-[44px]"
            aria-label="Toggle menu"
            aria-expanded={mobileMenuOpen}
            data-testid="mobile-menu-toggle"
          >
            <Menu size={20} />
          </button>
        </div>
      </div>

      {/* Second row: store info bar */}
      <div className="flex items-center gap-3 px-4 md:px-6 py-2
                      bg-[#FAF8F5] border-t border-[#E8E0D5] overflow-x-auto scrollbar-hide">
        {/* Store name + open badge */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-sm font-medium text-[#2C2420]">{displayName}</span>
          <span className={`text-[10px] font-bold px-1.5 py-0.5
            ${isOpen ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600'}`}
            data-testid="store-open-badge"
          >
            {isOpen ? 'OPEN' : 'CLOSED'}
          </span>
        </div>

        {/* Location */}
        {location && (
          <div className="flex items-center gap-1 flex-shrink-0 text-[#786A60]">
            <MapPin size={12} />
            <span className="text-xs">{location}</span>
          </div>
        )}

        {/* Order type switcher */}
        {orderTypes.length > 0 && (
          <div className="flex items-center gap-1 flex-shrink-0 ml-auto">
            <span className="text-xs text-[#786A60]">ORDER TYPE</span>
            <div className="relative">
              <select
                value={orderType}
                onChange={e => setOrderType(e.target.value)}
                className="text-xs font-medium text-[#2C2420] bg-transparent border-0
                           appearance-none pr-4 cursor-pointer focus:outline-none"
                aria-label="Order type"
                data-testid="order-type-select"
              >
                {orderTypes.map(type => (
                  <option key={type} value={type}>
                    {type.charAt(0).toUpperCase() + type.slice(1)}
                  </option>
                ))}
              </select>
              <ChevronDown size={10} className="absolute right-0 top-1/2 -translate-y-1/2 text-[#786A60] pointer-events-none" />
            </div>
          </div>
        )}

        {/* Offers chip */}
        {offerCount > 0 && (
          <div className="flex-shrink-0">
            <OffersPanel
              businessId={businessId}
              trigger={
                <span className="flex items-center gap-1">
                  <span className="text-xs font-semibold text-[#D4A373]">
                    {offerCount} OFFER{offerCount > 1 ? 'S' : ''} ▸
                  </span>
                </span>
              }
            />
          </div>
        )}
      </div>

      {/* Mobile dropdown menu */}
      {mobileMenuOpen && (
        <nav
          className="lg:hidden border-t border-[#E8E0D5] bg-white"
          aria-label="Mobile navigation"
        >
          {[
            { to: `/business/${businessId}`, label: 'Home' },
            { to: `/business/${businessId}/catalog`, label: 'Order Now' },
            { to: '/loyalty', label: 'Loyalty & Rewards' },
            { to: '/subscriptions', label: 'Subscriptions' },
            { to: '/my-orders', label: 'My Orders' },
          ].map(({ to, label }) => (
            <Link
              key={to}
              to={to}
              onClick={() => setMobileMenuOpen(false)}
              className="block px-4 py-3 text-sm text-[#2C2420] border-b border-[#E8E0D5]
                         hover:bg-[#FAF8F5] transition-colors"
            >
              {label}
            </Link>
          ))}
          {!user && (
            <Link
              to="/login"
              onClick={() => setMobileMenuOpen(false)}
              className="block px-4 py-3 text-sm font-semibold text-[#4A3B32]"
            >
              Login / Sign up
            </Link>
          )}
        </nav>
      )}
    </header>
  );
};

export default OrderNavbar;
