import { createContext, useContext, useState } from 'react';
import apiClient from '../utils/api';

const ChatContext = createContext(null);

export const ChatProvider = ({ children }) => {
  const [recommendations, setRecommendations] = useState([]);
  const [preferenceSummary, setPreferenceSummary] = useState({});
  const [isPrime, setIsPrime] = useState(false);
  const [primeMemberships, setPrimeMemberships] = useState([]);
  const [businessFeatures, setBusinessFeatures] = useState({});

  // Populate all fields from the POST /api/auth/google login response.
  // The login response shape is:
  // {
  //   "user": { "user_id": "...", "role": "...", "is_prime": false, "prime_memberships": [...], ... },
  //   "recommendations": ["prod_id_1", "prod_id_2"],
  //   "preference_summary": { "top_flavors": [...], "top_occasions": [...], "price_range": {...} },
  //   "message": "Login successful"
  // }
  // IMPORTANT: Data is stored in React state only — NEVER written to localStorage or
  // sessionStorage to prevent XSS exposure (Req 10.7).
  const setChatLoginData = (loginResponse) => {
    setRecommendations(loginResponse?.recommendations ?? []);
    setPreferenceSummary(loginResponse?.preference_summary ?? {});
    setIsPrime(loginResponse?.user?.is_prime ?? false);
    setPrimeMemberships(loginResponse?.user?.prime_memberships ?? []);
  };

  // Reset all fields to defaults. Call this on logout.
  const clearChatData = () => {
    setRecommendations([]);
    setPreferenceSummary({});
    setIsPrime(false);
    setPrimeMemberships([]);
    setBusinessFeatures({});
  };

  // Fetch business Prime features directly from API
  const fetchBusinessFeatures = async (businessId) => {
    try {
      const response = await apiClient.get(`/prime/upgrade-info/${businessId}`);
      setBusinessFeatures(prev => ({
        ...prev,
        [businessId]: response.data.enabled_features || []
      }));
      return response.data.enabled_features || [];
    } catch (err) {
      console.error('Error fetching business features:', err);
      return [];
    }
  };

  // Check if user has Prime access for a specific business and feature
  const hasPrimeFeature = (businessId, featureKey) => {
    const membership = primeMemberships.find(m => m.business_id === businessId);
    if (!membership || membership.status !== 'active') return false;

    // Check if feature is enabled in business config (from cached data or membership data)
    const enabledFeatures = businessFeatures[businessId] || membership.enabled_features || [];
    return enabledFeatures.includes(featureKey);
  };

  // Check if user has any active Prime membership for a business
  const hasPrimeMembership = (businessId) => {
    const membership = primeMemberships.find(m => m.business_id === businessId);
    return membership?.status === 'active';
  };

  return (
    <ChatContext.Provider
      value={{
        recommendations,
        preference_summary: preferenceSummary,
        is_prime: isPrime,
        prime_memberships: primeMemberships,
        setChatLoginData,
        clearChatData,
        hasPrimeFeature,
        hasPrimeMembership,
        fetchBusinessFeatures,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
};

export const useChatContext = () => {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChatContext must be used within ChatProvider');
  }
  return context;
};
