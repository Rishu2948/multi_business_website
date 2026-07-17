import { useState, useEffect, useRef, useCallback } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../../context/AuthContext';
import { useCart } from '../../context/CartContext';
import apiClient, { API_URL } from '../../utils/api';
import {
  LogOut, User, ShoppingCart, Award, RefreshCw, Package,
  Bell, Menu, X, Crown,
} from 'lucide-react';

const BakeryNavbar = ({ businessId }) => {
  const { user, isAuthenticated, logout } = useAuth();
  const { cartCount } = useCart();
  const navigate = useNavigate();
  const location = useLocation();

  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [showNotifs, setShowNotifs] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isPrime, setIsPrime] = useState(false);
  const notifRef = useRef(null);
  const sseRef = useRef(null);

  // Close mobile drawer on route change
  useEffect(() => { setMobileOpen(false); }, [location.pathname]);

  const fetchNotifications = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const res = await apiClient.get('/order-management/notifications');
      setNotifications(res.data.notifications.slice(0, 10));
      setUnreadCount(res.data.unread_count);
    } catch {}
  }, [isAuthenticated]);

  // Check Prime status for current business
  useEffect(() => {
    if (!isAuthenticated || !businessId) return;

    const checkPrimeStatus = async () => {
      try {
        const res = await apiClient.get(`/prime/upgrade-info/${businessId}`);
        const membership = res.data.membership;
        setIsPrime(membership && membership.status === 'active');
      } catch (err) {
        setIsPrime(false);
      }
    };

    checkPrimeStatus();
  }, [isAuthenticated, businessId]);

  // SSE + polling fallback
  useEffect(() => {
    if (!isAuthenticated) return;
    fetchNotifications();

    const sseUrl = `${API_URL.replace('/api', '')}/api/sse/events?token=${document.cookie.replace(/(?:(?:^|.*;\s*)session_token\s*=\s*([^;]*).*$)|^.*$/, '$1')}`;
    try {
      const es = new EventSource(sseUrl, { withCredentials: true });
      sseRef.current = es;
      es.onmessage = event => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'notification' || data.type === 'order_status') fetchNotifications();
        } catch {}
      };
    } catch {}

    const id = setInterval(fetchNotifications, 60000);
    return () => {
      clearInterval(id);
      if (sseRef.current) { sseRef.current.close(); sseRef.current = null; }
    };
  }, [isAuthenticated, fetchNotifications]);

  // Close notifications on outside click
  useEffect(() => {
    const handler = e => { if (notifRef.current && !notifRef.current.contains(e.target)) setShowNotifs(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const markAllRead = async () => {
    try {
      await apiClient.put('/order-management/notifications/read-all');
      setUnreadCount(0);
      setNotifications(n => n.map(x => ({ ...x, read: true })));
    } catch {}
  };

  const handleLogout = async () => { await logout(); navigate('/login'); };

  const isActive = path => location.pathname === path;
  const linkClass = path =>
    `text-xs tracking-[0.15em] uppercase font-semibold transition-colors duration-300
    ${isActive(path) ? 'text-[#D4A373]' : 'text-[#4A3B32] hover:text-[#D4A373]'}`;

  const getDashboardLink = () => {
    if (!user) return '/login';
    if (user.role === 'super_admin') return '/super-admin';
    if (user.role === 'business_admin') return '/admin';
    if (user.role === 'delivery_agent') return '/delivery';
    if (user.role === 'staff') return '/staff';
    return null;
  };

  // The effective businessId for catalog links
  const bizId = businessId || 'whisked_words';
  const catalogPath = `/business/${bizId}/catalog`;
  const customOrderPath = `/business/${bizId}/custom-order`;

  // Nav links shared between desktop and mobile drawer
  const primaryLinks = [
    { to: catalogPath, label: 'Shop', testId: 'nav-shop' },
    { to: customOrderPath, label: 'Custom Orders', testId: 'nav-custom-orders' },
    ...(isAuthenticated && (user?.role === 'super_admin' || user?.role === 'business_admin')
      ? [{ to: '/admin', label: 'Dashboard', testId: 'nav-dashboard' }]
      : []),
    ...(isAuthenticated && user?.role === 'delivery_agent'
      ? [{ to: '/delivery', label: 'Deliveries', testId: 'nav-deliveries' }]
      : []),
  ];

  const secondaryLinks = isAuthenticated
    ? [
        { to: '/my-orders', label: 'My Orders', icon: <Package size={14} />, testId: 'nav-my-orders' },
        { to: '/loyalty', label: 'Rewards', icon: <Award size={14} />, testId: 'nav-loyalty' },
        { to: '/subscriptions', label: 'Subscribe', icon: <RefreshCw size={13} />, testId: 'nav-subscriptions' },
        { to: `/prime?business_id=${bizId}`, label: 'Prime', icon: <Crown size={13} />, testId: 'nav-prime', isPrime },
      ]
    : [];

  return (
    <>
      <nav
        className="sticky top-0 z-50 backdrop-blur-xl bg-white/90 border-b border-[#E8E0D5]/50 transition-all duration-300"
        data-testid="bakery-navbar"
      >
        <div className="max-w-7xl mx-auto px-4 md:px-6 lg:px-12">
          <div className="flex items-center justify-between h-16 md:h-20">

            {/* ── Left: desktop links ────────────────────────────────── */}
            <div className="hidden md:flex items-center gap-6 lg:gap-8">
              {primaryLinks.map(link => (
                <Link key={link.to} to={link.to} className={linkClass(link.to)} data-testid={link.testId}>
                  {link.label}
                </Link>
              ))}
            </div>

            {/* Mobile: hamburger */}
            <button
              onClick={() => setMobileOpen(true)}
              className="md:hidden p-2 text-[#4A3B32] min-h-[44px] min-w-[44px]"
              aria-label="Open menu"
              aria-expanded={mobileOpen}
              data-testid="navbar-mobile-menu-btn"
            >
              <Menu size={22} strokeWidth={1.5} />
            </button>

            {/* ── Centre: Logo ───────────────────────────────────────── */}
            <Link
              to={catalogPath}
              className="flex flex-col items-center absolute left-1/2 -translate-x-1/2 md:static md:translate-x-0"
              data-testid="nav-logo"
            >
              <span className="font-serif text-xl md:text-2xl lg:text-3xl font-bold text-[#2C2420] tracking-tight italic">
                Whisked Words
              </span>
              <span className="text-[9px] tracking-[0.3em] uppercase text-[#D4A373] font-semibold -mt-0.5 hidden sm:block">
                Artisan Bakery
              </span>
            </Link>

            {/* ── Right: icons ───────────────────────────────────────── */}
            <div className="flex items-center gap-3 md:gap-4">
              {/* Secondary links — desktop only */}
              {secondaryLinks.map(link => (
                <Link
                  key={link.to}
                  to={link.to}
                  className={`hidden lg:flex items-center gap-1.5 ${linkClass(link.to)} ${link.isPrime ? 'text-[#D4A373]' : ''}`}
                  data-testid={link.testId}
                >
                  {link.icon}
                  {link.label}
                  {link.isPrime && (
                    <span className="w-2 h-2 bg-[#D4A373] rounded-full animate-pulse" />
                  )}
                </Link>
              ))}

              {/* Notification bell */}
              {isAuthenticated && (
                <div className="relative" ref={notifRef}>
                  <button
                    onClick={() => { setShowNotifs(v => !v); if (!showNotifs) fetchNotifications(); }}
                    className="relative text-[#4A3B32] hover:text-[#D4A373] transition-colors min-h-[44px] flex items-center"
                    aria-label="Notifications"
                    data-testid="nav-notifications-bell"
                  >
                    <Bell size={20} strokeWidth={1.5} />
                    {unreadCount > 0 && (
                      <span
                        className="absolute -top-1 -right-1 bg-red-500 text-white text-[9px] font-bold
                                   rounded-full w-4 h-4 flex items-center justify-center"
                        data-testid="notification-count"
                      >
                        {unreadCount > 9 ? '9+' : unreadCount}
                      </span>
                    )}
                  </button>

                  {showNotifs && (
                    <div
                      className="absolute right-0 top-12 w-72 sm:w-80 bg-white border border-[#E8E0D5] shadow-xl z-50"
                      data-testid="notifications-dropdown"
                    >
                      <div className="p-4 border-b border-[#E8E0D5] flex items-center justify-between">
                        <p className="text-xs tracking-[0.1em] uppercase text-[#2C2420] font-semibold">Notifications</p>
                        {unreadCount > 0 && (
                          <button onClick={markAllRead}
                            className="text-[10px] tracking-wide text-[#D4A373] hover:text-[#4A3B32] font-semibold uppercase"
                            data-testid="mark-all-read">
                            Mark all read
                          </button>
                        )}
                      </div>
                      <div className="max-h-72 overflow-y-auto">
                        {notifications.length === 0 ? (
                          <div className="p-8 text-center">
                            <Bell size={22} className="mx-auto text-[#786A60] mb-2" strokeWidth={1} />
                            <p className="text-xs text-[#786A60]">No notifications yet</p>
                          </div>
                        ) : notifications.map(n => (
                          <div key={n.notification_id}
                            className={`p-4 border-b border-[#E8E0D5] last:border-0 hover:bg-[#FAF8F5]
                              ${!n.read ? 'bg-[#D4A373]/5' : ''}`}
                            data-testid={`notification-${n.notification_id}`}>
                            <div className="flex items-start gap-3">
                              <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0
                                ${!n.read ? 'bg-[#D4A373]' : 'bg-transparent'}`} />
                              <div>
                                <p className="text-sm font-medium text-[#2C2420]">{n.title}</p>
                                <p className="text-xs text-[#786A60] mt-0.5">{n.message}</p>
                                <p className="text-[10px] text-[#786A60] mt-1">
                                  {new Date(n.created_at).toLocaleDateString('en-IN', {
                                    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
                                  })}
                                </p>
                              </div>
                            </div>
                            {n.order_id && (
                              <Link to={`/track/${n.order_id}`} onClick={() => setShowNotifs(false)}
                                className="text-[10px] tracking-wide text-[#D4A373] hover:text-[#4A3B32] font-semibold uppercase mt-2 inline-block">
                                Track Order
                              </Link>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Cart */}
              <Link
                to="/cart"
                className="relative text-[#4A3B32] hover:text-[#D4A373] transition-colors min-h-[44px] flex items-center"
                aria-label={`Cart (${cartCount} items)`}
                data-testid="nav-cart"
              >
                <ShoppingCart size={21} strokeWidth={1.5} />
                {cartCount > 0 && (
                  <span className="absolute -top-1 -right-1 bg-[#D4A373] text-white text-[9px] font-bold
                                   rounded-full w-4 h-4 flex items-center justify-center">
                    {cartCount}
                  </span>
                )}
              </Link>

              {/* Auth — desktop */}
              {isAuthenticated ? (
                <div className="hidden md:flex items-center gap-3 pl-3 border-l border-[#E8E0D5]">
                  {user?.picture ? (
                    <img src={user.picture} alt={user.name}
                      className="w-7 h-7 rounded-full border border-[#E8E0D5]" />
                  ) : (
                    <div className="w-7 h-7 bg-[#F3EFEA] flex items-center justify-center">
                      <User size={14} className="text-[#4A3B32]" />
                    </div>
                  )}
                  <button onClick={handleLogout}
                    className="text-[#786A60] hover:text-[#4A3B32] transition-colors"
                    aria-label="Logout"
                    data-testid="nav-logout-button">
                    <LogOut size={17} strokeWidth={1.5} />
                  </button>
                </div>
              ) : (
                <Link to="/login"
                  className="hidden md:block bg-[#4A3B32] text-white px-5 py-2
                             text-xs tracking-[0.15em] uppercase font-semibold
                             hover:bg-[#332822] transition-colors"
                  data-testid="nav-login-button">
                  Sign In
                </Link>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* ── Mobile full-height drawer ──────────────────────────────────── */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              className="fixed inset-0 bg-black/50 z-50 md:hidden"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setMobileOpen(false)}
              aria-hidden="true"
            />

            {/* Drawer */}
            <motion.nav
              className="fixed top-0 left-0 bottom-0 w-72 bg-white z-50 flex flex-col shadow-xl md:hidden"
              initial={{ x: '-100%' }} animate={{ x: 0 }} exit={{ x: '-100%' }}
              transition={{ type: 'spring', damping: 30, stiffness: 300 }}
              aria-label="Mobile navigation"
              data-testid="mobile-drawer"
            >
              {/* Drawer header */}
              <div className="flex items-center justify-between px-5 py-4 border-b border-[#E8E0D5]">
                <span className="font-serif text-lg italic text-[#2C2420]">Whisked Words</span>
                <button onClick={() => setMobileOpen(false)}
                  className="p-2 text-[#786A60]" aria-label="Close menu"
                  data-testid="mobile-drawer-close">
                  <X size={20} />
                </button>
              </div>

              {/* Drawer links */}
              <div className="flex-1 overflow-y-auto">
                {[...primaryLinks, ...secondaryLinks].map(link => (
                  <Link
                    key={link.to}
                    to={link.to}
                    onClick={() => setMobileOpen(false)}
                    className={`flex items-center gap-3 px-5 py-4 text-sm border-b border-[#F3EFEA]
                      ${isActive(link.to) ? 'text-[#D4A373] font-semibold' : 'text-[#2C2420]'}`}
                    data-testid={link.testId}
                  >
                    {link.icon && <span className="text-[#786A60]">{link.icon}</span>}
                    {link.label}
                    {link.isPrime && (
                      <span className="w-2 h-2 bg-[#D4A373] rounded-full animate-pulse ml-auto" />
                    )}
                  </Link>
                ))}

                {/* Admin config links — for admins */}
                {isAuthenticated && (user?.role === 'super_admin' || user?.role === 'business_admin') && (
                  <>
                    <p className="px-5 pt-4 pb-2 text-[10px] uppercase tracking-wider text-[#786A60] font-semibold">
                      Store Config
                    </p>
                    {[
                      { to: '/admin/categories', label: 'Category Manager' },
                      { to: '/admin/store-config', label: 'Store Config' },
                      ...(user?.role === 'super_admin'
                        ? [{ to: '/admin/business-config', label: 'Business Config' }]
                        : []),
                      { to: '/admin/offers', label: 'Offers' },
                      { to: '/admin/announcements', label: 'Announcements' },
                      { to: '/admin/collections', label: 'Collections' },
                    ].map(link => (
                      <Link
                        key={link.to}
                        to={link.to}
                        onClick={() => setMobileOpen(false)}
                        className="flex items-center px-5 py-3 text-sm text-[#786A60] border-b border-[#F3EFEA] hover:text-[#2C2420]"
                      >
                        {link.label}
                      </Link>
                    ))}
                  </>
                )}
              </div>

              {/* Drawer footer */}
              <div className="border-t border-[#E8E0D5] p-4 pb-[calc(16px+env(safe-area-inset-bottom))]">
                {isAuthenticated ? (
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {user?.picture
                        ? <img src={user.picture} alt={user.name} className="w-8 h-8 rounded-full" />
                        : <div className="w-8 h-8 bg-[#F3EFEA] flex items-center justify-center"><User size={14} /></div>
                      }
                      <div>
                        <p className="text-sm font-medium text-[#2C2420]">{user?.name?.split(' ')[0]}</p>
                        <p className="text-xs text-[#786A60] capitalize">{user?.role?.replace('_', ' ')}</p>
                      </div>
                    </div>
                    <button onClick={async () => { setMobileOpen(false); await handleLogout(); }}
                      className="text-[#786A60] p-2" aria-label="Logout"
                      data-testid="mobile-logout">
                      <LogOut size={18} strokeWidth={1.5} />
                    </button>
                  </div>
                ) : (
                  <Link to="/login" onClick={() => setMobileOpen(false)}
                    className="block w-full text-center bg-[#4A3B32] text-white py-3 text-sm font-semibold"
                    data-testid="mobile-signin">
                    Sign In
                  </Link>
                )}
              </div>
            </motion.nav>
          </>
        )}
      </AnimatePresence>
    </>
  );
};

export default BakeryNavbar;
