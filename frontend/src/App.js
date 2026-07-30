import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ChatProvider } from './context/ChatContext';
import { BusinessProvider } from './context/BusinessContext';
import { CartProvider } from './context/CartContext';
import ProtectedRoute from './components/protected/ProtectedRoute';
import { Toaster } from './components/ui/sonner';
import './App.css';

// Pages
import Landing from './pages/Landing';
import Login from './pages/Login';
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
import UserManagementPage from './pages/UserManagementPage';
import BusinessAdminDashboard from './pages/BusinessAdminDashboard';
import StaffDashboard from './pages/StaffDashboard';
import AdminOrdersDashboard from './pages/AdminOrdersDashboard';
import DeliveryDashboard from './pages/DeliveryDashboard';
import OrderTrackingPage from './pages/OrderTrackingPage';
import CategoryManager from './pages/admin/CategoryManager';
import StoreConfigManager from './pages/admin/StoreConfigManager';
import OffersManager from './pages/admin/OffersManager';
import AnnouncementManager from './pages/admin/AnnouncementManager';
import CollectionManager from './pages/admin/CollectionManager';
import CollectionsPage from './pages/CollectionsPage';
import ProductManager from './pages/admin/ProductManager';
import BusinessConfigManager from './pages/admin/BusinessConfigManager';
import BusinessConfigSelector from './pages/admin/BusinessConfigSelector';
import PrimeUpgradePage from './pages/PrimeUpgradePage';
import PrimeMembershipPage from './pages/PrimeMembershipPage';
import PrimeMembershipManager from './pages/admin/PrimeMembershipManager';
import PrimeAnalytics from './pages/admin/PrimeAnalytics';

function AppRouter() {
  const location = useLocation();
  
  // Check URL fragment (not query params) for session_id
  // CRITICAL: This must run synchronously during render before useEffect
  
  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
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
      
      {/* Prime Membership */}
      <Route path="/prime" element={<PrimeUpgradePage />} />
      <Route
        path="/prime/memberships"
        element={
          <ProtectedRoute>
            <PrimeMembershipPage />
          </ProtectedRoute>
        }
      />
      
      {/* Order Tracking */}
      <Route path="/track/:orderId" element={<OrderTrackingPage />} />

      {/* Collections — customer-facing */}
      <Route path="/business/:businessId/collections/:collectionId" element={<CollectionsPage />} />

      {/* Admin — Category Manager */}
      <Route
        path="/admin/categories"
        element={
          <ProtectedRoute allowedRoles={['super_admin', 'business_admin']}>
            <CategoryManager />
          </ProtectedRoute>
        }
      />

      {/* Admin — Store Config */}
      <Route
        path="/admin/store-config"
        element={
          <ProtectedRoute allowedRoles={['super_admin', 'business_admin']}>
            <StoreConfigManager />
          </ProtectedRoute>
        }
      />

      {/* Admin — Business Config Selector (super admin only) */}
      <Route
        path="/admin/business-config"
        element={
          <ProtectedRoute allowedRoles={['super_admin']}>
            <BusinessConfigSelector />
          </ProtectedRoute>
        }
      />

      {/* Admin — Business Config Manager */}
      <Route
        path="/admin/business-config/:businessId"
        element={
          <ProtectedRoute allowedRoles={['super_admin', 'business_admin']}>
            <BusinessConfigManager />
          </ProtectedRoute>
        }
      />

      {/* Admin — Prime Membership Manager */}
      <Route
        path="/admin/prime-memberships/:businessId"
        element={
          <ProtectedRoute allowedRoles={['super_admin', 'business_admin']}>
            <PrimeMembershipManager />
          </ProtectedRoute>
        }
      />

      {/* Admin — Prime Analytics */}
      <Route
        path="/admin/prime-analytics/:businessId"
        element={
          <ProtectedRoute allowedRoles={['super_admin', 'business_admin']}>
            <PrimeAnalytics />
          </ProtectedRoute>
        }
      />

      {/* Admin — Offers Manager */}
      <Route
        path="/admin/offers"
        element={
          <ProtectedRoute allowedRoles={['super_admin', 'business_admin']}>
            <OffersManager />
          </ProtectedRoute>
        }
      />

      {/* Admin — Announcement Manager */}
      <Route
        path="/admin/announcements"
        element={
          <ProtectedRoute allowedRoles={['super_admin', 'business_admin']}>
            <AnnouncementManager />
          </ProtectedRoute>
        }
      />

      {/* Admin — Collection Manager */}
      <Route
        path="/admin/collections"
        element={
          <ProtectedRoute allowedRoles={['super_admin', 'business_admin']}>
            <CollectionManager />
          </ProtectedRoute>
        }
      />

      {/* Admin — Product Manager */}
      <Route
        path="/admin/products"
        element={
          <ProtectedRoute allowedRoles={['super_admin', 'business_admin']}>
            <ProductManager />
          </ProtectedRoute>
        }
      />
      
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
      <Route
        path="/super-admin/users"
        element={
          <ProtectedRoute allowedRoles={['super_admin']}>
            <UserManagementPage />
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
          <ChatProvider>
            <BusinessProvider>
              <CartProvider>
                <AppRouter />
                <Toaster position="top-right" />
              </CartProvider>
            </BusinessProvider>
          </ChatProvider>
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
