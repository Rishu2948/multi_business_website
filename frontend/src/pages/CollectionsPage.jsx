/**
 * CollectionsPage — customer-facing
 * Displays products tagged to a specific collection (Gifting, Festive, etc.)
 * All metadata (title, banner, description) comes from GET /api/collections/:businessId.
 * Products from GET /api/products?collection=:collectionId.
 * Mobile: filter sheet. Desktop: sidebar filter panel.
 */

import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Package, ChevronRight, SlidersHorizontal, X } from 'lucide-react';
import OrderNavbar from '../components/common/OrderNavbar';
import AnnouncementBar from '../components/common/AnnouncementBar';
import FloatingCartBar from '../components/common/FloatingCartBar';
import BakeryFooter from '../components/common/BakeryFooter';
import ProductItemModal from '../components/catalog/ProductItemModal';
import VegNonVegBadge from '../components/catalog/VegNonVegBadge';
import ProductBadge from '../components/catalog/ProductBadge';
import { useCart } from '../context/CartContext';
import apiClient from '../utils/api';

const SORT_OPTIONS = [
  { value: 'sort_order',  label: 'Featured' },
  { value: 'popular',     label: 'Most Popular' },
  { value: 'newest',      label: "What's New" },
  { value: 'price_asc',   label: 'Price: Low to High' },
  { value: 'price_desc',  label: 'Price: High to Low' },
  { value: 'rating',      label: 'Highest Rated' },
];

// ── Filter sidebar/sheet ────────────────────────────────────────────────────

