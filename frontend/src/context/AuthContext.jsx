import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [accessToken, setAccessToken] = useState(null); // Store in memory only
  const [mfaRequired, setMfaRequired] = useState(false);

  const checkAuth = useCallback(async () => {
    // CRITICAL: Skip /auth/me check if returning from OAuth with session_id
    // Let AuthCallback exchange the session_id first
    if (window.location.hash?.includes('session_id=')) {
      setLoading(false);
      return;
    }

    try {
      const response = await axios.get(`${API}/auth/me`, {
        withCredentials: true
      });
      setUser(response.data);
      setIsAuthenticated(true);
    } catch (error) {
      setUser(null);
      setIsAuthenticated(false);
      setAccessToken(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = (userData, token) => {
    setUser(userData);
    setIsAuthenticated(true);
    setAccessToken(token); // Store access token in memory
    window.__ACCESS_TOKEN__ = token; // Store globally for API client
    setMfaRequired(false);
  };

  const loginWithMfaRequired = () => {
    setMfaRequired(true);
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const logout = async () => {
    try {
      await axios.post(`${API}/auth/logout`, {}, { withCredentials: true });
    } catch (error) {
      console.error('Logout error:', error);
    }
    setUser(null);
    setIsAuthenticated(false);
    setAccessToken(null); // Clear access token from memory
    window.__ACCESS_TOKEN__ = null; // Clear global storage
    setMfaRequired(false);
  };

  const refreshAccessToken = useCallback(async () => {
    try {
      const response = await axios.post(`${API}/auth/refresh`, {}, { withCredentials: true });
      const newAccessToken = response.data.access_token;
      setAccessToken(newAccessToken);
      return newAccessToken;
    } catch (error) {
      console.error('Token refresh failed:', error);
      // If refresh fails, force logout
      logout();
      throw error;
    }
  }, [logout]);

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated,
        accessToken,
        mfaRequired,
        login,
        loginWithMfaRequired,
        logout,
        refreshAuth: checkAuth,
        refreshAccessToken
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};