import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, Link, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import Marquee from 'react-fast-marquee';
import useSWR, { mutate } from 'swr';

import OrderNavbar from '../components/common/OrderNavbar';
import BakeryFooter from '../components/common/BakeryFooter';
import AnnouncementBar from '../components/common/AnnouncementBar';
import FloatingCartBar from '../components/common/FloatingCartBar';
import ChatWidget from '../components/chatbot/ChatWidget';
import CategorySidebar from '../components/catalog/CategorySidebar';
import CategoryChipStrip from '../components/catalog/CategoryChipStrip';
import ProductFiltersBar from '../components/catalog/ProductFiltersBar';
import OrderProductCard from '../components/catalog/OrderProductCard';
import ProductItemModal from '../components/catalog/ProductItemModal';

import { useCart } from '../context/CartContext';
import { useRecentlyViewed } from '../hooks/useRecentlyViewed';
import { useChatContext } from '../context/ChatContext';
import apiClient from '../utils/api';
import { Loader2, Package, Star, TrendingUp, Clock, Sparkles, Menu as MenuIcon } from 'lucide-react';

// ── Small shared components ────────────────────────────────────────────────

const StarDisplay = ({ rating, count }) => (
  <div className="flex items-center gap-1.5">
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map(s => (
        <Star key={s} size={11}
          className={s <= Math.round(rating) ? 'fill-[#D4A373] text-[#D4A373]' : 'text-[#E8E0D5]'}
        />
      ))}
    </div>
    <span className="text-xs font-medium text-[#2C2420]">{rating}</span>
    {count > 0 && <span className="text-xs text-[#786A60]">({count})</span>}
  </div>
);

const SectionHeader = ({ icon: Icon, title, subtitle, iconBg = 'bg-[#4A3B32]' }) => (
  <div className="flex items-center gap-4 mb-8">
    <div className={`w-9 h-9 ${iconBg} flex items-center justify-center flex-shrink-0`}>
      <Icon size={16} className="text-white" strokeWidth={1.5} />
    </div>
    <div>
      <h2 className="font-serif text-xl md:text-2xl text-[#2C2420]">{title}</h2>
      <p className="text-xs tracking-[0.15em] uppercase text-[#D4A373] font-semibold mt-0.5">{subtitle}</p>
    </div>
  </div>
);

