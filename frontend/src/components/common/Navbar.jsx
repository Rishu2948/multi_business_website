import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useCart } from '../../context/CartContext';
import { LogOut, User, LayoutDashboard, ShoppingCart, Package, Award, RefreshCw, Cake } from 'lucide-react';

const Navbar = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const { cartCount } = useCart();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const getDashboardLink = () => {
    if (!user) return '/login';
    if (user.role === 'super_admin') return '/super-admin';
    if (user.role === 'business_admin') return '/admin';
    if (user.role === 'staff') return '/staff';
    return '/businesses';
  };

  return (
    <nav className="sticky top-0 z-50 bg-white/80 backdrop-blur-xl backdrop-saturate-150 border-b border-border">
      <div className="max-w-7xl mx-auto px-8 py-4">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-3" data-testid="nav-logo">
            <div className="w-10 h-10 bg-primary flex items-center justify-center">
              <span className="text-white font-black text-xl">JI</span>
            </div>
            <span className="text-xl font-black tracking-tight text-primary uppercase">Jain Industries</span>
          </Link>

          {/* Navigation */}
          <div className="flex items-center gap-4">
            <Link
              to="/businesses"
              className="text-sm font-medium text-primary hover:text-accent transition-colors"
              data-testid="nav-businesses"
            >
              BUSINESSES
            </Link>

            {isAuthenticated && (
              <>
                <Link
                  to="/my-orders"
                  className="text-sm font-medium text-primary hover:text-accent transition-colors flex items-center gap-1"
                  data-testid="nav-my-orders"
                >
                  <Package size={16} />
                  ORDERS
                </Link>
                <Link
                  to="/loyalty"
                  className="text-sm font-medium text-primary hover:text-accent transition-colors flex items-center gap-1"
                  data-testid="nav-loyalty"
                >
                  <Award size={16} />
                  REWARDS
                </Link>
                <Link
                  to="/subscriptions"
                  className="text-sm font-medium text-primary hover:text-accent transition-colors flex items-center gap-1"
                  data-testid="nav-subscriptions"
                >
                  <RefreshCw size={14} />
                  SUBSCRIBE
                </Link>
              </>
            )}
            
            {/* Cart Icon */}
            <Link
              to="/cart"
              className="relative text-primary hover:text-accent transition-colors"
              data-testid="nav-cart"
            >
              <ShoppingCart size={22} />
              {cartCount > 0 && (
                <span className="absolute -top-2 -right-2 bg-accent text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
                  {cartCount}
                </span>
              )}
            </Link>
            
            {isAuthenticated ? (
              <>
                <Link
                  to={getDashboardLink()}
                  className="flex items-center gap-2 text-sm font-medium text-primary hover:text-accent transition-colors"
                  data-testid="nav-dashboard"
                >
                  <LayoutDashboard size={18} />
                  DASHBOARD
                </Link>
                
                <div className="flex items-center gap-4 pl-4 border-l border-border">
                  <div className="flex items-center gap-2" data-testid="nav-user-info">
                    {user?.picture ? (
                      <img src={user.picture} alt={user.name} className="w-8 h-8 rounded-full" />
                    ) : (
                      <div className="w-8 h-8 bg-secondary flex items-center justify-center">
                        <User size={16} />
                      </div>
                    )}
                    <span className="text-sm font-medium text-primary">{user?.name}</span>
                  </div>
                  
                  <button
                    onClick={handleLogout}
                    className="flex items-center gap-2 text-sm font-medium text-primary hover:text-destructive transition-colors"
                    data-testid="nav-logout-button"
                  >
                    <LogOut size={18} />
                  </button>
                </div>
              </>
            ) : (
              <Link
                to="/login"
                className="bg-primary text-white px-6 py-2 font-bold text-sm tracking-wide border border-primary hover:bg-[#333333] transition-all"
                data-testid="nav-login-button"
              >
                LOGIN
              </Link>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;