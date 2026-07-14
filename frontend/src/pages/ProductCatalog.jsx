import { useEffect, useState, useRef } from 'react';
import { useParams, Link, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import Marquee from 'react-fast-marquee';
import useSWR, { mutate } from 'swr';
import BakeryNavbar from '../components/common/BakeryNavbar';
import BakeryFooter from '../components/common/BakeryFooter';
import ChatWidget from '../components/chatbot/ChatWidget';
import { useCart } from '../context/CartContext';
import { useRecentlyViewed } from '../hooks/useRecentlyViewed';
import { useChatContext } from '../context/ChatContext';
import apiClient from '../utils/api';
import { Loader2, Package, ShoppingCart, Star, TrendingUp, Clock, Sparkles } from 'lucide-react';

const StarDisplay = ({ rating, count }) => (
  <div className="flex items-center gap-1.5">
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((s) => (
        <Star key={s} size={11} className={s <= Math.round(rating) ? 'fill-[#D4A373] text-[#D4A373]' : 'text-[#E8E0D5]'} />
      ))}
    </div>
    <span className="text-xs font-medium text-[#2C2420]">{rating}</span>
    {count > 0 && <span className="text-xs text-[#786A60]">({count})</span>}
  </div>
);

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: (i = 0) => ({ opacity: 1, y: 0, transition: { delay: i * 0.08, duration: 0.6, ease: [0.22, 1, 0.36, 1] } })
};

const CompactCard = ({ product, onAddToCart, cartLoading, rankBadge, testIdPrefix }) => (
  <motion.div
    variants={fadeUp}
    initial="hidden"
    whileInView="visible"
    viewport={{ once: true }}
    className="group"
    data-testid={`${testIdPrefix}-card-${product.product_id}`}
  >
    <div className="relative aspect-[4/5] overflow-hidden mb-4">
      {rankBadge && (
        <div className="absolute top-3 left-3 z-10 w-8 h-8 bg-[#2C2420] text-[#FAF8F5] flex items-center justify-center font-serif text-sm font-bold" data-testid={`trending-rank-${rankBadge}`}>
          {rankBadge}
        </div>
      )}
      {product.images?.[0]?.url ? (
        <img src={product.images[0].url} alt={product.product_name} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700 ease-out" />
      ) : (
        <div className="w-full h-full bg-[#F3EFEA] flex items-center justify-center">
          <Package size={32} className="text-[#786A60]" strokeWidth={1.5} />
        </div>
      )}
    </div>

    <h3 className="font-serif text-lg text-[#2C2420] mb-1">{product.product_name}</h3>

    <div className="flex items-center justify-between mb-2">
      {product.avg_rating !== undefined && product.avg_rating > 0 ? (
        <StarDisplay rating={product.avg_rating} count={product.review_count} />
      ) : <div />}
      {product.total_ordered > 0 && (
        <span className="text-[11px] text-[#786A60] flex items-center gap-1"><TrendingUp size={11} />{product.total_ordered} sold</span>
      )}
    </div>

    <div className="flex items-center justify-between">
      <p className="text-sm font-semibold text-[#2C2420]">₹{product.base_price.toLocaleString()}</p>
      <button
        onClick={() => onAddToCart(product.product_id, null, 1)}
        disabled={cartLoading}
        className="bg-transparent border border-[#4A3B32] text-[#4A3B32] px-4 py-2 text-[11px] tracking-[0.15em] uppercase font-semibold hover:bg-[#4A3B32] hover:text-white transition-colors duration-300 disabled:opacity-50 flex items-center gap-1.5"
        data-testid={`${testIdPrefix}-add-to-cart-${product.product_id}`}
      >
        <ShoppingCart size={13} />
        Add
      </button>
    </div>
  </motion.div>
);

