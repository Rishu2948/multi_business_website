import { Link } from 'react-router-dom';
import { Package, Star } from 'lucide-react';

/**
 * Compact product card for the AI chatbot panel.
 *
 * Props:
 *   product    – { product_id, product_name, base_price, images, avg_rating, rationale? }
 *   businessId – string, used to build the catalog deep-link
 *   onNavigate – optional callback to close the chat panel before navigating
 */
const ProductCard = ({ product, businessId, onNavigate }) => {
  const {
    product_id,
    product_name,
    base_price,
    images,
    avg_rating,
    rationale,
  } = product;

  const thumbnailUrl = images?.[0]?.url;
  const roundedRating = Math.round(avg_rating ?? 0);

  return (
    <div
      className="flex gap-3 p-3 bg-[#FAF8F5] border border-[#E8E0D5] rounded-sm hover:border-[#D4A373] transition-colors duration-200"
      data-testid={`chatbot-product-card-${product_id}`}
    >
      {/* Thumbnail */}
      <div className="flex-shrink-0 w-16 h-16 overflow-hidden bg-[#F3EFEA] rounded-sm">
        {thumbnailUrl ? (
          <img
            src={thumbnailUrl}
            alt={product_name}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Package size={22} className="text-[#786A60]" strokeWidth={1.5} />
          </div>
        )}
      </div>

      {/* Details */}
      <div className="flex flex-col justify-between flex-1 min-w-0">
        {/* Name */}
        <p
          className="font-serif text-sm text-[#2C2420] leading-snug line-clamp-2"
          title={product_name}
        >
          {product_name}
        </p>

        {/* Stars */}
        {avg_rating != null && avg_rating > 0 && (
          <div className="flex items-center gap-0.5 mt-1">
            {[1, 2, 3, 4, 5].map((s) => (
              <Star
                key={s}
                size={10}
                className={
                  s <= roundedRating
                    ? 'fill-[#D4A373] text-[#D4A373]'
                    : 'text-[#E8E0D5] fill-[#E8E0D5]'
                }
              />
            ))}
            <span className="text-[10px] text-[#786A60] ml-1">{avg_rating}</span>
          </div>
        )}

        {/* Price + CTA */}
        <div className="flex items-center justify-between mt-1.5 gap-2">
          <span className="text-xs font-semibold text-[#2C2420]">
            ₹{base_price.toLocaleString()}
          </span>
          <Link
            to={`/business/${businessId}/catalog?product=${product_id}`}
            onClick={onNavigate}
            className="flex-shrink-0 text-[10px] tracking-[0.12em] uppercase font-semibold text-[#4A3B32] border border-[#4A3B32] px-2.5 py-1 hover:bg-[#4A3B32] hover:text-white transition-colors duration-200 whitespace-nowrap"
            data-testid={`chatbot-view-product-${product_id}`}
          >
            View Product
          </Link>
        </div>

        {/* Rationale (shown for recommend intent) */}
        {rationale && (
          <p className="text-[10px] italic text-[#786A60] mt-1.5 leading-relaxed line-clamp-2">
            {rationale}
          </p>
        )}
      </div>
    </div>
  );
};

export default ProductCard;
