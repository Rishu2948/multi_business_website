import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

const ProtectedRoute = ({ children, allowedRoles = [] }) => {
  const { user, loading, isAuthenticated } = useAuth();
  const location = useLocation();

  // Show loading while checking auth
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="mt-4 text-muted">Loading...</p>
        </div>
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Check role permissions
  if (allowedRoles.length > 0 && !allowedRoles.includes(user.role)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white p-8">
        <div className="text-center max-w-md">
          <h1 className="text-4xl font-black text-primary mb-4">ACCESS DENIED</h1>
          <p className="text-muted mb-8">You don't have permission to access this page.</p>
          <button
            onClick={() => window.history.back()}
            className="bg-primary text-white px-8 py-3 font-bold tracking-wide border border-primary hover:bg-[#333333] transition-all"
            data-testid="go-back-button"
          >
            GO BACK
          </button>
        </div>
      </div>
    );
  }

  return children;
};

export default ProtectedRoute;