/**
 * OrderProductCard
 * Horizontal product card used in the order catalog (Theobroma-style).
 * Desktop & Mobile: image on right, text on left, ADD+ button overlaid on image.
 */

import { Package } from 'lucide-react';
import VegNonVegBadge from './VegNonVegBadge';
import ProductBadge from './ProductBadge';

const OrderProductCard = ({ product, onAddClick }) => {
  const hasAddons = product.addons && product.addons.length > 0;

  return (
    <div
      className="flex items-start gap-3 py-4 border-b border-[#E8E0D5] last:border-0"
      data-testid={`order-product-card-${product.product_id}`}
    >
      {/* Left: text */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <VegNonVegBadge isVeg={product.is_veg} />
          <ProductBadge product={product} />
        </div>

        <h3 className="font-medium text-[#2C2420] text-sm leading-snug line-clamp-2">
          {product.product_name}
        </h3>

        {product.description && (
          <p className="text-xs text-[#786A60] mt-0.5 line-clamp-2 leading-relaxed">
            {product.description}
          </p>
        )}

        {product.allergens && product.allergens.length > 0 && (
          <p className="text-[10px] text-[#786A60] mt-0.5">
            Allergens: {product.allergens.join(', ')}
          </p>
        )}

        <div className="flex items-center gap-2 mt-2">
          <p className="text-sm font-semibold text-[#2C2420]">
            ₹{product.base_price?.toLocaleString()}
          </p>
          {hasAddons && (
            <span className="text-[10px] text-[#786A60]">Customisable</span>
          )}
        </div>
      </div>

      {/* Right: image + ADD button */}
      <div className="relative w-20 h-20 flex-shrink-0 sm:w-24 sm:h-24">
        {product.images?.[0]?.url ? (
          <img
            src={product.images[0].url}
            alt={product.product_name}
            className="w-full h-full object-cover rounded-sm"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full bg-[#F3EFEA] rounded-sm flex items-center justify-center">
            <Package size={20} className="text-[#786A60]" strokeWidth={1.5} aria-hidden="true" />
          </div>
        )}

        <button
          onClick={() => onAddClick(product)}
          className="absolute -bottom-2 left-1/2 -translate-x-1/2
                     bg-white border border-[#D4A373] text-[#4A3B32]
                     text-xs font-bold px-3 py-1 shadow-sm
                     hover:bg-[#FAF8F5] transition-colors
                     min-w-[52px] min-h-[28px]"
          aria-label={`Add ${product.product_name} to cart`}
          data-testid={`add-${product.product_id}`}
        >
          ADD +
        </button>
      </div>
    </div>
  );
};

export default OrderProductCard;
