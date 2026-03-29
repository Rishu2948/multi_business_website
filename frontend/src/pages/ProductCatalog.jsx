import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import Navbar from '../components/common/Navbar';
import Footer from '../components/common/Footer';
import { useCart } from '../context/CartContext';
import apiClient from '../utils/api';
import { Loader2, Package, ShoppingCart, Star, TrendingUp, Flame } from 'lucide-react';

const StarDisplay = ({ rating, count }) => (
  <div className="flex items-center gap-1.5">
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((s) => (
        <Star
          key={s}
          size={12}
          className={s <= Math.round(rating) ? 'fill-yellow-400 text-yellow-400' : 'text-border'}
        />
      ))}
    </div>
    <span className="text-xs font-semibold text-primary">{rating}</span>
    {count > 0 && <span className="text-xs text-muted">({count})</span>}
  </div>
);

const ProductCatalog = () => {
  const { businessId } = useParams();
  const { addToCart, loading: cartLoading } = useCart();
  const [business, setBusiness] = useState(null);
  const [products, setProducts] = useState([]);
  const [trending, setTrending] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [businessRes, productsRes, trendingRes] = await Promise.all([
          apiClient.get(`/businesses/${businessId}`),
          apiClient.get(`/products?business_id=${businessId}`),
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
  }, [businessId]);

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col">
        <Navbar />
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </div>
    );
  }

  if (!business) {
    return (
      <div className="min-h-screen flex flex-col">
        <Navbar />
        <div className="flex-1 flex items-center justify-center">
          <p className="text-muted">Business not found</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-white">
      <Navbar />

      {/* Business Header */}
      <section className="py-12 bg-surface border-b border-border" data-testid="catalog-header">
        <div className="max-w-7xl mx-auto px-8">
          <div className="flex items-start gap-8">
            <div className="w-24 h-24 bg-white border border-border overflow-hidden flex-shrink-0">
              <img
                src={business.logo_url}
                alt={business.business_name}
                className="w-full h-full object-cover"
              />
            </div>
            <div className="flex-1">
              <p className="text-xs tracking-[0.2em] uppercase font-bold text-muted mb-2">
                {business.business_type.replace('_', ' ')}
              </p>
              <h1 className="text-4xl font-black tracking-tight text-primary uppercase mb-3">
                {business.business_name}
              </h1>
              <p className="text-base text-muted mb-4">{business.description}</p>
              <div className="flex items-center gap-6 text-sm text-muted">
                <span>{business.contact.email}</span>
                <span>{business.contact.phone}</span>
                <span>{business.contact.address.city}, {business.contact.address.state}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Trending / Bestsellers Section */}
      {trending.length > 0 && (
        <section className="py-12 border-b border-border bg-[#FAFAFA]" data-testid="trending-section">
          <div className="max-w-7xl mx-auto px-8">
            <div className="flex items-center gap-3 mb-8">
              <div className="w-10 h-10 bg-primary flex items-center justify-center">
                <Flame size={20} className="text-white" strokeWidth={1.5} />
              </div>
              <div>
                <h2 className="text-2xl font-black tracking-tight text-primary uppercase">TRENDING NOW</h2>
                <p className="text-xs tracking-wide text-muted">Bestsellers ranked by popularity and ratings</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {trending.map((product, index) => (
                <div
                  key={product.product_id}
                  className="bg-white border border-border group hover:-translate-y-1 hover:shadow-lg transition-all duration-300 relative"
                  data-testid={`trending-card-${product.product_id}`}
                >
                  {/* Rank Badge */}
                  <div className="absolute top-3 left-3 z-10 w-8 h-8 bg-primary text-white flex items-center justify-center font-black text-sm"
                       data-testid={`trending-rank-${index + 1}`}>
                    {index + 1}
                  </div>

                  {/* Product Image */}
                  <div className="aspect-[4/3] overflow-hidden">
                    {product.images && product.images.length > 0 ? (
                      <img
                        src={product.images[0].url}
                        alt={product.product_name}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                    ) : (
                      <div className="w-full h-full bg-surface flex items-center justify-center">
                        <Package size={36} className="text-muted" strokeWidth={1.5} />
                      </div>
                    )}
                  </div>

                  {/* Info */}
                  <div className="p-4">
                    <h3 className="text-sm font-bold text-primary mb-1.5 line-clamp-1">{product.product_name}</h3>

                    {/* Rating + Stats */}
                    <div className="flex items-center justify-between mb-3">
                      <StarDisplay rating={product.avg_rating} count={product.review_count} />
                      {product.total_ordered > 0 && (
                        <div className="flex items-center gap-1 text-xs text-muted">
                          <TrendingUp size={12} />
                          <span>{product.total_ordered} sold</span>
                        </div>
                      )}
                    </div>

                    {/* Price + CTA */}
                    <div className="flex items-center justify-between">
                      <p className="text-lg font-black text-primary">
                        {product.currency === 'INR' ? '₹' : '$'}{product.base_price.toLocaleString()}
                      </p>
                      <button
                        onClick={() => addToCart(product.product_id, null, 1)}
                        disabled={cartLoading}
                        className="bg-primary text-white hover:bg-[#333333] transition-all px-3 py-2 text-xs font-bold tracking-wide flex items-center gap-1 disabled:opacity-50"
                        data-testid={`trending-add-to-cart-${product.product_id}`}
                      >
                        <ShoppingCart size={14} />
                        ADD
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Products Section */}
      <main className="flex-1 py-16" data-testid="products-section">
        <div className="max-w-7xl mx-auto px-8">
          <div className="mb-12 flex items-end justify-between">
            <div>
              <h2 className="text-2xl font-bold text-primary mb-2">All Products</h2>
              <p className="text-sm text-muted">{products.length} products available</p>
            </div>
            {businessId === 'whisked_words' && (
              <Link
                to={`/business/${businessId}/custom-order`}
                className="bg-accent text-white hover:bg-[#002280] transition-all border border-accent px-6 py-3 font-bold text-sm tracking-wide"
                data-testid="custom-cake-order-button"
              >
                CUSTOM CAKE ORDER
              </Link>
            )}
          </div>

          {products.length === 0 ? (
            <div className="text-center py-20">
              <Package size={48} className="mx-auto text-muted mb-4" strokeWidth={1.5} />
              <p className="text-muted">No products available yet.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {products.map((product) => (
                <div
                  key={product.product_id}
                  className="bg-white border border-border group hover:-translate-y-1 hover:shadow-lg transition-all duration-300"
                  data-testid={`product-card-${product.product_id}`}
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

                    {/* Price and Add to Cart */}
                    <div className="pt-4 border-t border-border">
                      <div className="flex items-center justify-between mb-4">
                        <p className="text-2xl font-bold text-primary">
                          {product.currency === 'INR' ? '₹' : '$'}{product.base_price.toLocaleString()}
                        </p>
                      </div>
                      
                      <button
                        onClick={() => addToCart(product.product_id, null, 1)}
                        disabled={cartLoading}
                        className="w-full bg-accent text-white hover:bg-[#002280] transition-all border border-accent px-4 py-3 font-bold tracking-wide flex items-center justify-center gap-2 disabled:opacity-50"
                        data-testid={`add-to-cart-${product.product_id}`}
                      >
                        <ShoppingCart size={18} />
                        {cartLoading ? 'ADDING...' : 'ADD TO CART'}
                      </button>
                    </div>

                    {/* Attributes Preview */}
                    {product.attributes && Object.keys(product.attributes).length > 0 && (
                      <div className="mt-4 pt-4 border-t border-border">
                        <div className="flex flex-wrap gap-2">
                          {Object.entries(product.attributes).slice(0, 3).map(([key, value]) => (
                            <span
                              key={key}
                              className="text-xs px-2 py-1 bg-surface text-muted font-medium"
                            >
                              {Array.isArray(value) ? value[0] : value}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Reviews Link */}
                    <Link
                      to={`/reviews/${product.product_id}`}
                      className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-accent hover:text-[#002280] transition-colors"
                      data-testid={`reviews-link-${product.product_id}`}
                    >
                      <Star size={12} />
                      View Reviews
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>

      <Footer />
    </div>
  );
};

export default ProductCatalog;
