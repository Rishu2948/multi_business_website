/**
 * CategoryChipStrip
 * Mobile / tablet horizontal scrollable category pills.
 * Sticky below the navbar on small screens.
 * Data API-driven — same categories array as the sidebar.
 */

import { useRef, useEffect } from 'react';

const CategoryChipStrip = ({ categories, activeCategory, onCategoryClick }) => {
  const stripRef = useRef(null);

  // Auto-scroll the active chip into view when it changes
  useEffect(() => {
    if (!stripRef.current || !activeCategory) return;
    const active = stripRef.current.querySelector(`[data-cat="${activeCategory}"]`);
    if (active) {
      active.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
    }
  }, [activeCategory]);

  if (!categories || categories.length === 0) return null;

  // Only show top-level categories (no sub-categories in strip)
  const topLevel = categories.filter(c => !c.parent_category_id);

  return (
    <div
      ref={stripRef}
      className="flex gap-2 overflow-x-auto scrollbar-hide px-4 py-2 bg-white border-b border-[#E8E0D5]"
      role="navigation"
      aria-label="Product categories"
      data-testid="category-chip-strip"
    >
      {topLevel.map(cat => (
        <button
          key={cat.category_id}
          data-cat={cat.category_id}
          onClick={() => onCategoryClick(cat.category_id)}
          className={`flex-shrink-0 flex items-center gap-1.5 px-4 py-1.5 rounded-full
            text-sm font-medium border transition-colors duration-150
            min-h-[36px] touch-manipulation
            ${activeCategory === cat.category_id
              ? 'bg-[#4A3B32] text-white border-[#4A3B32]'
              : 'bg-white text-[#4A3B32] border-[#E8E0D5] hover:border-[#4A3B32]'
            }`}
          aria-pressed={activeCategory === cat.category_id}
          data-testid={`chip-${cat.category_id}`}
        >
          {cat.icon_emoji && <span aria-hidden="true">{cat.icon_emoji}</span>}
          <span>{cat.display_name}</span>
          {cat.product_count > 0 && (
            <span className={`text-[10px] tabular-nums ${
              activeCategory === cat.category_id ? 'text-white/70' : 'text-[#786A60]'
            }`}>
              {cat.product_count}
            </span>
          )}
        </button>
      ))}
    </div>
  );
};

export default CategoryChipStrip;
