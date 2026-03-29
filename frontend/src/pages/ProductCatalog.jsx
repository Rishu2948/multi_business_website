import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import Navbar from '../components/common/Navbar';
import Footer from '../components/common/Footer';
import { useCart } from '../context/CartContext';
import apiClient from '../utils/api';
import { Loader2, Package, ShoppingCart, Plus } from 'lucide-react';

const ProductCatalog = () => {
  const { businessId } = useParams();
  const { addToCart, loading: cartLoading } = useCart();
  const [business, setBusiness] = useState(null);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [businessRes, productsRes] = await Promise.all([
          apiClient.get(`/businesses/${businessId}`),
          apiClient.get(`/products?business_id=${businessId}`)
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

      {/* Products Section */}
      <main className="flex-1 py-16" data-testid="products-section">
        <div className="max-w-7xl mx-auto px-8">
          <div className="mb-12">
            <h2 className="text-2xl font-bold text-primary mb-2">Product Catalog</h2>
            <p className="text-sm text-muted">{products.length} products available</p>
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