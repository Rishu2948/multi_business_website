import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import apiClient from '../utils/api';

const AuthCallback = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    // Prevent double processing in StrictMode
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const processAuth = async () => {
      try {
        // Extract session_id from URL fragment
        const hash = window.location.hash.substring(1);
        const params = new URLSearchParams(hash);
        const sessionId = params.get('session_id');

        if (!sessionId) {
          throw new Error('No session_id found');
        }

        // Exchange session_id for session_token
        const response = await apiClient.post('/auth/session', {
          session_id: sessionId
        });

        const userData = response.data.user;
        login(userData);

        // Redirect based on role
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
        console.error('Auth callback error:', error);
        navigate('/login', { replace: true });
      }
    };

    processAuth();
  }, [login, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-white">
      <div className="text-center">
        <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto"></div>
        <p className="mt-4 text-muted">Completing login...</p>
      </div>
    </div>
  );
};

export default AuthCallback;