// Compact card used in trending/recommended/recently-viewed sections
const CompactCard = ({ product, onAddClick, rankBadge, testIdPrefix }) => (
  <div className="group" data-testid={`${testIdPrefix}-card-${product.product_id}`}>
    <div className="relative aspect-[4/5] overflow-hidden mb-3">
      {rankBadge && (
        <div className="absolute top-2 left-2 z-10 w-7 h-7 bg-[#2C2420] text-[#FAF8F5]
                        flex items-center justify-center font-serif text-xs font-bold"
             data-testid={`rank-${rankBadge}`}>
          {rankBadge}
        </div>
      )}
      {product.images?.[0]?.url ? (
        <img src={product.images[0].url} alt={product.product_name}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
          loading="lazy"
        />
      ) : (
        <div className="w-full h-full bg-[#F3EFEA] flex items-center justify-center">
          <Package size={28} className="text-[#786A60]" strokeWidth={1.5} aria-hidden="true" />
        </div>
      )}
    </div>
    <h3 className="font-serif text-base text-[#2C2420] mb-1 line-clamp-2">{product.product_name}</h3>
    {product.avg_rating > 0 && (
      <StarDisplay rating={product.avg_rating} count={product.review_count} />
    )}
    <div className="flex items-center justify-between mt-2">
      <p className="text-sm font-semibold text-[#2C2420]">₹{product.base_price?.toLocaleString()}</p>
      <button
        onClick={() => onAddClick(product)}
        className="bg-transparent border border-[#4A3B32] text-[#4A3B32] px-3 py-1.5
                   text-[11px] tracking-[0.12em] uppercase font-semibold
                   hover:bg-[#4A3B32] hover:text-white transition-colors
                   min-h-[36px]"
        aria-label={`Add ${product.product_name}`}
        data-testid={`${testIdPrefix}-add-${product.product_id}`}
      >
        Add
      </button>
    </div>
  </div>
);

// ── Filter helpers ─────────────────────────────────────────────────────────

const applyQuickFilters = (products, activeFilters, searchQuery) => {
  let result = products;
  if (searchQuery) {
    const q = searchQuery.toLowerCase();
    result = result.filter(p =>
      p.product_name?.toLowerCase().includes(q) ||
      p.description?.toLowerCase().includes(q)
    );
  }
  if (!activeFilters.length) return result;
  return result.filter(p => {
    return activeFilters.every(f => {
      if (f === 'veg') return p.is_veg === true;
      if (f === 'nonveg') return p.is_veg === false;
      if (f === 'bestseller') return p.is_bestseller;
      if (f === 'on_offer') return p.has_active_offer;
      if (f === 'rated4') return p.avg_rating >= 4;
      if (f === 'new') {
        if (!p.created_at) return false;
        return (Date.now() - new Date(p.created_at).getTime()) / 86400000 <= 30;
      }
      return true;
    });
  });
};

// ── Main page ──────────────────────────────────────────────────────────────

const ProductCatalog = () => {
  const { businessId } = useParams();
  const [searchParams] = useSearchParams();
  const { addToCart } = useCart();
  const { viewedIds, trackView } = useRecentlyViewed();
  const { recommendations } = useChatContext();

  const [business, setBusiness] = useState(null);
  const [categories, setCategories] = useState([]);
  const [productsByCategory, setProductsByCategory] = useState({});
  const [trending, setTrending] = useState([]);
  const [recommended, setRecommended] = useState([]);
  const [recStrategy, setRecStrategy] = useState('');
  const [recentProducts, setRecentProducts] = useState([]);
  const [loading, setLoading] = useState(true);

  // Active filter state
  const [activeFilters, setActiveFilters] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');

  // Scroll spy
  const [activeCategory, setActiveCategory] = useState('');

  // Mobile sidebar drawer
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Product item modal
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);

  // Section refs for scroll spy
  const sectionRefs = useRef({});
  const contentRef = useRef(null);

  // Chatbot URL params (backward compat)
  const highlightProductId = searchParams.get('product');
  const urlKeyword = searchParams.get('keyword');
  const urlCategory = searchParams.get('category');

  // ── Data fetching ──────────────────────────────────────────────────────

  const recFetcher = url => apiClient.get(url).then(r => r.data);
  const { data: recData } = useSWR(
    `/products/recommended/${businessId}?limit=4`,
    recFetcher,
    { revalidateOnFocus: false, dedupingInterval: 600000 }
  );

  useEffect(() => {
    if (recommendations?.length > 0) {
      mutate(
        `/products/recommended/${businessId}?limit=4`,
        { recommended: recommendations.map(id => ({ product_id: id })), strategy: 'personalized' },
        false
      );
    }
  }, [recommendations, businessId]);

  useEffect(() => {
    if (recData) {
      setRecommended(recData.recommended || []);
      setRecStrategy(recData.strategy || '');
    }
  }, [recData]);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [bizRes, catsRes, trendingRes] = await Promise.all([
          apiClient.get(`/businesses/${businessId}`),
          apiClient.get(`/categories/${businessId}`),
          apiClient.get(`/products/trending/${businessId}?limit=4`),
        ]);
        setBusiness(bizRes.data);
        const cats = catsRes.data.categories || [];
        setCategories(cats);
        setTrending(trendingRes.data.trending || []);

        // Fetch products per category in parallel (top-level only)
        const topLevel = cats.filter(c => !c.parent_category_id);
        const productPromises = topLevel.map(cat =>
          apiClient.get(`/products?business_id=${businessId}&category_id=${cat.category_id}&limit=50`)
            .then(r => ({ category_id: cat.category_id, products: r.data.products || [] }))
            .catch(() => ({ category_id: cat.category_id, products: [] }))
        );
        const results = await Promise.all(productPromises);
        const byCategory = {};
        results.forEach(r => { byCategory[r.category_id] = r.products; });
        setProductsByCategory(byCategory);
      } catch (err) {
        console.error('ProductCatalog fetch error:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, [businessId]);

  // Build recently viewed list
  useEffect(() => {
    if (!viewedIds.length) return;
    const allProducts = Object.values(productsByCategory).flat();
    const productMap = Object.fromEntries(allProducts.map(p => [p.product_id, p]));
    setRecentProducts(viewedIds.map(id => productMap[id]).filter(Boolean).slice(0, 4));
  }, [viewedIds, productsByCategory]);

  // ── Scroll spy ──────────────────────────────────────────────────────────

  useEffect(() => {
    const observer = new IntersectionObserver(
      entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            setActiveCategory(entry.target.dataset.categoryId);
          }
        });
      },
      { rootMargin: '-20% 0px -70% 0px', threshold: 0 }
    );
    Object.values(sectionRefs.current).forEach(el => el && observer.observe(el));
    return () => observer.disconnect();
  }, [categories, loading]);

  // Scroll to category section
  const handleCategoryClick = useCallback(categoryId => {
    setSidebarOpen(false);
    const el = sectionRefs.current[categoryId];
    if (el) {
      const offset = 200; // account for sticky headers
      const top = el.getBoundingClientRect().top + window.scrollY - offset;
      window.scrollTo({ top, behavior: 'smooth' });
    }
    setActiveCategory(categoryId);
  }, []);

  // ── Filter toggle ────────────────────────────────────────────────────────

  const handleFilterToggle = useCallback(filterId => {
    setActiveFilters(prev =>
      prev.includes(filterId) ? prev.filter(f => f !== filterId) : [...prev, filterId]
    );
  }, []);

  // ── Modal ────────────────────────────────────────────────────────────────

  const handleAddClick = useCallback(product => {
    const hasAddons = product.addons && product.addons.length > 0;
    if (hasAddons) {
      setSelectedProduct(product);
      setModalOpen(true);
    } else {
      addToCart(product.product_id, null, 1);
    }
    trackView(product.product_id);
    apiClient.post('/products/track-view', {
      product_id: product.product_id,
      business_id: businessId,
    }).catch(() => {});
  }, [addToCart, trackView, businessId]);

  const handleModalAdd = useCallback(async (product, selectedAddons, totalPrice) => {
    await addToCart(product.product_id, null, 1, selectedAddons);
  }, [addToCart]);

  // ── Category section renderer ─────────────────────────────────────────

  const renderCategorySection = (cat) => {
    const products = productsByCategory[cat.category_id] || [];
    const filtered = applyQuickFilters(products, activeFilters, searchQuery);
    if (filtered.length === 0 && (activeFilters.length > 0 || searchQuery)) return null;

    return (
      <section
        key={cat.category_id}
        ref={el => { sectionRefs.current[cat.category_id] = el; }}
        data-category-id={cat.category_id}
        className="py-6 border-b border-[#E8E0D5] last:border-0"
        data-testid={`category-section-${cat.category_id}`}
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="font-serif text-lg md:text-xl text-[#2C2420]">
              {cat.icon_emoji && <span className="mr-2" aria-hidden="true">{cat.icon_emoji}</span>}
              {cat.display_name}
            </h2>
            {cat.description && (
              <p className="text-xs text-[#786A60] mt-0.5">{cat.description}</p>
            )}
          </div>
          <span className="text-xs text-[#786A60] tabular-nums flex-shrink-0 ml-2">
            {filtered.length} items
          </span>
        </div>

        {filtered.length === 0 ? (
          <p className="text-sm text-[#786A60] py-4">No items match your filters.</p>
        ) : (
          <div>
            {filtered.map(product => (
              <OrderProductCard
                key={product.product_id}
                product={product}
                onAddClick={handleAddClick}
              />
            ))}
          </div>
        )}
      </section>
    );
  };

  // ── Loading / error states ─────────────────────────────────────────────

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col bg-[#FAF8F5]">
        <AnnouncementBar businessId={businessId} />
        <OrderNavbar businessId={businessId} />
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-[#4A3B32]" aria-label="Loading" />
        </div>
      </div>
    );
  }

  if (!business) {
    return (
      <div className="min-h-screen flex flex-col bg-[#FAF8F5]">
        <AnnouncementBar businessId={businessId} />
        <OrderNavbar businessId={businessId} />
        <div className="flex-1 flex items-center justify-center">
          <p className="text-[#786A60] font-sans">Business not found</p>
        </div>
      </div>
    );
  }

  const strategyLabels = {
    category_match: 'Based on your interests',
    also_bought: 'Customers also ordered',
    discovery: 'You might like these',
    top_rated: 'Our highest rated',
    personalized: 'Handpicked for you',
  };

  const topLevelCategories = categories.filter(c => !c.parent_category_id);

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5]">
      <AnnouncementBar businessId={businessId} />
      <OrderNavbar businessId={businessId} business={business} />
      <ProductFiltersBar
        activeFilters={activeFilters}
        onFilterToggle={handleFilterToggle}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
      />

      {/* Mobile category chip strip */}
      <div className="lg:hidden sticky top-[110px] z-30">
        <CategoryChipStrip
          categories={categories}
          activeCategory={activeCategory}
          onCategoryClick={handleCategoryClick}
        />
      </div>

      {/* Hero marquee */}
      <div className="bg-[#F3EFEA] py-2 border-b border-[#E8E0D5]">
        <Marquee speed={25} gradient={false}>
          {['Fresh pastries daily', 'Custom cakes for every occasion', 'Handcrafted with love', 'Subscribe for weekly deliveries'].map((text, i) => (
            <span key={i} className="flex items-center">
              <span className="text-xs tracking-[0.18em] uppercase text-[#4A3B32] font-serif mx-10">{text}</span>
              <span className="text-[#D4A373] mx-2" aria-hidden="true">&bull;</span>
            </span>
          ))}
        </Marquee>
      </div>

      {/* Main layout */}
      <div className="flex flex-1 max-w-7xl mx-auto w-full">
        {/* Desktop sidebar */}
        <div className="hidden lg:block">
          <CategorySidebar
            categories={categories}
            activeCategory={activeCategory}
            onCategoryClick={handleCategoryClick}
          />
        </div>

        {/* Mobile sidebar drawer overlay */}
        {sidebarOpen && (
          <>
            <div
              className="lg:hidden fixed inset-0 bg-black/40 z-40"
              onClick={() => setSidebarOpen(false)}
              aria-hidden="true"
            />
            <div className="lg:hidden fixed left-0 top-0 bottom-0 w-72 z-50 bg-white shadow-xl overflow-y-auto">
              <div className="flex items-center justify-between p-4 border-b border-[#E8E0D5]">
                <p className="font-semibold text-[#2C2420]">Menu</p>
                <button onClick={() => setSidebarOpen(false)} aria-label="Close menu"
                  className="p-2 text-[#786A60]">✕</button>
              </div>
              <CategorySidebar
                categories={categories}
                activeCategory={activeCategory}
                onCategoryClick={handleCategoryClick}
              />
            </div>
          </>
        )}

        {/* Content area */}
        <main ref={contentRef} className="flex-1 px-4 md:px-6 lg:px-8 py-4" data-testid="catalog-main">

          {/* Trending section */}
          {trending.length > 0 && !activeFilters.length && !searchQuery && (
            <section className="mb-6" data-testid="trending-section">
              <SectionHeader icon={TrendingUp} title="Trending Now" subtitle="Bestsellers ranked by popularity" />
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 md:gap-6">
                {trending.map((p, i) => (
                  <CompactCard key={p.product_id} product={p} onAddClick={handleAddClick}
                    rankBadge={i + 1} testIdPrefix="trending" />
                ))}
              </div>
            </section>
          )}

          {/* Recently viewed */}
          {recentProducts.length > 0 && !activeFilters.length && !searchQuery && (
            <section className="mb-6 bg-white py-6 px-4 -mx-4 md:-mx-6 lg:-mx-8 border-y border-[#E8E0D5]"
                     data-testid="recently-viewed-section">
              <div className="max-w-none">
                <SectionHeader icon={Clock} title="Recently Viewed" subtitle="Pick up where you left off"
                  iconBg="bg-[#786A60]" />
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 md:gap-6">
                  {recentProducts.map(p => (
                    <CompactCard key={p.product_id} product={p} onAddClick={handleAddClick}
                      testIdPrefix="recent" />
                  ))}
                </div>
              </div>
            </section>
          )}

          {/* Recommended */}
          {recommended.length > 0 && !activeFilters.length && !searchQuery && (
            <section className="mb-6" data-testid="recommended-section">
              <SectionHeader icon={Sparkles} title="Recommended For You"
                subtitle={strategyLabels[recStrategy] || 'Handpicked for you'}
                iconBg="bg-[#D4A373]" />
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 md:gap-6">
                {recommended.map(p => (
                  <CompactCard key={p.product_id} product={p} onAddClick={handleAddClick}
                    testIdPrefix="recommended" />
                ))}
              </div>
            </section>
          )}

          {/* Category sections — fully API-driven */}
          {topLevelCategories.length > 0 ? (
            topLevelCategories.map(cat => renderCategorySection(cat))
          ) : (
            <div className="text-center py-20">
              <Package size={40} className="mx-auto text-[#786A60] mb-3" strokeWidth={1} />
              <p className="text-[#786A60] font-serif text-lg">No products found.</p>
            </div>
          )}

          {/* Custom cake CTA */}
          {businessId === 'whisked_words' && (
            <div className="mt-8 mb-20 p-6 bg-[#F3EFEA] border border-[#E8E0D5] text-center">
              <p className="font-serif text-lg text-[#2C2420] mb-2">Want something custom?</p>
              <p className="text-sm text-[#786A60] mb-4">Design your perfect cake for any occasion.</p>
              <Link
                to={`/business/${businessId}/custom-order`}
                className="inline-block bg-[#4A3B32] text-white px-8 py-3 text-xs tracking-[0.15em]
                           uppercase font-semibold hover:bg-[#332822] transition-colors"
                data-testid="custom-cake-cta"
              >
                Custom Cake Order
              </Link>
            </div>
          )}

          {/* Bottom padding for floating cart bar */}
          <div className="h-20 lg:h-0" />
        </main>
      </div>

      {/* Mobile menu FAB */}
      <button
        onClick={() => setSidebarOpen(true)}
        className="lg:hidden fixed left-4 bottom-20 z-30 bg-[#4A3B32] text-white
                   px-4 py-2.5 shadow-lg flex items-center gap-2 text-sm font-medium
                   pb-[calc(10px+env(safe-area-inset-bottom))]"
        aria-label="Browse menu categories"
        data-testid="mobile-menu-fab"
      >
        <MenuIcon size={16} />
        Menu
      </button>

      <ProductItemModal
        product={selectedProduct}
        isOpen={modalOpen}
        onClose={() => { setModalOpen(false); setSelectedProduct(null); }}
        onAddToCart={handleModalAdd}
      />

      <ChatWidget businessId={businessId} businessName={business?.business_name || ''} />
      <FloatingCartBar />
      <BakeryFooter />
    </div>
  );
};

export default ProductCatalog;
