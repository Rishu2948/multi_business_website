/**
 * ProductFiltersBar
 * Horizontal pill row for quick product filtering.
 * Filters apply client-side against API product fields.
 * Mobile: horizontal scroll, no wrap.
 * Desktop: inline flex row.
 */

import { useState, useRef } from 'react';
import { Search, X } from 'lucide-react';

const FILTERS = [
  { id: 'veg',       label: '● Veg' },
  { id: 'nonveg',    label: '○ Non-Veg' },
  { id: 'bestseller',label: '★ Bestseller' },
  { id: 'on_offer',  label: '% On Offer' },
  { id: 'new',       label: '✦ What\'s New' },
  { id: 'rated4',    label: '⭐ Rated 4+' },
];

const ProductFiltersBar = ({ activeFilters, onFilterToggle, searchQuery, onSearchChange }) => {
  const [searchOpen, setSearchOpen] = useState(false);
  const searchRef = useRef(null);

  const handleSearchToggle = () => {
    setSearchOpen(prev => {
      if (!prev) setTimeout(() => searchRef.current?.focus(), 50);
      return !prev;
    });
    if (searchOpen) onSearchChange('');
  };

  return (
    <div
      className="bg-white border-b border-[#E8E0D5] px-4 py-2"
      data-testid="product-filters-bar"
    >
      <div className="flex items-center gap-2 overflow-x-auto scrollbar-hide">
        {/* Search pill */}
        <div className="flex-shrink-0 flex items-center">
          {searchOpen ? (
            <div className="flex items-center border border-[#4A3B32] rounded-full px-3 py-1.5 gap-2 bg-white">
              <Search size={13} className="text-[#786A60]" />
              <input
                ref={searchRef}
                type="text"
                value={searchQuery}
                onChange={e => onSearchChange(e.target.value)}
                placeholder="Search menu..."
                className="text-sm text-[#2C2420] outline-none bg-transparent w-36"
                data-testid="menu-search-input"
                aria-label="Search menu items"
              />
              <button onClick={handleSearchToggle} aria-label="Clear search">
                <X size={13} className="text-[#786A60]" />
              </button>
            </div>
          ) : (
            <button
              onClick={handleSearchToggle}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-[#E8E0D5]
                         text-sm text-[#4A3B32] hover:border-[#4A3B32] transition-colors min-h-[36px]"
              aria-label="Open search"
              data-testid="open-search-btn"
            >
              <Search size={13} />
              <span className="hidden sm:inline">Search</span>
            </button>
          )}
        </div>

        {/* Filter pills */}
        {FILTERS.map(filter => {
          const active = activeFilters.includes(filter.id);
          return (
            <button
              key={filter.id}
              onClick={() => onFilterToggle(filter.id)}
              className={`flex-shrink-0 px-3 py-1.5 rounded-full text-sm font-medium border
                transition-colors duration-150 min-h-[36px] touch-manipulation
                ${active
                  ? 'bg-[#4A3B32] text-white border-[#4A3B32]'
                  : 'bg-white text-[#4A3B32] border-[#E8E0D5] hover:border-[#4A3B32]'
                }`}
              aria-pressed={active}
              data-testid={`filter-${filter.id}`}
            >
              {filter.label}
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default ProductFiltersBar;
