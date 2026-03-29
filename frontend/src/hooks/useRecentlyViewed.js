import { useState, useCallback } from 'react';

const STORAGE_KEY = 'jain_recently_viewed';
const MAX_ITEMS = 10;

export const useRecentlyViewed = () => {
  const [viewedIds, setViewedIds] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  const trackView = useCallback((productId) => {
    setViewedIds(prev => {
      const filtered = prev.filter(id => id !== productId);
      const updated = [productId, ...filtered].slice(0, MAX_ITEMS);
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      } catch { /* ignore */ }
      return updated;
    });
  }, []);

  return { viewedIds, trackView };
};
