import React from 'react';

/**
 * ComparisonTable — renders a side-by-side product comparison table.
 *
 * Props:
 *   products              — array of Product_Result objects (max 4)
 *   attributes            — array of attribute key strings to compare as rows (max 4)
 *   missing_product_names — array of product name strings that didn't resolve (partial-success)
 *
 * Requirements: 7.4
 */
const ComparisonTable = ({ products = [], attributes = [], missing_product_names = [] }) => {
  // Enforce max 4 products and max 4 attribute rows as per spec (7.4, design doc)
  const displayProducts = products.slice(0, 4);
  const displayAttributes = attributes.slice(0, 4);

  if (displayProducts.length === 0) return null;

  /**
   * Resolve a cell value for a given product and attribute key.
   * Priority:
   *   1. product.attributes?.[attr]  — structured attributes object
   *   2. product[attr]               — top-level standard fields
   */
  const getCellValue = (product, attr) => {
    // 1. Look inside the nested attributes object first
    const nested = product.attributes?.[attr];
    if (nested !== undefined && nested !== null && nested !== '') {
      return nested;
    }

    // 2. Fall back to top-level field (standard fields: base_price, avg_rating, description, etc.)
    const topLevel = product[attr];
    if (topLevel !== undefined && topLevel !== null && topLevel !== '') {
      return topLevel;
    }

    return '—';
  };

  /**
   * Format a raw value for display based on attribute key:
   *   base_price  → ₹{value.toLocaleString('en-IN')}
   *   avg_rating  → ⭐ {value}
   *   anything else → string coercion
   */
  const formatValue = (attr, value) => {
    if (value === '—') return value;

    if (attr === 'base_price') {
      const num = Number(value);
      if (!Number.isNaN(num)) {
        return `₹${num.toLocaleString('en-IN')}`;
      }
    }

    if (attr === 'avg_rating') {
      const num = Number(value);
      if (!Number.isNaN(num)) {
        return `⭐ ${num}`;
      }
    }

    return String(value);
  };

  /**
   * Human-readable label for an attribute key.
   * Converts snake_case / camelCase to Title Case for display.
   */
  const formatAttributeLabel = (attr) => {
    return attr
      .replace(/_/g, ' ')
      .replace(/([a-z])([A-Z])/g, '$1 $2')
      .replace(/\b\w/g, (c) => c.toUpperCase());
  };

  return (
    <div
      className="w-full mt-3"
      data-testid="comparison-table-wrapper"
    >
      {/* Horizontally scrollable container for small screens (Req 7.4) */}
      <div className="overflow-x-auto">
        <table
          className="w-full border-collapse text-sm"
          aria-label="Product comparison table"
          data-testid="comparison-table"
        >
          {/* Column headers — product names */}
          <thead>
            <tr>
              {/* Empty top-left cell above the attribute label column */}
              <th
                scope="col"
                className="py-2 px-3 text-left text-xs uppercase tracking-widest text-[#786A60] font-semibold bg-[#F3EFEA] border-b border-[#E8E0D5] min-w-[100px]"
                aria-label="Attribute"
              >
                Attribute
              </th>

              {displayProducts.map((product) => (
                <th
                  key={product.product_id}
                  scope="col"
                  className="py-2 px-3 text-left font-serif text-[#2C2420] text-sm font-semibold bg-[#F3EFEA] border-b border-l border-[#E8E0D5] min-w-[140px]"
                  data-testid={`comparison-col-header-${product.product_id}`}
                >
                  {product.product_name}
                </th>
              ))}
            </tr>
          </thead>

          {/* Attribute rows */}
          <tbody>
            {displayAttributes.map((attr, rowIdx) => (
              <tr
                key={attr}
                className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-[#FAF8F5]'}
                data-testid={`comparison-row-${attr}`}
              >
                {/* Row label */}
                <th
                  scope="row"
                  className="py-2 px-3 text-left text-xs font-semibold uppercase tracking-wide text-[#786A60] border-b border-[#E8E0D5] whitespace-nowrap"
                  data-testid={`comparison-row-label-${attr}`}
                >
                  {formatAttributeLabel(attr)}
                </th>

                {/* One cell per product */}
                {displayProducts.map((product) => {
                  const raw = getCellValue(product, attr);
                  const display = formatValue(attr, raw);

                  return (
                    <td
                      key={`${product.product_id}-${attr}`}
                      className="py-2 px-3 text-[#2C2420] border-b border-l border-[#E8E0D5] align-top"
                      data-testid={`comparison-cell-${product.product_id}-${attr}`}
                    >
                      {display}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Partial-success note — shown when some product names could not be resolved (Req 7.4) */}
      {missing_product_names.length > 0 && (
        <p
          className="mt-2 text-xs text-[#786A60] font-sans"
          data-testid="comparison-missing-products-note"
          role="status"
          aria-live="polite"
        >
          <span className="font-semibold text-[#4A3B32]">Could not find:</span>{' '}
          {missing_product_names.join(', ')}
        </p>
      )}
    </div>
  );
};

export default ComparisonTable;