const FilterPanel = ({ filters, onChange, onClose }) => {
  return (
    <div className="p-4">
      {onClose && (
        <div className="flex items-center justify-between mb-4">
          <p className="font-semibold text-[#2C2420]">Filters</p>
          <button onClick={onClose} aria-label="Close filters" className="p-1">
            <X size={18} className="text-[#786A60]" />
          </button>
        </div>
      )}

      {/* Veg/Non-veg */}
      <div className="mb-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-[#786A60] mb-2">Type</p>
        {[
          { label: '● Veg', value: 'veg' },
          { label: '○ Non-Veg', value: 'nonveg' },
          { label: 'All', value: 'all' },
        ].map(opt => (
          <label key={opt.value} className="flex items-center gap-2 py-1.5 cursor-pointer">
            <input
              type="radio"
              name="veg-filter"
              value={opt.value}
              checked={filters.vegFilter === opt.value}
              onChange={() => onChange({ ...filters, vegFilter: opt.value })}
              className="accent-[#4A3B32]"
            />
            <span className="text-sm text-[#2C2420]">{opt.label}</span>
          </label>
        ))}
      </div>

      {/* Price range */}
      <div className="mb-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-[#786A60] mb-2">Price Range</p>
        <div className="flex items-center gap-2">
          <input
            type="number"
            placeholder="Min ₹"
            value={filters.minPrice}
            onChange={e => onChange({ ...filters, minPrice: e.target.value })}
            className="w-full border border-[#E8E0D5] px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#4A3B32]"
            data-testid="min-price-filter"
          />
          <span className="text-[#786A60] text-sm">–</span>
          <input
            type="number"
            placeholder="Max ₹"
            value={filters.maxPrice}
            onChange={e => onChange({ ...filters, maxPrice: e.target.value })}
            className="w-full border border-[#E8E0D5] px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#4A3B32]"
            data-testid="max-price-filter"
          />
        </div>
      </div>

      {/* Rating */}
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-[#786A60] mb-2">Rating</p>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={filters.ratedFour}
            onChange={e => onChange({ ...filters, ratedFour: e.target.checked })}
            className="w-4 h-4 accent-[#4A3B32]"
            data-testid="rated4-filter"
          />
          <span className="text-sm text-[#2C2420]">Rated 4+</span>
        </label>
      </div>
    </div>
  );
};

// ── Product grid card ────────────────────────────────────────────────────────

const CollectionProductCard = ({ product, onAddClick }) => (
  <motion.div
    initial={{ opacity: 0, y: 16 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true }}
    transition={{ duration: 0.5 }}
    className="group bg-white border border-[#E8E0D5]"
    data-testid={`collection-product-${product.product_id}`}
  >
    <div className="relative aspect-square overflow-hidden">
      {product.images?.[0]?.url ? (
        <img
          src={product.images[0].url}
          alt={product.product_name}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
          loading="lazy"
        />
      ) : (
        <div className="w-full h-full bg-[#F3EFEA] flex items-center justify-center">
          <Package size={32} className="text-[#786A60]" strokeWidth={1.5} aria-hidden="true" />
        </div>
      )}
      <div className="absolute top-2 left-2 flex flex-col gap-1">
        <VegNonVegBadge isVeg={product.is_veg} />
        <ProductBadge product={product} />
      </div>
    </div>
    <div className="p-3">
      <h3 className="font-serif text-sm text-[#2C2420] line-clamp-2 mb-1">{product.product_name}</h3>
      {product.description && (
        <p className="text-xs text-[#786A60] line-clamp-1 mb-2">{product.description}</p>
      )}
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-[#2C2420]">₹{product.base_price?.toLocaleString()}</p>
        <button
          onClick={() => onAddClick(product)}
          className="bg-white border border-[#D4A373] text-[#4A3B32] text-xs font-bold
                     px-3 py-1.5 hover:bg-[#FAF8F5] transition-colors min-h-[32px]"
          aria-label={`Add ${product.product_name}`}
          data-testid={`col-add-${product.product_id}`}
        >
          ADD +
        </button>
      </div>
    </div>
  </motion.div>
);

// ── Main page ────────────────────────────────────────────────────────────────

const CollectionsPage = () => {
  const { businessId, collectionId } = useParams();
  const { addToCart } = useCart();

  const [collection, setCollection] = useState(null);
  const [business, setBusiness] = useState(null);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState('sort_order');
  const [filterSheetOpen, setFilterSheetOpen] = useState(false);
  const [filters, setFilters] = useState({ vegFilter: 'all', minPrice: '', maxPrice: '', ratedFour: false });
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [bizRes, colsRes] = await Promise.all([
          apiClient.get(`/businesses/${businessId}`),
          apiClient.get(`/collections/${businessId}`),
        ]);
        setBusiness(bizRes.data);
        const col = (colsRes.data.collections || []).find(c => c.collection_id === collectionId);
        setCollection(col || { display_name: collectionId, description: '' });
      } catch {
        setCollection({ display_name: collectionId, description: '' });
      }
    };
    fetchAll();
  }, [businessId, collectionId]);

  useEffect(() => {
    const fetchProducts = async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams({
          business_id: businessId,
          collection: collectionId,
          sort_by: sortBy,
          limit: 100,
        });
        if (filters.vegFilter === 'veg') params.set('is_veg', 'true');
        if (filters.vegFilter === 'nonveg') params.set('is_veg', 'false');
        if (filters.minPrice) params.set('min_price', filters.minPrice);
        if (filters.maxPrice) params.set('max_price', filters.maxPrice);
        if (filters.ratedFour) params.set('min_rating', '4');

        const r = await apiClient.get(`/products?${params}`);
        setProducts(r.data.products || []);
      } catch {
        setProducts([]);
      } finally {
        setLoading(false);
      }
    };
    fetchProducts();
  }, [businessId, collectionId, sortBy, filters]);

  const handleAddClick = product => {
    if (product.addons?.length > 0) {
      setSelectedProduct(product);
      setModalOpen(true);
    } else {
      addToCart(product.product_id, null, 1);
    }
  };

  const handleModalAdd = async (product, selectedAddons) => {
    await addToCart(product.product_id, null, 1, selectedAddons);
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5]">
      <AnnouncementBar businessId={businessId} />
      <OrderNavbar businessId={businessId} business={business} />

      {/* Breadcrumb */}
      <div className="px-4 md:px-8 py-3 border-b border-[#E8E0D5] bg-white">
        <nav className="text-xs text-[#786A60] flex items-center gap-1.5 max-w-7xl mx-auto" aria-label="Breadcrumb">
          <Link to={`/business/${businessId}`} className="hover:text-[#4A3B32]">Home</Link>
          <ChevronRight size={12} />
          <Link to={`/business/${businessId}/catalog`} className="hover:text-[#4A3B32]">Products</Link>
          <ChevronRight size={12} />
          <span className="text-[#2C2420] font-medium capitalize">{collection?.display_name}</span>
        </nav>
      </div>

      {/* Collection hero */}
      {collection && (
        <section className="bg-white py-8 px-4 md:px-8 border-b border-[#E8E0D5]"
                 data-testid="collection-hero">
          <div className="max-w-7xl mx-auto">
            {collection.banner_image_url && (
              <div className="flex justify-center mb-6">
                <img src={collection.banner_image_url} alt={collection.display_name}
                  className="w-24 h-24 object-contain" />
              </div>
            )}
            <h1 className="font-serif text-3xl md:text-4xl text-[#2C2420] text-center uppercase tracking-wide mb-2">
              {collection.display_name}
            </h1>
            {/* decorative divider */}
            <div className="flex items-center justify-center gap-2 mb-4">
              <span className="text-[#D4A373]">✦</span>
              <span className="text-[#D4A373]">✦</span>
              <span className="text-[#D4A373]">✦</span>
            </div>
            {collection.description && (
              <p className="text-sm text-[#786A60] text-center max-w-lg mx-auto leading-relaxed">
                {collection.description}
              </p>
            )}
          </div>
        </section>
      )}

      {/* Main content */}
      <div className="flex flex-1 max-w-7xl mx-auto w-full px-4 md:px-8 py-6 gap-6">

        {/* Desktop filter sidebar */}
        <aside className="hidden lg:block w-52 flex-shrink-0">
          <div className="bg-white border border-[#E8E0D5] sticky top-[130px]">
            <p className="text-xs font-semibold uppercase tracking-wide text-[#786A60] px-4 pt-4 pb-2 border-b border-[#E8E0D5]">
              FILTERS
            </p>
            <FilterPanel filters={filters} onChange={setFilters} />
          </div>
        </aside>

        {/* Product grid */}
        <main className="flex-1" data-testid="collection-products">
          {/* Toolbar */}
          <div className="flex items-center justify-between mb-5 gap-3 flex-wrap">
            {/* Mobile filter button */}
            <button
              onClick={() => setFilterSheetOpen(true)}
              className="lg:hidden flex items-center gap-2 border border-[#E8E0D5] px-3 py-2 text-sm text-[#4A3B32]"
              data-testid="open-filter-sheet"
            >
              <SlidersHorizontal size={14} />
              Filters
            </button>

            <p className="text-sm text-[#786A60]">{products.length} items</p>

            <select
              value={sortBy}
              onChange={e => setSortBy(e.target.value)}
              className="border border-[#E8E0D5] px-3 py-2 text-sm bg-white
                         focus:outline-none focus:ring-1 focus:ring-[#4A3B32]"
              aria-label="Sort products"
              data-testid="sort-select"
            >
              {SORT_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-24">
              <div className="w-8 h-8 border-4 border-[#4A3B32] border-t-transparent rounded-full animate-spin" />
            </div>
          ) : products.length === 0 ? (
            <div className="text-center py-24">
              <Package size={40} className="mx-auto text-[#786A60] mb-3" strokeWidth={1} aria-hidden="true" />
              <p className="font-serif text-lg text-[#786A60]">No products found.</p>
              <Link to={`/business/${businessId}/catalog`} className="mt-3 inline-block text-sm text-[#4A3B32] underline">
                Browse all products
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
              {products.map(product => (
                <CollectionProductCard
                  key={product.product_id}
                  product={product}
                  onAddClick={handleAddClick}
                />
              ))}
            </div>
          )}
        </main>
      </div>

      {/* Mobile filter bottom sheet */}
      {filterSheetOpen && (
        <>
          <div
            className="fixed inset-0 bg-black/40 z-40"
            onClick={() => setFilterSheetOpen(false)}
            aria-hidden="true"
          />
          <div className="fixed bottom-0 left-0 right-0 bg-white z-50 rounded-t-2xl max-h-[80vh] overflow-y-auto shadow-xl">
            <div className="w-10 h-1 bg-[#E8E0D5] rounded-full mx-auto mt-3 mb-1" />
            <FilterPanel
              filters={filters}
              onChange={newFilters => { setFilters(newFilters); }}
              onClose={() => setFilterSheetOpen(false)}
            />
            <div className="px-4 pb-6 pb-[calc(24px+env(safe-area-inset-bottom))]">
              <button
                onClick={() => setFilterSheetOpen(false)}
                className="w-full bg-[#4A3B32] text-white py-3 text-sm font-semibold"
                data-testid="apply-filters-btn"
              >
                Apply Filters
              </button>
            </div>
          </div>
        </>
      )}

      <ProductItemModal
        product={selectedProduct}
        isOpen={modalOpen}
        onClose={() => { setModalOpen(false); setSelectedProduct(null); }}
        onAddToCart={handleModalAdd}
      />

      <FloatingCartBar />
      <BakeryFooter />
    </div>
  );
};

export default CollectionsPage;
