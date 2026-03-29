import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import apiClient from '../utils/api';
import { ArrowRight, Package, Phone, Mail, MapPin, Loader2 } from 'lucide-react';

const BusinessHome = () => {
  const { businessId } = useParams();
  const [business, setBusiness] = useState(null);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [businessRes, productsRes] = await Promise.all([
          apiClient.get(`/businesses/${businessId}`),
          apiClient.get(`/products?business_id=${businessId}&limit=6`)
        ]);
        setBusiness(businessRes.data);
        setProducts(productsRes.data.products);
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
      {/* Independent Business Navbar */}
      <nav className="sticky top-0 z-50 bg-white/80 backdrop-blur-xl backdrop-saturate-150 border-b border-border">
        <div className="max-w-7xl mx-auto px-8 py-4">
          <div className="flex items-center justify-between">
            {/* Business Logo/Name */}
            <Link to={`/business/${businessId}`} className="flex items-center gap-3" data-testid="business-logo">
              <div className="w-10 h-10 bg-primary flex items-center justify-center overflow-hidden">
                <img src={business.logo_url} alt={business.business_name} className="w-full h-full object-cover" />
              </div>
              <div>
                <span className="text-xl font-black tracking-tight text-primary uppercase">{business.business_name}</span>
                <p className="text-xs text-muted">A {business.parent_company} Company</p>
              </div>
            </Link>

            {/* Navigation */}
            <div className="flex items-center gap-6">
              <Link
                to={`/business/${businessId}`}
                className="text-sm font-medium text-primary hover:text-accent transition-colors"
                data-testid="nav-home"
              >
                HOME
              </Link>
              <Link
                to={`/business/${businessId}/catalog`}
                className="text-sm font-medium text-primary hover:text-accent transition-colors"
                data-testid="nav-catalog"
              >
                CATALOG
              </Link>
              <Link
                to={`/business/${businessId}/contact`}
                className="text-sm font-medium text-primary hover:text-accent transition-colors"
                data-testid="nav-contact"
              >
                CONTACT
              </Link>
              <Link
                to="/"
                className="text-xs text-muted hover:text-primary transition-colors"
                data-testid="nav-parent-company"
              >
                {business.parent_company}
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative py-32 bg-surface overflow-hidden" data-testid="business-hero">
        <div className="absolute inset-0 opacity-10">
          <img src={business.logo_url} alt="" className="w-full h-full object-cover" />
        </div>
        <div className="relative max-w-7xl mx-auto px-8">
          <div className="max-w-3xl">
            <p className="text-xs tracking-[0.2em] uppercase font-bold text-muted mb-6">
              {business.business_type.replace('_', ' ')}
            </p>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl tracking-tighter font-black uppercase text-primary mb-8 leading-none">
              {business.business_name}
            </h1>
            <p className="text-xl leading-relaxed text-muted mb-12">
              {business.description}
            </p>
            <div className="flex flex-wrap gap-4">
              <Link
                to={`/business/${businessId}/catalog`}
                className="bg-primary text-white hover:bg-[#333333] transition-all border border-primary px-8 py-4 font-bold tracking-wide flex items-center gap-2"
                data-testid="view-catalog-button"
              >
                VIEW CATALOG
                <ArrowRight size={20} />
              </Link>
              <Link
                to={`/business/${businessId}/contact`}
                className="bg-transparent text-primary hover:bg-secondary transition-all border border-border px-8 py-4 font-bold tracking-wide"
                data-testid="contact-us-button"
              >
                CONTACT US
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Featured Products */}
      {products.length > 0 && (
        <section className="py-20 bg-white" data-testid="featured-products">
          <div className="max-w-7xl mx-auto px-8">
            <div className="mb-12">
              <p className="text-xs tracking-[0.2em] uppercase font-bold text-muted mb-4">FEATURED PRODUCTS</p>
              <h2 className="text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold text-primary">Discover Our Collection</h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {products.map((product) => (
                <div
                  key={product.product_id}
                  className="bg-white border border-border group hover:-translate-y-1 hover:shadow-lg transition-all duration-300"
                  data-testid={`featured-product-${product.product_id}`}
                >
                  {/* Product Image */}
                  <div className="aspect-square overflow-hidden">
                    {product.images && product.images.length > 0 ? (
                      <img
                        src={product.images[0].url}
                        alt={product.product_name}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                    ) : (
                      <div className="w-full h-full bg-surface flex items-center justify-center">
                        <Package size={48} className="text-muted" strokeWidth={1.5} />
                      </div>
                    )}
                  </div>

                  {/* Product Details */}
                  <div className="p-6">
                    <h3 className="text-lg font-semibold text-primary mb-2 line-clamp-2">
                      {product.product_name}
                    </h3>
                    <p className="text-sm text-muted mb-4 line-clamp-2">
                      {product.description}
                    </p>
                    <div className="flex items-center justify-between pt-4 border-t border-border">
                      <p className="text-2xl font-bold text-primary">
                        {product.currency === 'INR' ? '₹' : '$'}{product.base_price.toLocaleString()}
                      </p>
                      <button className="text-sm font-bold text-accent hover:text-[#002280] transition-colors">
                        VIEW DETAILS
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-12 text-center">
              <Link
                to={`/business/${businessId}/catalog`}
                className="inline-flex items-center gap-2 bg-transparent text-primary hover:bg-secondary transition-all border border-border px-8 py-4 font-bold tracking-wide"
                data-testid="view-all-products-link"
              >
                VIEW ALL PRODUCTS
                <ArrowRight size={20} />
              </Link>
            </div>
          </div>
        </section>
      )}

      {/* About Section */}
      <section className="py-20 bg-surface" data-testid="about-section">
        <div className="max-w-7xl mx-auto px-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
            <div>
              <p className="text-xs tracking-[0.2em] uppercase font-bold text-muted mb-4">ABOUT US</p>
              <h2 className="text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold text-primary mb-6">
                Who We Are
              </h2>
              <p className="text-base leading-relaxed text-muted mb-6">
                {business.description}
              </p>
              <p className="text-base leading-relaxed text-muted">
                As part of {business.parent_company}, we maintain the highest standards of quality and customer service.
              </p>
            </div>

            <div className="bg-white border border-border p-8">
              <h3 className="text-xl font-bold text-primary mb-6">GET IN TOUCH</h3>
              <div className="space-y-4">
                <div className="flex items-start gap-3">
                  <MapPin size={20} className="text-accent flex-shrink-0 mt-1" />
                  <div>
                    <p className="text-sm font-medium text-primary">Address</p>
                    <p className="text-sm text-muted">
                      {business.contact.address.street}, {business.contact.address.city}<br />
                      {business.contact.address.state} {business.contact.address.pincode}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Phone size={20} className="text-accent flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-primary">Phone</p>
                    <p className="text-sm text-muted">{business.contact.phone}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Mail size={20} className="text-accent flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-primary">Email</p>
                    <p className="text-sm text-muted">{business.contact.email}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-primary text-white mt-auto">
        <div className="max-w-7xl mx-auto px-8 py-12">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div>
              <h3 className="text-lg font-black tracking-tight mb-4 uppercase">{business.business_name}</h3>
              <p className="text-sm text-white/70">{business.description}</p>
            </div>
            <div>
              <h4 className="text-sm font-bold tracking-wide uppercase mb-4">Quick Links</h4>
              <ul className="space-y-2">
                <li>
                  <Link to={`/business/${businessId}`} className="text-sm text-white/70 hover:text-white transition-colors">
                    Home
                  </Link>
                </li>
                <li>
                  <Link to={`/business/${businessId}/catalog`} className="text-sm text-white/70 hover:text-white transition-colors">
                    Catalog
                  </Link>
                </li>
                <li>
                  <Link to={`/business/${businessId}/contact`} className="text-sm text-white/70 hover:text-white transition-colors">
                    Contact
                  </Link>
                </li>
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