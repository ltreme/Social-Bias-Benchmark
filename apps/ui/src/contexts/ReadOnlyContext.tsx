import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../lib/apiClient';

interface ReadOnlyContextType {
  isReadOnly: boolean;
  isLoading: boolean;
}

const ReadOnlyContext = createContext<ReadOnlyContextType>({
  isReadOnly: false,
  isLoading: true,
});

export const useReadOnly = () => {
  const context = useContext(ReadOnlyContext);
  if (!context) {
    throw new Error('useReadOnly must be used within ReadOnlyProvider');
  }
  return context;
};

export const ReadOnlyProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isReadOnly, setIsReadOnly] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await api.get<{ read_only_mode: boolean }>('/config');
        setIsReadOnly(response.data.read_only_mode);
      } catch (error) {
        console.error('Failed to fetch application config:', error);
        // Default to read-only on error for safety
        setIsReadOnly(false);
      } finally {
        setIsLoading(false);
      }
    };

    fetchConfig();
  }, []);

  return (
    <ReadOnlyContext.Provider value={{ isReadOnly, isLoading }}>
      {children}
    </ReadOnlyContext.Provider>
  );
};
