/**
 * ProductBadge
 * Quality badges shown on product cards.
 * Priority: Best Seller > Highly Ordered > On Offer > New
 * All data comes from API fields — no hardcoded thresholds in display logic.
 */

const BADGE_STYLES = {
  bestseller: 'bg-orange-500 text-white',
  highly_ordered: 'bg-teal-600 text-white',
  on_offer: 'bg-[#D4A373] text-white',
  new: 'bg-[#A3B18A] text-white',
};

const ProductBadge = ({ product }) => {
  if (!product) return null;

  // is_bestseller and total_ordered come directly from the API
  if (product.is_bestseller) {
    return (
      <span
        className={`inline-block text-[10px] px-2 py-0.5 font-semibold tracking-wide ${BADGE_STYLES.bestseller}`}
        data-testid="badge-bestseller"
      >
        ★ Best Seller
      </span>
    );
  }

  if (product.total_ordered > 100) {
    return (
      <span
        className={`inline-block text-[10px] px-2 py-0.5 font-semibold tracking-wide ${BADGE_STYLES.highly_ordered}`}
        data-testid="badge-highly-ordered"
      >
        🔥 Highly Ordered
      </span>
    );
  }

  if (product.has_active_offer) {
    return (
      <span
        className={`inline-block text-[10px] px-2 py-0.5 font-semibold tracking-wide ${BADGE_STYLES.on_offer}`}
        data-testid="badge-on-offer"
      >
        % On Offer
      </span>
    );
  }

  // "New" — within 30 days of created_at
  if (product.created_at) {
    const createdAt = new Date(product.created_at);
    const diffDays = (Date.now() - createdAt.getTime()) / (1000 * 60 * 60 * 24);
    if (diffDays <= 30) {
      return (
        <span
          className={`inline-block text-[10px] px-2 py-0.5 font-semibold tracking-wide ${BADGE_STYLES.new}`}
          data-testid="badge-new"
        >
          ✦ New
        </span>
      );
    }
  }

  return null;
};

export default ProductBadge;
