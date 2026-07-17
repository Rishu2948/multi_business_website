/**
 * AnnouncementBar
 * Fetches active announcement from GET /api/announcements/:businessId.
 * Dismissible — dismissed state persisted in localStorage keyed by announcement_id.
 * Renders nothing if no active announcement or already dismissed.
 */

import { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import apiClient from '../../utils/api';

const AnnouncementBar = ({ businessId }) => {
  const [announcement, setAnnouncement] = useState(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!businessId) return;
    apiClient.get(`/announcements/${businessId}`)
      .then(res => {
        const ann = res.data?.announcement;
        if (!ann) return;
        const key = `ann_dismissed_${ann.announcement_id}`;
        if (localStorage.getItem(key)) {
          setDismissed(true);
        }
        setAnnouncement(ann);
      })
      .catch(() => {});
  }, [businessId]);

  const handleDismiss = () => {
    if (announcement) {
      localStorage.setItem(`ann_dismissed_${announcement.announcement_id}`, '1');
    }
    setDismissed(true);
  };

  if (!announcement || dismissed) return null;

  const bgColor = announcement.bg_color || '#4A3B32';
  const textColor = announcement.text_color || '#FAF8F5';

  return (
    <div
      style={{ backgroundColor: bgColor, color: textColor }}
      className="text-xs py-2 px-4 text-center relative"
      role="banner"
      data-testid="announcement-bar"
    >
      <span>
        {announcement.message}
        {announcement.link_url && (
          <a
            href={announcement.link_url}
            className="underline ml-1 font-semibold"
            style={{ color: textColor }}
            data-testid="announcement-link"
          >
            {announcement.link_text || 'Learn more'}
          </a>
        )}
      </span>

      <button
        onClick={handleDismiss}
        className="absolute right-3 top-1/2 -translate-y-1/2 p-1 opacity-70 hover:opacity-100"
        aria-label="Dismiss announcement"
        style={{ color: textColor }}
        data-testid="announcement-dismiss"
      >
        <X size={12} />
      </button>
    </div>
  );
};

export default AnnouncementBar;
