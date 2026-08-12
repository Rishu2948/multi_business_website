import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useChatContext } from '../context/ChatContext';
import { GoogleLogin } from '@react-oauth/google';
import apiClient from '../utils/api';
import { toast } from 'sonner';
import MFAVerification from '../components/MFAVerification';

const Login = () => {
  console.log("Client ID loaded:", process.env.REACT_APP_GOOGLE_CLIENT_ID);
  const navigate = useNavigate();
  const { isAuthenticated, user, login } = useAuth();
  const { setChatLoginData } = useChatContext();

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

  const [loading, setLoading] = useState(false);
  const [showMFAVerification, setShowMFAVerification] = useState(false);
  const [mfaUser, setMfaUser] = useState(null);

  const handleGoogleSuccess = async (credentialResponse) => {
    try {
      setLoading(true);
      const res = await apiClient.post('/auth/google', { token: credentialResponse.credential });
      
      // Check if MFA is required
      if (res.data.mfa_required) {
        if (res.data.mfa_enrollment) {
          // MFA enrollment required (not implemented in this iteration)
          toast.error('MFA enrollment is required for privileged accounts. Please contact administrator.');
          setLoading(false);
          return;
        } else {
          // MFA verification required
          setMfaUser(res.data.user);
          setShowMFAVerification(true);
          setLoading(false);
          return;
        }
      }
      
      const userData = res.data.user;
      const accessToken = res.data.access_token;
      login(userData, accessToken); // Pass access token to AuthContext
      setChatLoginData(res.data);  // populates recommendations, preference_summary, is_prime
      toast.success(res.data.message);
      
      if (userData.role === 'super_admin') {
        navigate('/super-admin', { replace: true, state: { user: userData } });
      } else if (userData.role === 'business_admin') {
        navigate('/admin', { replace: true, state: { user: userData } });
      } else if (userData.role === 'staff') {
        navigate('/staff', { replace: true, state: { user: userData } });
      } else {
        navigate('/businesses', { replace: true, state: { user: userData } });
      }
    } catch (error) {
      console.error('Google login failed:', error);
      toast.error('Authentication failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleMFAVerificationComplete = (verificationData) => {
    // After MFA verification, complete the login flow
    login(mfaUser, verificationData.access_token);
    setChatLoginData({ user: mfaUser }); // Populate chat context
    
    setShowMFAVerification(false);
    
    // Navigate based on role
    if (mfaUser.role === 'super_admin') {
      navigate('/super-admin', { replace: true, state: { user: mfaUser } });
    } else if (mfaUser.role === 'business_admin') {
      navigate('/admin', { replace: true, state: { user: mfaUser } });
    } else if (mfaUser.role === 'staff') {
      navigate('/staff', { replace: true, state: { user: mfaUser } });
    } else {
      navigate('/businesses', { replace: true, state: { user: mfaUser } });
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-white p-8" data-testid="login-page">
      {showMFAVerification ? (
        <MFAVerification 
          onVerificationComplete={handleMFAVerificationComplete}
          user_id={mfaUser?.user_id}
        />
      ) : (
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

            <div className="flex justify-center mt-4">
              {loading ? (
                <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
              ) : (
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={() => toast.error('Login Failed')}
                  theme="filled_blue"
                  size="large"
                  width="100%"
                  text="signin_with"
                />
              )}
            </div>

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
      )}
    </div>
  );
};

export default Login;