import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { BusinessProvider } from './context/BusinessContext';
import { CartProvider } from './context/CartContext';
import ProtectedRoute from './components/protected/ProtectedRoute';
import { Toaster } from './components/ui/sonner';
import './App.css';

// Pages
import Landing from './pages/Landing';
import Login from './pages/Login';
import AuthCallback from './pages/AuthCallback';
import Businesses from './pages/Businesses';
import ProductCatalog from './pages/ProductCatalog';
import BusinessHome from './pages/BusinessHome';
import CartPage from './pages/CartPage';
import CheckoutPage from './pages/CheckoutPage';
import OrderSuccessPage from './pages/OrderSuccessPage';
import MyOrdersPage from './pages/MyOrdersPage';
import CustomCakeOrderPage from './pages/CustomCakeOrderPage';
import ReviewsPage from './pages/ReviewsPage';
import LoyaltyPage from './pages/LoyaltyPage';
import SubscriptionsPage from './pages/SubscriptionsPage';
import SuperAdminDashboard from './pages/SuperAdminDashboard';
import BusinessAdminDashboard from './pages/BusinessAdminDashboard';
import StaffDashboard from './pages/StaffDashboard';
import AdminOrdersDashboard from './pages/AdminOrdersDashboard';
import DeliveryDashboard from './pages/DeliveryDashboard';
import OrderTrackingPage from './pages/OrderTrackingPage';

function AppRouter() {
  const location = useLocation();
  
  // Check URL fragment (not query params) for session_id
  // CRITICAL: This must run synchronously during render before useEffect
  if (location.hash?.includes('session_id=')) {
    return <AuthCallback />;
  }
  
  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/auth-callback" element={<AuthCallback />} />
      <Route path="/businesses" element={<Businesses />} />
      <Route path="/catalog/:businessId" element={<ProductCatalog />} />
      
      {/* Independent Business Sites */}
      <Route path="/business/:businessId" element={<BusinessHome />} />
      <Route path="/business/:businessId/catalog" element={<ProductCatalog />} />
      <Route path="/business/:businessId/contact" element={<BusinessHome />} />
      
      {/* E-Commerce Routes */}
      <Route path="/cart" element={<CartPage />} />
      <Route path="/checkout" element={<CheckoutPage />} />
      <Route path="/order-success" element={<OrderSuccessPage />} />
      <Route path="/my-orders" element={<MyOrdersPage />} />
      
      {/* Phase 3: Reviews, Loyalty, Subscriptions */}
      <Route path="/reviews/:productId" element={<ReviewsPage />} />
      <Route path="/loyalty" element={<LoyaltyPage />} />
      <Route path="/subscriptions" element={<SubscriptionsPage />} />
      <Route path="/business/:businessId/custom-order" element={<CustomCakeOrderPage />} />
      
      {/* Order Tracking */}
      <Route path="/track/:orderId" element={<OrderTrackingPage />} />
      
      {/* Admin Order Management */}
      <Route
        path="/admin/orders"
        element={
          <ProtectedRoute allowedRoles={['super_admin', 'business_admin']}>
            <AdminOrdersDashboard />
          </ProtectedRoute>
        }
      />
      
      {/* Delivery Agent Dashboard */}
      <Route
        path="/delivery"
        element={
          <ProtectedRoute allowedRoles={['delivery_agent']}>
            <DeliveryDashboard />
          </ProtectedRoute>
        }
      />
      
      {/* Protected Routes - Super Admin */}
      <Route
        path="/super-admin"
        element={
          <ProtectedRoute allowedRoles={['super_admin']}>
            <SuperAdminDashboard />
          </ProtectedRoute>
        }
      />
      
      {/* Protected Routes - Business Admin */}
      <Route
        path="/admin"
        element={
          <ProtectedRoute allowedRoles={['super_admin', 'business_admin']}>
            <BusinessAdminDashboard />
          </ProtectedRoute>
        }
      />
      
      {/* Protected Routes - Staff */}
      <Route
        path="/staff"
        element={
          <ProtectedRoute allowedRoles={['super_admin', 'business_admin', 'staff']}>
            <StaffDashboard />
          </ProtectedRoute>
        }
      />
      
      {/* Fallback */}
      <Route path="*" element={<Landing />} />
    </Routes>
  );
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <BusinessProvider>
            <CartProvider>
              <AppRouter />
              <Toaster position="top-right" />
            </CartProvider>
          </BusinessProvider>
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
