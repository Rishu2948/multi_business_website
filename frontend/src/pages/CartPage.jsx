import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useCart } from '../context/CartContext';
import { Trash2, Plus, Minus, ShoppingBag, ArrowRight } from 'lucide-react';

const CartPage = () => {
  const navigate = useNavigate();
  const { cart, loading, updateQuantity, removeFromCart } = useCart();
  const [subtotal, setSubtotal] = useState(0);
  const [tax, setTax] = useState(0);
  const [deliveryCharge] = useState(50); // Fixed delivery charge
  const [total, setTotal] = useState(0);

  useEffect(() => {
    if (cart && cart.items) {
      const sub = cart.items.reduce((sum, item) => sum + (item.price * item.quantity), 0);
      const taxAmount = sub * 0.05; // 5% tax
      setSubtotal(sub);
      setTax(taxAmount);
      setTotal(sub + taxAmount + deliveryCharge);
    }
  }, [cart, deliveryCharge]);

  const handleQuantityChange = async (item, newQuantity) => {
    if (newQuantity < 1) return;
    await updateQuantity(item.product_id, item.variant_id, newQuantity);
  };

  const handleRemove = async (item) => {
    await removeFromCart(item.product_id, item.variant_id);
  };

  if (!cart || !cart.items || cart.items.length === 0) {
    return (
      <div className="min-h-screen flex flex-col bg-white">
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center max-w-md">
            <ShoppingBag size={64} className="mx-auto text-muted mb-6" strokeWidth={1.5} />
            <h1 className="text-3xl font-black text-primary mb-4">YOUR CART IS EMPTY</h1>
            <p className="text-muted mb-8">Add some delicious items from our bakery to get started!</p>
            <Link
              to="/business/whisked_words/catalog"
              className="inline-flex items-center gap-2 bg-primary text-white hover:bg-[#333333] transition-all border border-primary px-8 py-4 font-bold tracking-wide"
              data-testid="browse-products-button"
            >
              BROWSE PRODUCTS
              <ArrowRight size={20} />
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface py-12" data-testid="cart-page">
      <div className="max-w-7xl mx-auto px-8">
        <h1 className="text-4xl font-black text-primary uppercase mb-8">SHOPPING CART</h1>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Cart Items */}
          <div className="lg:col-span-2">
            <div className="bg-white border border-border">
              {cart.items.map((item, index) => (
                <div
                  key={`${item.product_id}-${item.variant_id || 'default'}`}
                  className={`p-6 flex gap-6 ${index !== cart.items.length - 1 ? 'border-b border-border' : ''}`}
                  data-testid={`cart-item-${item.product_id}`}
                >
                  {/* Product Image */}
                  <div className="w-24 h-24 bg-surface flex-shrink-0 overflow-hidden">
                    {item.image_url ? (
                      <img src={item.image_url} alt={item.product_name} className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <ShoppingBag size={32} className="text-muted" />
                      </div>
                    )}
                  </div>

                  {/* Product Details */}
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold text-primary mb-2">{item.product_name}</h3>
                    {item.attributes && Object.keys(item.attributes).length > 0 && (
                      <div className="flex flex-wrap gap-2 mb-3">
                        {Object.entries(item.attributes).slice(0, 3).map(([key, value]) => (
                          <span key={key} className="text-xs px-2 py-1 bg-surface text-muted">
                            {Array.isArray(value) ? value[0] : value}
                          </span>
                        ))}
                      </div>
                    )}
                    <p className="text-xl font-bold text-primary">₹{item.price.toLocaleString()}</p>
                  </div>

                  {/* Quantity Controls */}
                  <div className="flex flex-col items-end gap-4">
                    <button
                      onClick={() => handleRemove(item)}
                      className="text-destructive hover:text-red-700 transition-colors"
                      data-testid={`remove-item-${item.product_id}`}
                    >
                      <Trash2 size={20} />
                    </button>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleQuantityChange(item, item.quantity - 1)}
                        disabled={loading || item.quantity <= 1}
                        className="w-8 h-8 bg-surface text-primary border border-border hover:bg-primary hover:text-white transition-all flex items-center justify-center disabled:opacity-50"
                        data-testid={`decrease-qty-${item.product_id}`}
                      >
                        <Minus size={16} />
                      </button>
                      <span className="w-12 text-center font-semibold text-primary" data-testid={`qty-${item.product_id}`}>
                        {item.quantity}
                      </span>
                      <button
                        onClick={() => handleQuantityChange(item, item.quantity + 1)}
                        disabled={loading}
                        className="w-8 h-8 bg-surface text-primary border border-border hover:bg-primary hover:text-white transition-all flex items-center justify-center"
                        data-testid={`increase-qty-${item.product_id}`}
                      >
                        <Plus size={16} />
                      </button>
                    </div>

                    <p className="text-sm text-muted">
                      Total: ₹{(item.price * item.quantity).toLocaleString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Order Summary */}
          <div className="lg:col-span-1">
            <div className="bg-white border border-border p-6 sticky top-24">
              <h2 className="text-xl font-bold text-primary mb-6">ORDER SUMMARY</h2>

              <div className="space-y-4 mb-6">
                <div className="flex justify-between text-base">
                  <span className="text-muted">Subtotal</span>
                  <span className="font-semibold text-primary">₹{subtotal.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-base">
                  <span className="text-muted">Tax (5%)</span>
                  <span className="font-semibold text-primary">₹{tax.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-base">
                  <span className="text-muted">Delivery</span>
                  <span className="font-semibold text-primary">₹{deliveryCharge.toFixed(2)}</span>
                </div>
                <div className="pt-4 border-t border-border flex justify-between text-lg">
                  <span className="font-bold text-primary">Total</span>
                  <span className="font-black text-primary">₹{total.toFixed(2)}</span>
                </div>
              </div>

              <button
                onClick={() => navigate('/checkout')}
                className="w-full bg-primary text-white hover:bg-[#333333] transition-all border border-primary px-8 py-4 font-bold tracking-wide flex items-center justify-center gap-2"
                data-testid="proceed-checkout-button"
              >
                PROCEED TO CHECKOUT
                <ArrowRight size={20} />
              </button>

              <Link
                to="/business/whisked_words/catalog"
                className="block text-center mt-4 text-sm text-muted hover:text-primary transition-colors"
              >
                ← Continue Shopping
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CartPage;