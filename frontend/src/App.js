import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { BusinessProvider } from './context/BusinessContext';
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
import SuperAdminDashboard from './pages/SuperAdminDashboard';
import BusinessAdminDashboard from './pages/BusinessAdminDashboard';
import StaffDashboard from './pages/StaffDashboard';

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
            <AppRouter />
            <Toaster position="top-right" />
          </BusinessProvider>
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
