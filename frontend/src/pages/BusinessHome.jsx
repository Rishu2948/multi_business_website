import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import apiClient from '../utils/api';
import AnnouncementBar from '../components/common/AnnouncementBar';
import {
  ArrowRight, Package, Phone, Mail, MapPin, Loader2,
  ShoppingCart, Cake, CreditCard, RefreshCw,
} from 'lucide-react';

const QUICK_ACTIONS = (businessId) => [
  { to: `/business/${businessId}/catalog`, icon: ShoppingCart, label: 'Order Now', testId: 'qa-order' },
  { to: `/business/${businessId}/custom-order`, icon: Cake, label: 'Custom Cake', testId: 'qa-custom' },
  { to: '/loyalty', icon: CreditCard, label: 'Loyalty', testId: 'qa-loyalty' },
  { to: '/subscriptions', icon: RefreshCw, label: 'Subscribe', testId: 'qa-subscribe' },
];

const BusinessHome = () => {
  const { businessId } = useParams();
  const [business, setBusiness] = useState(null);
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [businessRes, productsRes, catsRes] = await Promise.all([
          apiClient.get(`/businesses/${businessId}`),
          apiClient.get(`/products?business_id=${businessId}&is_featured=true&limit=6`),
          apiClient.get(`/categories/${businessId}?is_featured=true`),
        ]);
        setBusiness(businessRes.data);
        setProducts(productsRes.data.products || []);
        setCategories(catsRes.data.categories || []);
      } catch (error) {
        console.error('Error fetching data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [businessId]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!business) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="text-center">
          <h1 className="text-4xl font-black text-primary mb-4">BUSINESS NOT FOUND</h1>
          <Link to="/" className="text-accent hover:text-[#002280] transition-colors">
            Return to Home
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-white">
      <AnnouncementBar businessId={businessId} />
      {/* Independent Business Navbar */}
      <nav className="sticky top-0 z-50 bg-white/80 backdrop-blur-xl backdrop-saturate-150 border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-8 py-4">
          <div className="flex items-center justify-between">
            {/* Business Logo/Name */}
            <Link to={`/business/${businessId}`} className="flex items-center gap-3" data-testid="business-logo">
              <div className="w-10 h-10 bg-primary flex items-center justify-center overflow-hidden">
                <img src={business.logo_url} alt={business.business_name} className="w-full h-full object-cover" />
              </div>
              <div>
                <span className="text-lg sm:text-xl font-black tracking-tight text-primary uppercase">{business.business_name}</span>
                <p className="text-xs text-muted hidden sm:block">A {business.parent_company} Company</p>
              </div>
            </Link>

            {/* Desktop Navigation */}
            <div className="hidden md:flex items-center gap-6">
              <Link to={`/business/${businessId}`}
                className="text-sm font-medium text-primary hover:text-accent transition-colors"
                data-testid="nav-home">HOME</Link>
              <Link to={`/business/${businessId}/catalog`}
                className="text-sm font-medium text-primary hover:text-accent transition-colors"
                data-testid="nav-catalog">CATALOG</Link>
              <Link to={`/business/${businessId}/contact`}
                className="text-sm font-medium text-primary hover:text-accent transition-colors"
                data-testid="nav-contact">CONTACT</Link>
              <Link to="/"
                className="text-xs text-muted hover:text-primary transition-colors"
                data-testid="nav-parent-company">{business.parent_company}</Link>
            </div>

            {/* Mobile: Order Now CTA */}
            <Link to={`/business/${businessId}/catalog`}
              className="md:hidden bg-primary text-white px-4 py-2 text-xs font-semibold"
              data-testid="mobile-order-now">
              Order Now
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative py-20 sm:py-32 bg-surface overflow-hidden" data-testid="business-hero">
        <div className="absolute inset-0 opacity-10" aria-hidden="true">
          <img src={business.logo_url} alt="" className="w-full h-full object-cover" />
        </div>
        <div className="relative max-w-7xl mx-auto px-4 sm:px-8">
          <div className="max-w-3xl">
            <p className="text-xs tracking-[0.2em] uppercase font-bold text-muted mb-4 sm:mb-6">
              {business.business_type.replace('_', ' ')}
            </p>
            <h1 className="text-3xl sm:text-5xl lg:text-6xl tracking-tighter font-black uppercase text-primary mb-6 sm:mb-8 leading-none">
              {business.business_name}
            </h1>
            <p className="text-base sm:text-xl leading-relaxed text-muted mb-8 sm:mb-12">
              {business.description}
            </p>
            <div className="flex flex-wrap gap-3 sm:gap-4">
              <Link
                to={`/business/${businessId}/catalog`}
                className="bg-primary text-white hover:bg-[#333333] transition-all border border-primary
                           px-6 sm:px-8 py-3 sm:py-4 font-bold tracking-wide flex items-center gap-2 text-sm sm:text-base"
                data-testid="view-catalog-button">
                ORDER NOW
                <ArrowRight size={18} />
              </Link>
              <Link
                to={`/business/${businessId}/contact`}
                className="bg-transparent text-primary hover:bg-secondary transition-all border border-border
                           px-6 sm:px-8 py-3 sm:py-4 font-bold tracking-wide text-sm sm:text-base"
                data-testid="contact-us-button">
                CONTACT US
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Quick Action Pills */}
      <section className="bg-white border-b border-border py-4 px-4 sm:px-8" data-testid="quick-actions">
        <div className="max-w-7xl mx-auto">
          <div className="flex gap-3 overflow-x-auto scrollbar-hide pb-1">
            {QUICK_ACTIONS(businessId).map(({ to, icon: Icon, label, testId }) => (
              <Link
                key={to}
                to={to}
                className="flex-shrink-0 flex items-center gap-2 bg-[#FAF8F5] border border-border
                           px-4 py-2.5 text-sm font-medium text-primary hover:border-primary
                           hover:bg-[#F3EFEA] transition-colors rounded-full min-h-[40px]"
                data-testid={testId}>
                <Icon size={15} className="text-[#D4A373]" />
                {label}
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Featured Category Tiles — API-driven from categories with is_featured=true */}
      {categories.length > 0 && (
        <section className="py-12 sm:py-16 bg-[#FAF8F5]" data-testid="category-tiles">
          <div className="max-w-7xl mx-auto px-4 sm:px-8">
            <p className="text-xs tracking-[0.2em] uppercase font-bold text-muted mb-4">BROWSE BY CATEGORY</p>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 sm:gap-4">
              {categories.map(cat => (
                <Link
                  key={cat.category_id}
                  to={`/business/${businessId}/catalog`}
                  state={{ scrollToCategory: cat.category_id }}
                  onClick={() => {
                    // Store scroll target in sessionStorage for ProductCatalog to read
                    sessionStorage.setItem('scrollToCategory', cat.category_id);
                  }}
                  className="group relative bg-white border border-border overflow-hidden
                             hover:-translate-y-0.5 hover:shadow-md transition-all"
                  data-testid={`category-tile-${cat.category_id}`}>
                  {cat.image_url ? (
                    <div className="aspect-square overflow-hidden">
                      <img src={cat.image_url} alt={cat.display_name}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                        loading="lazy" />
                    </div>
                  ) : (
                    <div className="aspect-square bg-[#F3EFEA] flex items-center justify-center">
                      <span className="text-3xl" aria-hidden="true">{cat.icon_emoji || '🍰'}</span>
                    </div>
                  )}
                  <div className="p-3 text-center">
                    <p className="text-xs font-semibold text-primary uppercase tracking-wide line-clamp-1">
                      {cat.display_name}
                    </p>
                    {cat.product_count > 0 && (
                      <p className="text-[10px] text-muted mt-0.5">{cat.product_count} items</p>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Featured Products */}
      {products.length > 0 && (
        <section className="py-12 sm:py-20 bg-white" data-testid="featured-products">
          <div className="max-w-7xl mx-auto px-4 sm:px-8">
            <div className="mb-8 sm:mb-12">
              <p className="text-xs tracking-[0.2em] uppercase font-bold text-muted mb-3 sm:mb-4">FEATURED PRODUCTS</p>
              <h2 className="text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold text-primary">
                Discover Our Collection
              </h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-8">
              {products.map((product) => (
                <motion.div
                  key={product.product_id}
                  initial={{ opacity: 0, y: 16 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  className="bg-white border border-border group hover:-translate-y-1 hover:shadow-lg transition-all duration-300"
                  data-testid={`featured-product-${product.product_id}`}
                >
                  <div className="aspect-square overflow-hidden">
                    {product.images?.length > 0 ? (
                      <img
                        src={product.images[0].url}
                        alt={product.product_name}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        loading="lazy"
                      />
                    ) : (
                      <div className="w-full h-full bg-surface flex items-center justify-center">
                        <Package size={48} className="text-muted" strokeWidth={1.5} aria-hidden="true" />
                      </div>
                    )}
                  </div>
                  <div className="p-4 sm:p-6">
                    <h3 className="text-base sm:text-lg font-semibold text-primary mb-2 line-clamp-2">
                      {product.product_name}
                    </h3>
                    <p className="text-sm text-muted mb-4 line-clamp-2">{product.description}</p>
                    <div className="flex items-center justify-between pt-4 border-t border-border">
                      <p className="text-xl sm:text-2xl font-bold text-primary">
                        ₹{product.base_price.toLocaleString()}
                      </p>
                      <Link
                        to={`/business/${businessId}/catalog`}
                        className="text-sm font-bold text-accent hover:text-[#002280] transition-colors"
                        data-testid={`view-product-${product.product_id}`}>
                        VIEW DETAILS
                      </Link>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>

            <div className="mt-8 sm:mt-12 text-center">
              <Link
                to={`/business/${businessId}/catalog`}
                className="inline-flex items-center gap-2 bg-transparent text-primary hover:bg-secondary
                           transition-all border border-border px-8 py-4 font-bold tracking-wide"
                data-testid="view-all-products-link">
                VIEW ALL PRODUCTS
                <ArrowRight size={20} />
              </Link>
            </div>
          </div>
        </section>
      )}

      {/* Testimonials row */}
      <section className="py-12 sm:py-16 bg-white border-b border-border overflow-hidden" data-testid="testimonials">
        <div className="max-w-7xl mx-auto px-4 sm:px-8">
          <p className="text-xs tracking-[0.2em] uppercase font-bold text-muted mb-8 text-center">
            WHAT OUR CUSTOMERS SAY
          </p>
          <div className="flex gap-5 overflow-x-auto scrollbar-hide pb-2">
            {[
              { name: 'Priya S.', city: 'Bengaluru', text: 'The custom cake for my daughter\'s birthday was absolutely stunning. Everyone at the party was amazed!', rating: 5, initial: 'P' },
              { name: 'Arjun M.', city: 'HSR Layout', text: 'Best croissants in the city. I order every Sunday morning — they\'re always fresh and perfectly flaky.', rating: 5, initial: 'A' },
              { name: 'Neha R.', city: 'Indiranagar', text: 'The gift box I ordered for Diwali was beautifully presented. Great quality and super fast delivery!', rating: 5, initial: 'N' },
              { name: 'Karan T.', city: 'Koramangala', text: 'Subscribed for weekly brownies and it\'s the best decision I\'ve made. Consistently excellent every time.', rating: 5, initial: 'K' },
              { name: 'Shruti D.', city: 'Whitefield', text: 'Their eggless cakes are just as decadent as the regular ones. Perfect for my family gatherings!', rating: 5, initial: 'S' },
            ].map((t, i) => (
              <div key={i}
                className="flex-shrink-0 w-72 sm:w-80 bg-[#FAF8F5] border border-border p-5 flex flex-col gap-3"
                data-testid={`testimonial-${i}`}>
                <div className="flex items-center gap-0.5">
                  {[...Array(t.rating)].map((_, s) => (
                    <svg key={s} className="w-3.5 h-3.5 fill-[#D4A373] text-[#D4A373]" viewBox="0 0 20 20" aria-hidden="true">
                      <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                    </svg>
                  ))}
                </div>
                <p className="text-sm text-muted leading-relaxed flex-1">"{t.text}"</p>
                <div className="flex items-center gap-2.5 pt-2 border-t border-border">
                  <div className="w-8 h-8 bg-primary rounded-full flex items-center justify-center flex-shrink-0">
                    <span className="text-xs font-bold text-white">{t.initial}</span>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-primary">{t.name}</p>
                    <p className="text-[10px] text-muted">{t.city}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* About Section */}
      <section className="py-12 sm:py-20 bg-surface" data-testid="about-section">
        <div className="max-w-7xl mx-auto px-4 sm:px-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 sm:gap-12">
            <div>
              <p className="text-xs tracking-[0.2em] uppercase font-bold text-muted mb-4">ABOUT US</p>
              <h2 className="text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold text-primary mb-6">Who We Are</h2>
              <p className="text-base leading-relaxed text-muted mb-4">{business.description}</p>
              <p className="text-base leading-relaxed text-muted">
                As part of {business.parent_company}, we maintain the highest standards of quality and customer service.
              </p>
            </div>
            <div className="bg-white border border-border p-6 sm:p-8">
              <h3 className="text-xl font-bold text-primary mb-6">GET IN TOUCH</h3>
              <div className="space-y-4">
                <div className="flex items-start gap-3">
                  <MapPin size={20} className="text-accent flex-shrink-0 mt-1" />
                  <div>
                    <p className="text-sm font-medium text-primary">Address</p>
                    <p className="text-sm text-muted">
                      {business.contact?.address?.street}, {business.contact?.address?.city}<br />
                      {business.contact?.address?.state} {business.contact?.address?.pincode}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Phone size={20} className="text-accent flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-primary">Phone</p>
                    <p className="text-sm text-muted">{business.contact?.phone}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Mail size={20} className="text-accent flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-primary">Email</p>
                    <p className="text-sm text-muted">{business.contact?.email}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-primary text-white mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-8 py-10 sm:py-12">
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-8">
            <div>
              <h3 className="text-base font-black tracking-tight mb-4 uppercase">{business.business_name}</h3>
              <p className="text-sm text-white/70">{business.description}</p>
            </div>
            <div>
              <h4 className="text-sm font-bold tracking-wide uppercase mb-4">Quick Links</h4>
              <ul className="space-y-2">
                {[
                  { to: `/business/${businessId}`, label: 'Home' },
                  { to: `/business/${businessId}/catalog`, label: 'Catalog' },
                  { to: `/business/${businessId}/contact`, label: 'Contact' },
                ].map(({ to, label }) => (
                  <li key={to}>
                    <Link to={to} className="text-sm text-white/70 hover:text-white transition-colors">{label}</Link>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="text-sm font-bold tracking-wide uppercase mb-4">Part Of</h4>
              <Link to="/" className="text-sm text-white/70 hover:text-white transition-colors">
                {business.parent_company}
              </Link>
            </div>
          </div>
          <div className="mt-8 pt-8 border-t border-white/20">
            <p className="text-sm text-white/70 text-center">
              © {new Date().getFullYear()} {business.business_name}. A {business.parent_company} Company. All rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default BusinessHome;