const SectionHeader = ({ icon: Icon, title, subtitle, iconBg = 'bg-[#4A3B32]' }) => (
  <div className="flex items-center gap-4 mb-10">
    <div className={`w-10 h-10 ${iconBg} flex items-center justify-center`}>
      <Icon size={18} className="text-white" strokeWidth={1.5} />
    </div>
    <div>
      <h2 className="font-serif text-2xl md:text-3xl text-[#2C2420]">{title}</h2>
      <p className="text-xs tracking-[0.15em] uppercase text-[#D4A373] font-semibold mt-0.5">{subtitle}</p>
    </div>
  </div>
);

const ProductCatalog = () => {
  const { businessId } = useParams();
  const [searchParams] = useSearchParams();
  const { addToCart, loading: cartLoading } = useCart();
  const { viewedIds, trackView } = useRecentlyViewed();
  const { recommendations } = useChatContext();
  const [business, setBusiness] = useState(null);
  const [products, setProducts] = useState([]);
  const [trending, setTrending] = useState([]);
  const [recommended, setRecommended] = useState([]);
  const [recStrategy, setRecStrategy] = useState('');
  const [recentProducts, setRecentProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const productRefs = useRef({});

  // Read chatbot URL params
  const highlightProductId = searchParams.get('product');
  const urlKeyword = searchParams.get('keyword');
  const urlFlavor = searchParams.get('flavor');
  const urlOccasion = searchParams.get('occasion');
  const urlCategory = searchParams.get('category');
  const urlPriceMin = searchParams.get('price_min');
  const urlPriceMax = searchParams.get('price_max');

  // Filter products based on URL params from chatbot
  const filteredProducts = products.filter(p => {
    if (urlKeyword) {
      // Split multi-word keywords and match ANY word against name, description, or attributes
      const words = urlKeyword.toLowerCase().split(/\s+/).filter(Boolean);
      const searchText = [
        p.product_name,
        p.description,
        p.attributes?.flavor,
        p.attributes?.cake_type,
        p.attributes?.fabric,
        p.attributes?.metal_type,
        p.attributes?.design,
        p.category_id,
      ].filter(Boolean).join(' ').toLowerCase();

      const anyWordMatches = words.some(w => searchText.includes(w));
      if (!anyWordMatches) return false;
    }
    if (urlFlavor) {
      const fl = urlFlavor.toLowerCase();
      const searchText = [
        p.product_name,
        p.attributes?.flavor,
        p.attributes?.flavour,
        p.description,
      ].filter(Boolean).join(' ').toLowerCase();
      if (!searchText.includes(fl)) return false;
    }
    if (urlOccasion) {
      const occ = urlOccasion.toLowerCase();
      const attrOcc = [p.attributes?.occasion, p.description].filter(Boolean).join(' ').toLowerCase();
      if (!attrOcc.includes(occ)) return false;
    }
    if (urlCategory) {
      const cat = urlCategory.toLowerCase();
      const catText = [p.category_id, p.product_name, p.description].filter(Boolean).join(' ').toLowerCase();
      if (!catText.includes(cat)) return false;
    }
    if (urlPriceMin && p.base_price < parseFloat(urlPriceMin)) return false;
    if (urlPriceMax && p.base_price > parseFloat(urlPriceMax)) return false;
    return true;
  });

  const displayProducts = (urlKeyword || urlFlavor || urlOccasion || urlCategory || urlPriceMin || urlPriceMax)
    ? filteredProducts
    : products;

  // SWR fetcher using apiClient
  const recFetcher = (url) => apiClient.get(url).then(res => res.data);
  const { data: recData } = useSWR(
    `/products/recommended/${businessId}?limit=4`,
    recFetcher,
    { revalidateOnFocus: false, dedupingInterval: 600000 }
  );

  // Seed the SWR cache at login when recommendations are available from ChatContext
  useEffect(() => {
    if (recommendations && recommendations.length > 0) {
      mutate(
        `/products/recommended/${businessId}?limit=4`,
        { recommended: recommendations.map(id => ({ product_id: id })), strategy: 'personalized' },
        false  // don't revalidate — we trust the login-time data
      );
    }
  }, [recommendations, businessId]);

  // Derive recommended and recStrategy from SWR data
  useEffect(() => {
    if (recData) {
      setRecommended(recData.recommended || []);
      setRecStrategy(recData.strategy || '');
    }
  }, [recData]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // When chatbot filter params are present, fetch all products (up to 200)
        // so the client-side filter has the full catalog to search through
        const hasFilterParams = urlKeyword || urlFlavor || urlOccasion || urlCategory || urlPriceMin || urlPriceMax;
        const productLimit = hasFilterParams ? 200 : 50;

        const [businessRes, productsRes, trendingRes] = await Promise.all([
          apiClient.get(`/businesses/${businessId}`),
          apiClient.get(`/products?business_id=${businessId}&limit=${productLimit}`),
          apiClient.get(`/products/trending/${businessId}?limit=4`)
        ]);
        setBusiness(businessRes.data);
        setProducts(productsRes.data.products);
        setTrending(trendingRes.data.trending);
      } catch (error) {
        console.error('Error fetching data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [businessId, urlKeyword, urlFlavor, urlOccasion, urlCategory, urlPriceMin, urlPriceMax]);

  useEffect(() => {
    if (products.length > 0 && viewedIds.length > 0) {
      const productMap = {};
      products.forEach(p => { productMap[p.product_id] = p; });
      setRecentProducts(viewedIds.map(id => productMap[id]).filter(Boolean).slice(0, 4));
    }
  }, [products, viewedIds]);

  const handleProductClick = (productId) => {
    trackView(productId);
    apiClient.post('/products/track-view', { product_id: productId, business_id: businessId }).catch(() => {});
  };

  // Scroll to and highlight a specific product when ?product= is in URL
  useEffect(() => {
    if (!highlightProductId || loading) return;
    const tryScroll = () => {
      const el = productRefs.current[highlightProductId];
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    };
    // Small delay to let the DOM render first
    const t = setTimeout(tryScroll, 300);
    return () => clearTimeout(t);
  }, [highlightProductId, loading, displayProducts]);

  const strategyLabels = {
    category_match: 'Based on your interests',
    also_bought: 'Customers also ordered',
    discovery: 'You might like these',
    top_rated: 'Our highest rated'
  };

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col bg-[#FAF8F5]">
        <BakeryNavbar />
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-[#4A3B32]" />
        </div>
      </div>
    );
  }

  if (!business) {
    return (
      <div className="min-h-screen flex flex-col bg-[#FAF8F5]">
        <BakeryNavbar />
        <div className="flex-1 flex items-center justify-center">
          <p className="text-[#786A60] font-sans">Business not found</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5]">
      <BakeryNavbar />

      {/* Hero */}
      <section className="relative h-[50vh] min-h-[400px] overflow-hidden" data-testid="catalog-header">
        <img
          src="https://images.unsplash.com/photo-1774758951271-e0886de596f7?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1MDZ8MHwxfHNlYXJjaHwxfHxhcnRpc2FuJTIwYmFrZXJ5JTIwcGFzdHJpZXMlMjB3YXJtJTIwbGlnaHR8ZW58MHx8fHwxNzc3NjE4NjEyfDA&ixlib=rb-4.1.0&q=85"
          alt="Whisked Words Bakery"
          className="absolute inset-0 w-full h-full object-cover"
          aria-hidden="true"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-[#2C2420]/80 via-[#2C2420]/30 to-transparent" />
        <div className="relative z-10 h-full flex flex-col justify-end max-w-7xl mx-auto px-6 md:px-12 pb-16">
          <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}>
            <p className="text-xs tracking-[0.3em] uppercase text-[#D4A373] font-semibold mb-3">Artisan Bakery</p>
            <h1 className="font-serif text-5xl md:text-6xl lg:text-7xl text-[#FAF8F5] leading-none mb-4 italic">
              {business.business_name}
            </h1>
            <p className="text-base text-[#FAF8F5]/70 font-sans max-w-md">{business.description}</p>
          </motion.div>
        </div>
      </section>

      {/* Marquee */}
      <div className="bg-[#F3EFEA] py-3 border-y border-[#E8E0D5]">
        <Marquee speed={30} gradient={false}>
          <span className="text-sm tracking-[0.2em] uppercase text-[#4A3B32] font-serif mx-12">Fresh pastries daily</span>
          <span className="text-[#D4A373] mx-4">&bull;</span>
          <span className="text-sm tracking-[0.2em] uppercase text-[#4A3B32] font-serif mx-12">Custom cakes for every occasion</span>
          <span className="text-[#D4A373] mx-4">&bull;</span>
          <span className="text-sm tracking-[0.2em] uppercase text-[#4A3B32] font-serif mx-12">Handcrafted with love</span>
          <span className="text-[#D4A373] mx-4">&bull;</span>
          <span className="text-sm tracking-[0.2em] uppercase text-[#4A3B32] font-serif mx-12">Subscribe for weekly deliveries</span>
          <span className="text-[#D4A373] mx-4">&bull;</span>
        </Marquee>
      </div>

      {/* Trending Now */}
      {trending.length > 0 && (
        <section className="py-20 md:py-28" data-testid="trending-section">
          <div className="max-w-7xl mx-auto px-6 md:px-12">
            <SectionHeader icon={TrendingUp} title="Trending Now" subtitle="Bestsellers ranked by popularity" />
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8 lg:gap-12">
              {trending.map((product, index) => (
                <CompactCard key={product.product_id} product={product} onAddToCart={addToCart} cartLoading={cartLoading} rankBadge={index + 1} testIdPrefix="trending" />
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Recently Viewed */}
      {recentProducts.length > 0 && (
        <section className="py-20 md:py-28 bg-white border-y border-[#E8E0D5]" data-testid="recently-viewed-section">
          <div className="max-w-7xl mx-auto px-6 md:px-12">
            <SectionHeader icon={Clock} title="Recently Viewed" subtitle="Pick up where you left off" iconBg="bg-[#786A60]" />
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8 lg:gap-12">
              {recentProducts.map((product) => (
                <CompactCard key={product.product_id} product={product} onAddToCart={addToCart} cartLoading={cartLoading} testIdPrefix="recent" />
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Recommended For You */}
      {recommended.length > 0 && (
        <section className="py-20 md:py-28" data-testid="recommended-section">
          <div className="max-w-7xl mx-auto px-6 md:px-12">
            <SectionHeader icon={Sparkles} title="Recommended For You" subtitle={strategyLabels[recStrategy] || 'Handpicked for you'} iconBg="bg-[#D4A373]" />
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8 lg:gap-12">
              {recommended.map((product) => (
                <CompactCard key={product.product_id} product={product} onAddToCart={addToCart} cartLoading={cartLoading} testIdPrefix="recommended" />
              ))}
            </div>
          </div>
        </section>
      )}

      {/* All Products */}
      <main className="py-20 md:py-28 bg-white border-t border-[#E8E0D5]" data-testid="products-section">
        <div className="max-w-7xl mx-auto px-6 md:px-12">
          <div className="flex items-end justify-between mb-14">
            <div>
              <h2 className="font-serif text-3xl md:text-4xl text-[#2C2420] mb-2">
                {displayProducts.length < products.length ? 'Filtered Results' : 'All Products'}
              </h2>
              <p className="text-sm text-[#786A60]">{displayProducts.length} items{displayProducts.length < products.length ? ` of ${products.length}` : ''}</p>
              {/* Active filter banner from chatbot URL params */}
              {(urlKeyword || urlFlavor || urlOccasion || urlCategory) && (
                <div className="flex flex-wrap gap-2 mt-3">
                  {urlKeyword && <span className="text-xs bg-[#F3EFEA] border border-[#D4A373] text-[#4A3B32] px-3 py-1 rounded-sm">"{urlKeyword}"</span>}
                  {urlFlavor && <span className="text-xs bg-[#F3EFEA] border border-[#D4A373] text-[#4A3B32] px-3 py-1 rounded-sm">Flavor: {urlFlavor}</span>}
                  {urlOccasion && <span className="text-xs bg-[#F3EFEA] border border-[#D4A373] text-[#4A3B32] px-3 py-1 rounded-sm">Occasion: {urlOccasion}</span>}
                  {urlCategory && <span className="text-xs bg-[#F3EFEA] border border-[#D4A373] text-[#4A3B32] px-3 py-1 rounded-sm">Category: {urlCategory}</span>}
                  {(urlPriceMin || urlPriceMax) && <span className="text-xs bg-[#F3EFEA] border border-[#D4A373] text-[#4A3B32] px-3 py-1 rounded-sm">₹{urlPriceMin || '0'} – ₹{urlPriceMax || '∞'}</span>}
                  <Link to={`/business/${businessId}/catalog`} className="text-xs text-[#786A60] underline px-2 py-1 hover:text-[#4A3B32]">Clear filters</Link>
                </div>
              )}
            </div>
            {businessId === 'whisked_words' && (
              <Link
                to={`/business/${businessId}/custom-order`}
                className="bg-[#4A3B32] text-white px-8 py-4 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#332822] transition-colors duration-300 flex items-center gap-2"
                data-testid="custom-cake-order-button"
              >
                Custom Cake Order
              </Link>
            )}
          </div>

          {displayProducts.length === 0 ? (
            <div className="text-center py-32">
              <Package size={48} className="mx-auto text-[#786A60] mb-4" strokeWidth={1} />
              <p className="text-[#786A60] font-serif text-xl">No products match your search.</p>
              <Link to={`/business/${businessId}/catalog`} className="mt-4 inline-block text-sm text-[#4A3B32] underline">Show all products</Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-10 lg:gap-16">
              {displayProducts.map((product, i) => (
                <motion.div
                  key={product.product_id}
                  ref={el => { productRefs.current[product.product_id] = el; }}
                  variants={fadeUp}
                  custom={i}
                  initial="hidden"
                  whileInView="visible"
                  viewport={{ once: true }}
                  className={`group ${highlightProductId === product.product_id ? 'ring-2 ring-[#D4A373] ring-offset-4' : ''}`}
                  data-testid={`product-card-${product.product_id}`}
                >
                  {/* Product Image - Editorial */}
                  <div className="relative aspect-[4/5] overflow-hidden mb-5">
                    {product.images?.[0]?.url ? (
                      <img src={product.images[0].url} alt={product.product_name} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700 ease-out" />
                    ) : (
                      <div className="w-full h-full bg-[#F3EFEA] flex items-center justify-center">
                        <Package size={48} className="text-[#786A60]" strokeWidth={1} />
                      </div>
                    )}
                  </div>

                  {/* Product Details */}
                  <h3 className="font-serif text-xl text-[#2C2420] mb-2">{product.product_name}</h3>
                  <p className="text-sm text-[#786A60] leading-relaxed mb-4 line-clamp-2">{product.description}</p>

                  <div className="flex items-center justify-between pt-4 border-t border-[#E8E0D5]">
                    <p className="text-lg font-semibold text-[#2C2420]">
                      ₹{product.base_price.toLocaleString()}
                    </p>
                    <button
                      onClick={() => addToCart(product.product_id, null, 1)}
                      disabled={cartLoading}
                      className="bg-[#4A3B32] text-white px-6 py-3 text-[11px] tracking-[0.15em] uppercase font-semibold hover:bg-[#332822] transition-colors duration-300 flex items-center gap-2 disabled:opacity-50"
                      data-testid={`add-to-cart-${product.product_id}`}
                    >
                      <ShoppingCart size={14} />
                      Add to Cart
                    </button>
                  </div>

                  {/* Reviews Link */}
                  <Link
                    to={`/reviews/${product.product_id}`}
                    onClick={() => handleProductClick(product.product_id)}
                    className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-[#D4A373] hover:text-[#4A3B32] transition-colors"
                    data-testid={`reviews-link-${product.product_id}`}
                  >
                    <Star size={12} />
                    View Reviews
                  </Link>
                </motion.div>
              ))}
            </div>
          )}
        </div>
      </main>

      <ChatWidget businessId={businessId} businessName={business?.business_name || ''} />
      <BakeryFooter />
    </div>
  );
};

export default ProductCatalog;
