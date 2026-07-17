import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import BakeryNavbar from '../components/common/BakeryNavbar';
import BakeryFooter from '../components/common/BakeryFooter';
import AnnouncementBar from '../components/common/AnnouncementBar';
import { useCart } from '../context/CartContext';
import { ShoppingCart, Minus, Plus, Trash2, ArrowRight } from 'lucide-react';

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: (i = 0) => ({ opacity: 1, y: 0, transition: { delay: i * 0.06, duration: 0.5 } }),
};

const CartPage = () => {
  const { cart, updateQuantity, removeFromCart, loading } = useCart();
  const items = cart?.items || [];
  const total = cart?.total_amount || 0;

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5]">
      <AnnouncementBar businessId="whisked_words" />
      <BakeryNavbar />

      {/* Extra bottom padding on mobile for sticky bar */}
      <main className="flex-1 py-8 md:py-16 lg:py-24 pb-28 lg:pb-16">
        <div className="max-w-5xl mx-auto px-4 md:px-6 lg:px-12">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <p className="text-xs tracking-[0.2em] uppercase text-[#D4A373] font-semibold mb-2">Your Selection</p>
            <h1 className="font-serif text-3xl md:text-4xl lg:text-5xl text-[#2C2420] mb-8 md:mb-12"
                data-testid="cart-title">Shopping Cart</h1>
          </motion.div>

          {items.length === 0 ? (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center py-16 md:py-24">
              <ShoppingCart size={48} className="mx-auto text-[#786A60] mb-6" strokeWidth={1} aria-hidden="true" />
              <p className="font-serif text-2xl text-[#2C2420] mb-3">Your cart is empty</p>
              <p className="text-sm text-[#786A60] mb-8">Browse our collection and find something you love</p>
              <Link to="/business/whisked_words/catalog"
                className="bg-[#4A3B32] text-white px-8 py-4 text-xs tracking-[0.15em] uppercase font-semibold
                           hover:bg-[#332822] transition-colors inline-flex items-center gap-2"
                data-testid="continue-shopping-button">
                Continue Shopping
              </Link>
            </motion.div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12">
              {/* Items */}
              <div className="lg:col-span-8" data-testid="cart-items-list">
                {/* Desktop header */}
                <div className="border-b border-[#E8E0D5] pb-3 mb-4 hidden md:grid grid-cols-12 gap-4">
                  {['Product','Quantity','Price','Total'].map((h, i) => (
                    <span key={h}
                      className={`text-xs tracking-[0.15em] uppercase text-[#786A60] font-semibold
                        ${i === 0 ? 'col-span-6' : i === 1 ? 'col-span-2 text-center' : 'col-span-2 text-right'}`}>
                      {h}
                    </span>
                  ))}
                </div>

                {items.map((item, i) => {
                  const itemTotal = (item.price + (item.addons_price || 0)) * item.quantity;
                  return (
                    <motion.div key={`${item.product_id}-${i}`}
                      variants={fadeUp} custom={i} initial="hidden" animate="visible"
                      className="py-5 border-b border-[#E8E0D5] relative overflow-hidden"
                      drag="x"
                      dragConstraints={{ left: -80, right: 0 }}
                      dragElastic={0.1}
                      onDragEnd={(_, info) => {
                        if (info.offset.x < -60) {
                          removeFromCart(item.product_id);
                        }
                      }}
                      whileDrag={{ cursor: 'grabbing' }}
                      data-testid={`cart-item-${item.product_id}`}>

                      {/* Swipe hint — revealed on drag left */}
                      <div className="absolute right-0 top-0 bottom-0 w-20 bg-red-500 flex items-center justify-center z-0">
                        <Trash2 size={20} className="text-white" />
                      </div>

                      {/* Card content — sits above swipe background */}
                      <div className="relative z-10 bg-[#FAF8F5]">

                      {/* Mobile layout */}
                      <div className="flex items-start gap-3 md:hidden">
                        <div className="w-16 h-16 bg-[#F3EFEA] flex-shrink-0 overflow-hidden rounded-sm">
                          {item.image_url
                            ? <img src={item.image_url} alt={item.product_name} className="w-full h-full object-cover" />
                            : <ShoppingCart size={18} className="m-auto mt-5 text-[#786A60]" aria-hidden="true" />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-serif text-sm text-[#2C2420] line-clamp-2">{item.product_name}</p>
                          {item.selected_addons?.length > 0 && (
                            <p className="text-[11px] text-[#786A60] mt-0.5 line-clamp-1">
                              + {item.selected_addons.flatMap(g => g.selected_items.map(si => si.name)).join(', ')}
                            </p>
                          )}
                          <p className="text-sm font-semibold text-[#2C2420] mt-1">₹{itemTotal.toLocaleString()}</p>
                          <div className="flex items-center gap-3 mt-2">
                            <div className="flex items-center border border-[#E8E0D5]">
                              <button onClick={() => updateQuantity(item.product_id, null, Math.max(1, item.quantity - 1))}
                                disabled={loading}
                                className="px-2 py-1.5 text-[#4A3B32] hover:bg-[#F3EFEA] min-h-[36px]"
                                data-testid={`decrease-qty-${item.product_id}`}>
                                <Minus size={12} />
                              </button>
                              <span className="px-3 text-sm font-semibold text-[#2C2420] min-w-[32px] text-center"
                                data-testid={`qty-${item.product_id}`}>{item.quantity}</span>
                              <button onClick={() => updateQuantity(item.product_id, null, item.quantity + 1)}
                                disabled={loading}
                                className="px-2 py-1.5 text-[#4A3B32] hover:bg-[#F3EFEA] min-h-[36px]"
                                data-testid={`increase-qty-${item.product_id}`}>
                                <Plus size={12} />
                              </button>
                            </div>
                            <button onClick={() => removeFromCart(item.product_id)} disabled={loading}
                              className="text-xs text-[#D4A373] hover:text-[#4A3B32] flex items-center gap-1"
                              data-testid={`remove-item-${item.product_id}`}>
                              <Trash2 size={12} /> Remove
                            </button>
                          </div>
                        </div>
                      </div>

                      {/* Desktop layout */}
                      <div className="hidden md:grid grid-cols-12 gap-4 items-center">
                        <div className="col-span-6 flex items-center gap-4">
                          <div className="w-16 h-16 bg-[#F3EFEA] overflow-hidden flex-shrink-0">
                            {item.image_url
                              ? <img src={item.image_url} alt={item.product_name} className="w-full h-full object-cover" />
                              : <ShoppingCart size={18} className="m-auto mt-5 text-[#786A60]" aria-hidden="true" />}
                          </div>
                          <div>
                            <h3 className="font-serif text-base text-[#2C2420]">{item.product_name}</h3>
                            {item.selected_addons?.length > 0 && (
                              <p className="text-xs text-[#786A60] mt-0.5">
                                + {item.selected_addons.flatMap(g => g.selected_items.map(si => si.name)).join(', ')}
                              </p>
                            )}
                            <button onClick={() => removeFromCart(item.product_id)} disabled={loading}
                              className="text-xs text-[#D4A373] hover:text-[#4A3B32] mt-1 flex items-center gap-1"
                              data-testid={`remove-item-${item.product_id}`}>
                              <Trash2 size={12} /> Remove
                            </button>
                          </div>
                        </div>
                        <div className="col-span-2 flex justify-center">
                          <div className="flex items-center border border-[#E8E0D5]">
                            <button onClick={() => updateQuantity(item.product_id, null, Math.max(1, item.quantity - 1))}
                              disabled={loading}
                              className="px-3 py-2 text-[#4A3B32] hover:bg-[#F3EFEA]"
                              data-testid={`decrease-qty-${item.product_id}`}>
                              <Minus size={13} />
                            </button>
                            <span className="px-4 py-2 text-sm font-semibold text-[#2C2420] min-w-[40px] text-center"
                              data-testid={`qty-${item.product_id}`}>{item.quantity}</span>
                            <button onClick={() => updateQuantity(item.product_id, null, item.quantity + 1)}
                              disabled={loading}
                              className="px-3 py-2 text-[#4A3B32] hover:bg-[#F3EFEA]"
                              data-testid={`increase-qty-${item.product_id}`}>
                              <Plus size={13} />
                            </button>
                          </div>
                        </div>
                        <div className="col-span-2 text-right">
                          <p className="text-sm text-[#786A60]">₹{(item.price + (item.addons_price || 0)).toLocaleString()}</p>
                        </div>
                        <div className="col-span-2 text-right">
                          <p className="text-sm font-semibold text-[#2C2420]">₹{itemTotal.toLocaleString()}</p>
                        </div>
                      </div>
                      </div>
                    </motion.div>
                  );
                })}
              </div>

              {/* Desktop order summary */}
              <div className="lg:col-span-4 hidden lg:block">
                <div className="sticky top-28 bg-white border border-[#E8E0D5] p-8" data-testid="cart-summary">
                  <h3 className="font-serif text-xl text-[#2C2420] mb-6">Order Summary</h3>
                  <div className="space-y-3 mb-6 pb-6 border-b border-[#E8E0D5]">
                    <div className="flex justify-between text-sm">
                      <span className="text-[#786A60]">Subtotal ({items.length} item{items.length > 1 ? 's' : ''})</span>
                      <span className="text-[#2C2420] font-medium">₹{total.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-[#786A60]">Delivery</span>
                      <span className="text-[#A3B18A] font-medium">At checkout</span>
                    </div>
                  </div>
                  <div className="flex justify-between mb-8">
                    <span className="font-serif text-lg text-[#2C2420]">Total</span>
                    <span className="font-serif text-xl text-[#2C2420]" data-testid="cart-total">
                      ₹{total.toLocaleString()}
                    </span>
                  </div>
                  <Link to="/checkout"
                    className="w-full bg-[#4A3B32] text-white py-4 text-xs tracking-[0.15em] uppercase font-semibold
                               hover:bg-[#332822] transition-colors flex items-center justify-center gap-2"
                    data-testid="checkout-button">
                    Proceed to Checkout <ArrowRight size={14} />
                  </Link>
                  <Link to="/business/whisked_words/catalog"
                    className="block text-center mt-4 text-xs tracking-[0.1em] uppercase text-[#D4A373] hover:text-[#4A3B32] font-semibold">
                    Continue Shopping
                  </Link>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Mobile sticky checkout bar */}
      {items.length > 0 && (
        <div className="lg:hidden fixed bottom-0 left-0 right-0 z-40 bg-white border-t border-[#E8E0D5]
                        px-4 py-3 pb-[calc(12px+env(safe-area-inset-bottom))]">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-[#786A60]">{items.length} item{items.length > 1 ? 's' : ''}</span>
            <span className="font-semibold text-[#2C2420]" data-testid="cart-total-mobile">₹{total.toLocaleString()}</span>
          </div>
          <Link to="/checkout"
            className="block w-full bg-[#4A3B32] text-white py-3 text-center text-sm font-semibold
                       hover:bg-[#332822] transition-colors"
            data-testid="mobile-checkout-button">
            Proceed to Checkout →
          </Link>
        </div>
      )}

      <BakeryFooter />
    </div>
  );
};

export default CartPage;
