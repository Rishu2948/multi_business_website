import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useCart } from '../../context/CartContext';
import { LogOut, User, ShoppingCart, Award, RefreshCw, Package, Cake } from 'lucide-react';

const BakeryNavbar = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const { cartCount } = useCart();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const isActive = (path) => location.pathname === path;

  const linkClass = (path) =>
    `text-xs tracking-[0.15em] uppercase font-semibold transition-colors duration-300 ${
      isActive(path) ? 'text-[#D4A373]' : 'text-[#4A3B32] hover:text-[#D4A373]'
    }`;

  return (
    <nav className="sticky top-0 z-50 backdrop-blur-xl bg-white/80 border-b border-[#E8E0D5]/50 transition-all duration-300" data-testid="bakery-navbar">
      <div className="max-w-7xl mx-auto px-6 md:px-12">
        <div className="flex items-center justify-between h-20">
          {/* Left Links */}
          <div className="hidden md:flex items-center gap-8">
            <Link to="/business/whisked_words/catalog" className={linkClass('/business/whisked_words/catalog')} data-testid="nav-shop">
              Shop
            </Link>
            <Link to="/business/whisked_words/custom-order" className={linkClass('/business/whisked_words/custom-order')} data-testid="nav-custom-orders">
              Custom Orders
            </Link>
          </div>

          {/* Center Logo */}
          <Link to="/business/whisked_words/catalog" className="flex flex-col items-center" data-testid="nav-logo">
            <span className="font-serif text-2xl md:text-3xl font-bold text-[#2C2420] tracking-tight italic">Whisked Words</span>
            <span className="text-[10px] tracking-[0.3em] uppercase text-[#D4A373] font-semibold -mt-0.5">Artisan Bakery</span>
          </Link>

          {/* Right Links */}
          <div className="flex items-center gap-6">
            {isAuthenticated && (
              <>
                <Link to="/my-orders" className={`hidden md:flex items-center gap-1.5 ${linkClass('/my-orders')}`} data-testid="nav-my-orders">
                  <Package size={15} />
                  Orders
                </Link>
                <Link to="/loyalty" className={`hidden md:flex items-center gap-1.5 ${linkClass('/loyalty')}`} data-testid="nav-loyalty">
                  <Award size={15} />
                  Rewards
                </Link>
                <Link to="/subscriptions" className={`hidden md:flex items-center gap-1.5 ${linkClass('/subscriptions')}`} data-testid="nav-subscriptions">
                  <RefreshCw size={13} />
                  Subscribe
                </Link>
              </>
            )}

            {/* Cart */}
            <Link to="/cart" className="relative text-[#4A3B32] hover:text-[#D4A373] transition-colors" data-testid="nav-cart">
              <ShoppingCart size={22} strokeWidth={1.5} />
              {cartCount > 0 && (
                <span className="absolute -top-2 -right-2 bg-[#D4A373] text-white text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center">
                  {cartCount}
                </span>
              )}
            </Link>

            {isAuthenticated ? (
              <div className="flex items-center gap-3 pl-4 border-l border-[#E8E0D5]">
                <div className="flex items-center gap-2" data-testid="nav-user-info">
                  {user?.picture ? (
                    <img src={user.picture} alt={user.name} className="w-8 h-8 rounded-full border border-[#E8E0D5]" />
                  ) : (
                    <div className="w-8 h-8 bg-[#F3EFEA] flex items-center justify-center">
                      <User size={16} className="text-[#4A3B32]" />
                    </div>
                  )}
                </div>
                <button
                  onClick={handleLogout}
                  className="text-[#786A60] hover:text-[#4A3B32] transition-colors"
                  data-testid="nav-logout-button"
                  aria-label="Logout"
                >
                  <LogOut size={18} strokeWidth={1.5} />
                </button>
              </div>
            ) : (
              <Link
                to="/login"
                className="bg-[#4A3B32] text-white px-6 py-2.5 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#332822] transition-colors duration-300"
                data-testid="nav-login-button"
              >
                Sign In
              </Link>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
};

export default BakeryNavbar;
