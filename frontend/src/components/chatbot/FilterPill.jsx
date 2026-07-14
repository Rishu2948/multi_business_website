import React from 'react';
import { X } from 'lucide-react';

/**
 * FilterPill — a dismissible pill tag representing a single active chat filter.
 *
 * Renders a <button> element so it is natively keyboard-activatable and
 * screen-reader discoverable without additional ARIA roles. (Req 1.4, WCAG 2.1 AA)
 *
 * Props:
 *   filterKey   {string} — filter key, e.g. "price_max" or "flavor"
 *   filterValue {string|number} — current value, e.g. 500 or "chocolate"
 *   onRemove    {function} — callback fired with filterKey when the pill is dismissed
 *
 * Requirements: 3.6, 3.7, 1.4
 */
const FilterPill = ({ filterKey, filterValue, onRemove }) => {
  const handleClick = () => {
    if (typeof onRemove === 'function') {
      onRemove(filterKey);
    }
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      aria-label={`Remove ${filterKey} filter`}
      data-testid={`filter-pill-${filterKey}`}
      className={[
        // Layout
        'inline-flex items-center gap-1.5',
        'px-3 py-1',
        // Shape — squared corners per design guidelines
        'rounded-none',
        // Colour palette: warm brown surface + text
        'bg-[#F3EFEA] text-[#4A3B32]',
        'border border-[#E8E0D5]',
        // Typography
        'text-xs font-semibold font-sans uppercase tracking-wide',
        // Interactive states
        'hover:bg-[#E8E0D5] hover:border-[#4A3B32]',
        'focus:outline-none focus:ring-1 focus:ring-[#4A3B32]',
        'transition-colors duration-200',
        'cursor-pointer',
      ].join(' ')}
    >
      {/* Filter label */}
      <span>{filterKey}: {filterValue}</span>

      {/* Dismiss icon — hidden from assistive tech; the button aria-label is sufficient */}
      <X
        size={12}
        strokeWidth={2.5}
        aria-hidden="true"
        className="text-[#786A60]"
      />
    </button>
  );
};

export default FilterPill;
