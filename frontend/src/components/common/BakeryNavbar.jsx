import { useState, useEffect, useRef, useCallback } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useCart } from '../../context/CartContext';
import apiClient, { API_URL } from '../../utils/api';
import { LogOut, User, ShoppingCart, Award, RefreshCw, Package, Bell, Truck } from 'lucide-react';

const BakeryNavbar = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const { cartCount } = useCart();
  const navigate = useNavigate();
  const location = useLocation();
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [showNotifs, setShowNotifs] = useState(false);
  const notifRef = useRef(null);
  const sseRef = useRef(null);

  const fetchNotifications = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const res = await apiClient.get('/order-management/notifications');
      setNotifications(res.data.notifications.slice(0, 10));
      setUnreadCount(res.data.unread_count);
    } catch {}
  }, [isAuthenticated]);

  // SSE: real-time updates, fallback to 30s polling
  useEffect(() => {
    if (!isAuthenticated) return;
    fetchNotifications();

    // Try SSE connection
    const sseUrl = `${API_URL.replace('/api', '')}/api/sse/events?token=${document.cookie.replace(/(?:(?:^|.*;\s*)session_token\s*=\s*([^;]*).*$)|^.*$/, '$1')}`;
    try {
      const es = new EventSource(sseUrl, { withCredentials: true });
      sseRef.current = es;
      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'notification' || data.type === 'order_status') {
            fetchNotifications();
          }
        } catch {}
      };
      es.onerror = () => { /* SSE failed, polling fallback handles it */ };
    } catch {}

    // Fallback polling (longer interval since SSE handles real-time)
    const id = setInterval(fetchNotifications, 60000);
    return () => {
      clearInterval(id);
      if (sseRef.current) { sseRef.current.close(); sseRef.current = null; }
    };
  }, [isAuthenticated, fetchNotifications]);

  useEffect(() => {
    const handleClick = (e) => { if (notifRef.current && !notifRef.current.contains(e.target)) setShowNotifs(false); };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const markAllRead = async () => {
    try {
      await apiClient.put('/order-management/notifications/read-all');
      setUnreadCount(0);
      setNotifications(n => n.map(x => ({ ...x, read: true })));
    } catch {}
  };

  const handleLogout = async () => { await logout(); navigate('/login'); };

  const isActive = (path) => location.pathname === path;
  const linkClass = (path) => `text-xs tracking-[0.15em] uppercase font-semibold transition-colors duration-300 ${isActive(path) ? 'text-[#D4A373]' : 'text-[#4A3B32] hover:text-[#D4A373]'}`;

  const getDashboardLink = () => {
    if (!user) return '/login';
    if (user.role === 'super_admin') return '/super-admin';
    if (user.role === 'business_admin') return '/admin/orders';
    if (user.role === 'delivery_agent') return '/delivery';
    if (user.role === 'staff') return '/staff';
    return null;
  };

  return (
    <nav className="sticky top-0 z-50 backdrop-blur-xl bg-white/80 border-b border-[#E8E0D5]/50 transition-all duration-300" data-testid="bakery-navbar">
      <div className="max-w-7xl mx-auto px-6 md:px-12">
        <div className="flex items-center justify-between h-20">
          {/* Left Links */}
          <div className="hidden md:flex items-center gap-8">
            <Link to="/business/whisked_words/catalog" className={linkClass('/business/whisked_words/catalog')} data-testid="nav-shop">Shop</Link>
            <Link to="/business/whisked_words/custom-order" className={linkClass('/business/whisked_words/custom-order')} data-testid="nav-custom-orders">Custom Orders</Link>
            {isAuthenticated && (user?.role === 'super_admin' || user?.role === 'business_admin') && (
              <Link to="/admin/orders" className={linkClass('/admin/orders')} data-testid="nav-admin-orders">
                Manage Orders
              </Link>
            )}
            {isAuthenticated && getDashboardLink() && (
              <Link to={getDashboardLink()} className={linkClass(getDashboardLink())} data-testid="nav-dashboard">
                {user?.role === 'delivery_agent' ? 'Deliveries' : user?.role === 'business_admin' ? 'Dashboard' : 'Admin'}
              </Link>
            )}
          </div>

          {/* Center Logo */}
          <Link to="/business/whisked_words/catalog" className="flex flex-col items-center" data-testid="nav-logo">
            <span className="font-serif text-2xl md:text-3xl font-bold text-[#2C2420] tracking-tight italic">Whisked Words</span>
            <span className="text-[10px] tracking-[0.3em] uppercase text-[#D4A373] font-semibold -mt-0.5">Artisan Bakery</span>
          </Link>

          {/* Right Links */}
          <div className="flex items-center gap-5">
            {isAuthenticated && (
              <>
                <Link to="/my-orders" className={`hidden md:flex items-center gap-1.5 ${linkClass('/my-orders')}`} data-testid="nav-my-orders"><Package size={15} />Orders</Link>
                <Link to="/loyalty" className={`hidden md:flex items-center gap-1.5 ${linkClass('/loyalty')}`} data-testid="nav-loyalty"><Award size={15} />Rewards</Link>
                <Link to="/subscriptions" className={`hidden md:flex items-center gap-1.5 ${linkClass('/subscriptions')}`} data-testid="nav-subscriptions"><RefreshCw size={13} />Subscribe</Link>
              </>
            )}

            {/* Notification Bell */}
            {isAuthenticated && (
              <div className="relative" ref={notifRef}>
                <button onClick={() => { setShowNotifs(!showNotifs); if (!showNotifs) fetchNotifications(); }} className="relative text-[#4A3B32] hover:text-[#D4A373] transition-colors" data-testid="nav-notifications-bell">
                  <Bell size={21} strokeWidth={1.5} />
                  {unreadCount > 0 && (
                    <span className="absolute -top-2 -right-2 bg-red-500 text-white text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center" data-testid="notification-count">{unreadCount > 9 ? '9+' : unreadCount}</span>
                  )}
                </button>

                {showNotifs && (
                  <div className="absolute right-0 top-12 w-80 bg-white border border-[#E8E0D5] shadow-xl z-50" data-testid="notifications-dropdown">
                    <div className="p-4 border-b border-[#E8E0D5] flex items-center justify-between">
                      <p className="text-xs tracking-[0.1em] uppercase text-[#2C2420] font-semibold">Notifications</p>
                      {unreadCount > 0 && (
                        <button onClick={markAllRead} className="text-[10px] tracking-wide text-[#D4A373] hover:text-[#4A3B32] font-semibold uppercase" data-testid="mark-all-read">Mark all read</button>
                      )}
                    </div>
                    <div className="max-h-80 overflow-y-auto">
                      {notifications.length === 0 ? (
                        <div className="p-8 text-center"><Bell size={24} className="mx-auto text-[#786A60] mb-2" strokeWidth={1} /><p className="text-xs text-[#786A60]">No notifications yet</p></div>
                      ) : notifications.map(n => (
                        <div key={n.notification_id} className={`p-4 border-b border-[#E8E0D5] last:border-0 hover:bg-[#FAF8F5] transition-colors ${!n.read ? 'bg-[#D4A373]/5' : ''}`} data-testid={`notification-${n.notification_id}`}>
                          <div className="flex items-start gap-3">
                            <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${!n.read ? 'bg-[#D4A373]' : 'bg-transparent'}`} />
                            <div>
                              <p className="text-sm font-medium text-[#2C2420]">{n.title}</p>
                              <p className="text-xs text-[#786A60] mt-0.5">{n.message}</p>
                              <p className="text-[10px] text-[#786A60] mt-1">{new Date(n.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</p>
                            </div>
                          </div>
                          {n.order_id && (
                            <Link to={`/track/${n.order_id}`} onClick={() => setShowNotifs(false)} className="text-[10px] tracking-wide text-[#D4A373] hover:text-[#4A3B32] font-semibold uppercase mt-2 inline-block">Track Order</Link>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Cart */}
            <Link to="/cart" className="relative text-[#4A3B32] hover:text-[#D4A373] transition-colors" data-testid="nav-cart">
              <ShoppingCart size={22} strokeWidth={1.5} />
              {cartCount > 0 && (
                <span className="absolute -top-2 -right-2 bg-[#D4A373] text-white text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center">{cartCount}</span>
              )}
            </Link>

            {isAuthenticated ? (
              <div className="flex items-center gap-3 pl-4 border-l border-[#E8E0D5]">
                <div className="flex items-center gap-2" data-testid="nav-user-info">
                  {user?.picture ? <img src={user.picture} alt={user.name} className="w-8 h-8 rounded-full border border-[#E8E0D5]" /> : <div className="w-8 h-8 bg-[#F3EFEA] flex items-center justify-center"><User size={16} className="text-[#4A3B32]" /></div>}
                </div>
                <button onClick={handleLogout} className="text-[#786A60] hover:text-[#4A3B32] transition-colors" data-testid="nav-logout-button" aria-label="Logout"><LogOut size={18} strokeWidth={1.5} /></button>
              </div>
            ) : (
              <Link to="/login" className="bg-[#4A3B32] text-white px-6 py-2.5 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#332822] transition-colors duration-300" data-testid="nav-login-button">Sign In</Link>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
};

export default BakeryNavbar;
