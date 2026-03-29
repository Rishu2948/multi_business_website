import { createContext, useContext, useState } from 'react';

const BusinessContext = createContext(null);

export const BusinessProvider = ({ children }) => {
  const [selectedBusiness, setSelectedBusiness] = useState(null);

  return (
    <BusinessContext.Provider
      value={{
        selectedBusiness,
        setSelectedBusiness
      }}
    >
      {children}
    </BusinessContext.Provider>
  );
};

export const useBusiness = () => {
  const context = useContext(BusinessContext);
  if (!context) {
    throw new Error('useBusiness must be used within BusinessProvider');
  }
  return context;
};