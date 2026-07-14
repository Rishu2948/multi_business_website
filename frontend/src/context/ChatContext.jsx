import { createContext, useContext, useState } from 'react';

const ChatContext = createContext(null);

export const ChatProvider = ({ children }) => {
  const [recommendations, setRecommendations] = useState([]);
  const [preferenceSummary, setPreferenceSummary] = useState({});
  const [isPrime, setIsPrime] = useState(false);

  // Populate all three fields from the POST /api/auth/google login response.
  // The login response shape is:
  // {
  //   "user": { "user_id": "...", "role": "...", "is_prime": false, ... },
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
  };

  // Reset all fields to defaults. Call this on logout.
  const clearChatData = () => {
    setRecommendations([]);
    setPreferenceSummary({});
    setIsPrime(false);
  };

  return (
    <ChatContext.Provider
      value={{
        recommendations,
        preference_summary: preferenceSummary,
        is_prime: isPrime,
        setChatLoginData,
        clearChatData,
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
