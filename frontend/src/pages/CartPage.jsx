import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import BakeryNavbar from '../components/common/BakeryNavbar';
import BakeryFooter from '../components/common/BakeryFooter';
import { useCart } from '../context/CartContext';
import { ShoppingCart, Minus, Plus, Trash2, ArrowRight } from 'lucide-react';

const fadeUp = { hidden: { opacity: 0, y: 20 }, visible: (i = 0) => ({ opacity: 1, y: 0, transition: { delay: i * 0.06, duration: 0.5, ease: [0.22, 1, 0.36, 1] } }) };

const CartPage = () => {
  const { cart, updateQuantity, removeFromCart, loading } = useCart();
  const items = cart?.items || [];
  const total = cart?.total_amount || 0;

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5]">
      <BakeryNavbar />

      <main className="flex-1 py-16 md:py-24">
        <div className="max-w-5xl mx-auto px-6 md:px-12">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <p className="text-xs tracking-[0.2em] uppercase text-[#D4A373] font-semibold mb-2">Your Selection</p>
            <h1 className="font-serif text-4xl md:text-5xl text-[#2C2420] mb-12" data-testid="cart-title">Shopping Cart</h1>
          </motion.div>

          {items.length === 0 ? (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center py-24">
              <ShoppingCart size={48} className="mx-auto text-[#786A60] mb-6" strokeWidth={1} />
              <p className="font-serif text-2xl text-[#2C2420] mb-3">Your cart is empty</p>
              <p className="text-sm text-[#786A60] mb-8">Browse our collection and find something you love</p>
              <Link to="/business/whisked_words/catalog" className="bg-[#4A3B32] text-white px-8 py-4 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#332822] transition-colors duration-300 inline-flex items-center gap-2" data-testid="continue-shopping-button">
                Continue Shopping
              </Link>
            </motion.div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">
              {/* Cart Items */}
              <div className="lg:col-span-8" data-testid="cart-items-list">
                <div className="border-b border-[#E8E0D5] pb-3 mb-6 hidden md:grid grid-cols-12 gap-4">
                  <span className="col-span-6 text-xs tracking-[0.15em] uppercase text-[#786A60] font-semibold">Product</span>
                  <span className="col-span-2 text-xs tracking-[0.15em] uppercase text-[#786A60] font-semibold text-center">Quantity</span>
                  <span className="col-span-2 text-xs tracking-[0.15em] uppercase text-[#786A60] font-semibold text-right">Price</span>
                  <span className="col-span-2 text-xs tracking-[0.15em] uppercase text-[#786A60] font-semibold text-right">Total</span>
                </div>

                {items.map((item, i) => (
                  <motion.div
                    key={item.product_id}
                    variants={fadeUp}
                    custom={i}
                    initial="hidden"
                    animate="visible"
                    className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center py-6 border-b border-[#E8E0D5]"
                    data-testid={`cart-item-${item.product_id}`}
                  >
                    {/* Product */}
                    <div className="md:col-span-6 flex items-center gap-4">
                      <div className="w-20 h-20 bg-[#F3EFEA] overflow-hidden flex-shrink-0">
                        {item.image_url ? (
                          <img src={item.image_url} alt={item.product_name} className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center"><ShoppingCart size={20} className="text-[#786A60]" /></div>
                        )}
                      </div>
                      <div>
                        <h3 className="font-serif text-base text-[#2C2420]">{item.product_name}</h3>
                        <button onClick={() => removeFromCart(item.product_id)} disabled={loading} className="text-xs text-[#D4A373] hover:text-[#4A3B32] transition-colors mt-1 flex items-center gap-1" data-testid={`remove-item-${item.product_id}`}>
                          <Trash2 size={12} /> Remove
                        </button>
                      </div>
                    </div>

                    {/* Quantity */}
                    <div className="md:col-span-2 flex items-center justify-center">
                      <div className="flex items-center border border-[#E8E0D5]">
                        <button onClick={() => updateQuantity(item.product_id, null, Math.max(1, item.quantity - 1))} disabled={loading} className="px-3 py-2 text-[#4A3B32] hover:bg-[#F3EFEA] transition-colors" data-testid={`decrease-qty-${item.product_id}`}>
                          <Minus size={14} />
                        </button>
                        <span className="px-4 py-2 text-sm font-semibold text-[#2C2420] min-w-[40px] text-center" data-testid={`qty-${item.product_id}`}>{item.quantity}</span>
                        <button onClick={() => updateQuantity(item.product_id, null, item.quantity + 1)} disabled={loading} className="px-3 py-2 text-[#4A3B32] hover:bg-[#F3EFEA] transition-colors" data-testid={`increase-qty-${item.product_id}`}>
                          <Plus size={14} />
                        </button>
                      </div>
                    </div>

                    {/* Price */}
                    <div className="md:col-span-2 text-right">
                      <p className="text-sm text-[#786A60]">₹{item.price?.toLocaleString()}</p>
                    </div>

                    {/* Subtotal */}
                    <div className="md:col-span-2 text-right">
                      <p className="text-sm font-semibold text-[#2C2420]">₹{(item.price * item.quantity).toLocaleString()}</p>
                    </div>
                  </motion.div>
                ))}
              </div>

              {/* Order Summary */}
              <div className="lg:col-span-4">
                <div className="sticky top-28 bg-white border border-[#E8E0D5] p-8" data-testid="cart-summary">
                  <h3 className="font-serif text-xl text-[#2C2420] mb-6">Order Summary</h3>

                  <div className="space-y-3 mb-6 pb-6 border-b border-[#E8E0D5]">
                    <div className="flex justify-between text-sm">
                      <span className="text-[#786A60]">Subtotal ({items.length} items)</span>
                      <span className="text-[#2C2420] font-medium">₹{total.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-[#786A60]">Delivery</span>
                      <span className="text-[#A3B18A] font-medium">Calculated at checkout</span>
                    </div>
                  </div>

                  <div className="flex justify-between mb-8">
                    <span className="font-serif text-lg text-[#2C2420]">Total</span>
                    <span className="font-serif text-xl text-[#2C2420]" data-testid="cart-total">₹{total.toLocaleString()}</span>
                  </div>

                  <Link
                    to="/checkout"
                    className="w-full bg-[#4A3B32] text-white py-4 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#332822] transition-colors duration-300 flex items-center justify-center gap-2"
                    data-testid="checkout-button"
                  >
                    Proceed to Checkout <ArrowRight size={14} />
                  </Link>

                  <Link to="/business/whisked_words/catalog" className="block text-center mt-4 text-xs tracking-[0.1em] uppercase text-[#D4A373] hover:text-[#4A3B32] font-semibold transition-colors">
                    Continue Shopping
                  </Link>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      <BakeryFooter />
    </div>
  );
};

export default CartPage;
