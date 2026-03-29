import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const Login = () => {
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth();

  useEffect(() => {
    // Redirect if already authenticated
    if (isAuthenticated && user) {
      if (user.role === 'super_admin') {
        navigate('/super-admin');
      } else if (user.role === 'business_admin') {
        navigate('/admin');
      } else if (user.role === 'staff') {
        navigate('/staff');
      } else {
        navigate('/businesses');
      }
    }
  }, [isAuthenticated, user, navigate]);

  const handleGoogleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + '/auth-callback';
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-white p-8" data-testid="login-page">
      <div className="max-w-md w-full">
        {/* Logo */}
        <div className="text-center mb-12">
          <div className="w-20 h-20 bg-primary flex items-center justify-center mx-auto mb-6">
            <span className="text-white font-black text-3xl">MB</span>
          </div>
          <h1 className="text-4xl font-black tracking-tight text-primary uppercase mb-2">
            Multi-Business
          </h1>
          <p className="text-sm tracking-[0.2em] uppercase font-bold text-muted">Admin Portal</p>
        </div>

        {/* Login Card */}
        <div className="bg-white border border-border p-8">
          <p className="text-sm text-muted text-center mb-8">
            Sign in with your Google account to access the admin dashboard.
          </p>

          <button
            onClick={handleGoogleLogin}
            className="w-full bg-accent text-accent-foreground hover:bg-[#002280] transition-all border border-accent px-8 py-4 font-bold tracking-wide flex items-center justify-center gap-3"
            data-testid="google-login-button"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
            </svg>
            LOGIN WITH GOOGLE
          </button>

          <div className="mt-8 pt-8 border-t border-border">
            <p className="text-xs text-muted text-center">
              For admin and staff access only.<br />
              Customers can browse without login.
            </p>
          </div>
        </div>

        {/* Back to Home */}
        <div className="mt-8 text-center">
          <a
            href="/"
            className="text-sm font-medium text-muted hover:text-primary transition-colors"
            data-testid="back-to-home-link"
          >
            ← Back to Homepage
          </a>
        </div>
      </div>
    </div>
  );
};

export default Login;