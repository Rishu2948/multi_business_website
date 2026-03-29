import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import BakeryNavbar from '../components/common/BakeryNavbar';
import BakeryFooter from '../components/common/BakeryFooter';
import { useCart } from '../context/CartContext';
import { useAuth } from '../context/AuthContext';
import apiClient from '../utils/api';
import { toast } from 'sonner';
import { CreditCard, Truck, Wallet } from 'lucide-react';

const CheckoutPage = () => {
  const navigate = useNavigate();
  const { cart, clearCart } = useCart();
  const { isAuthenticated } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState('cod');
  const [delivery, setDelivery] = useState({ name: '', phone: '', email: '', address: '', city: '', state: '', pincode: '' });

  const items = cart?.items || [];
  const subtotal = cart?.total_amount || 0;
  const tax = Math.round(subtotal * 0.05 * 100) / 100;
  const deliveryCharge = subtotal >= 500 ? 0 : 50;
  const total = subtotal + tax + deliveryCharge;

  const inputClass = "w-full border border-[#E8E0D5] px-4 py-3 focus:ring-1 focus:ring-[#4A3B32] focus:border-[#4A3B32] transition-all outline-none bg-white text-[#2C2420]";

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!isAuthenticated) { toast.error('Please login to place an order'); navigate('/login'); return; }
    if (items.length === 0) { toast.error('Cart is empty'); return; }
    if (!delivery.name || !delivery.phone || !delivery.address || !delivery.city || !delivery.state || !delivery.pincode) { toast.error('Please fill delivery details'); return; }

    setSubmitting(true);
    try {
      const orderPayload = {
        items: items.map(item => ({ product_id: item.product_id, variant_id: null, product_name: item.product_name, quantity: item.quantity, price: item.price, subtotal: item.price * item.quantity })),
        delivery_info: delivery, payment_method: paymentMethod, subtotal, tax, delivery_charge: deliveryCharge, total
      };

      if (paymentMethod === 'stripe') {
        const paymentRes = await apiClient.post('/payments/stripe/create-session', { items: orderPayload.items, delivery_info: delivery, subtotal, tax, delivery_charge: deliveryCharge, total });
        if (paymentRes.data.checkout_url) { window.location.href = paymentRes.data.checkout_url; return; }
      }

      const orderRes = await apiClient.post('/orders/create', orderPayload);
      await clearCart();
      toast.success('Order placed successfully!');
      navigate(`/order-success?orderId=${orderRes.data.order_id}&method=${paymentMethod}`);
    } catch (error) { toast.error(error.response?.data?.detail || 'Failed to place order'); }
    finally { setSubmitting(false); }
  };

  if (items.length === 0) {
    return (
      <div className="min-h-screen flex flex-col bg-[#FAF8F5]"><BakeryNavbar />
        <div className="flex-1 flex items-center justify-center flex-col gap-4 py-24">
          <p className="font-serif text-2xl text-[#2C2420]">Your cart is empty</p>
          <button onClick={() => navigate('/business/whisked_words/catalog')} className="bg-[#4A3B32] text-white px-8 py-4 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#332822] transition-colors">Browse Products</button>
        </div>
      <BakeryFooter /></div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5]" data-testid="checkout-page">
      <BakeryNavbar />

      <main className="flex-1 py-16 md:py-24">
        <div className="max-w-6xl mx-auto px-6 md:px-12">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <p className="text-xs tracking-[0.2em] uppercase text-[#D4A373] font-semibold mb-2">Final Step</p>
            <h1 className="font-serif text-4xl md:text-5xl text-[#2C2420] mb-12">Checkout</h1>
          </motion.div>

          <form onSubmit={handleSubmit}>
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">
              {/* Left: Forms */}
              <div className="lg:col-span-7 space-y-10">
                {/* Delivery */}
                <div className="bg-white border border-[#E8E0D5] p-8" data-testid="delivery-info-section">
                  <h2 className="font-serif text-xl text-[#2C2420] mb-6">Delivery Details</h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Full Name *</label><input type="text" value={delivery.name} onChange={(e) => setDelivery(d => ({ ...d, name: e.target.value }))} className={inputClass} data-testid="checkout-input-name" /></div>
                    <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Phone *</label><input type="tel" value={delivery.phone} onChange={(e) => setDelivery(d => ({ ...d, phone: e.target.value }))} className={inputClass} data-testid="checkout-input-phone" /></div>
                    <div className="md:col-span-2"><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Email</label><input type="email" value={delivery.email} onChange={(e) => setDelivery(d => ({ ...d, email: e.target.value }))} className={inputClass} data-testid="checkout-input-email" /></div>
                    <div className="md:col-span-2"><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Address *</label><textarea value={delivery.address} onChange={(e) => setDelivery(d => ({ ...d, address: e.target.value }))} rows="2" className={`${inputClass} resize-none`} data-testid="checkout-input-address" /></div>
                    <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">City *</label><input type="text" value={delivery.city} onChange={(e) => setDelivery(d => ({ ...d, city: e.target.value }))} className={inputClass} data-testid="checkout-input-city" /></div>
                    <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">State *</label><input type="text" value={delivery.state} onChange={(e) => setDelivery(d => ({ ...d, state: e.target.value }))} className={inputClass} data-testid="checkout-input-state" /></div>
                    <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Pincode *</label><input type="text" value={delivery.pincode} onChange={(e) => setDelivery(d => ({ ...d, pincode: e.target.value }))} className={inputClass} data-testid="checkout-input-pincode" /></div>
                  </div>
                </div>

                {/* Payment */}
                <div className="bg-white border border-[#E8E0D5] p-8" data-testid="payment-method-section">
                  <h2 className="font-serif text-xl text-[#2C2420] mb-6">Payment Method</h2>
                  <div className="space-y-3">
                    {[
                      { value: 'cod', label: 'Cash on Delivery', icon: Truck, desc: 'Pay when your order arrives' },
                      { value: 'stripe', label: 'Card / UPI (Stripe)', icon: CreditCard, desc: 'Secure online payment' },
                      { value: 'razorpay', label: 'Razorpay', icon: Wallet, desc: 'UPI, Cards, Netbanking' }
                    ].map(({ value, label, icon: Icon, desc }) => (
                      <button key={value} type="button" onClick={() => setPaymentMethod(value)} className={`w-full p-5 border text-left flex items-center gap-4 transition-all ${paymentMethod === value ? 'border-[#D4A373] bg-[#D4A373]/5' : 'border-[#E8E0D5] hover:bg-[#FAF8F5]'}`} data-testid={`payment-${value}`}>
                        <div className={`w-10 h-10 flex items-center justify-center ${paymentMethod === value ? 'bg-[#4A3B32]' : 'bg-[#F3EFEA]'}`}>
                          <Icon size={18} className={paymentMethod === value ? 'text-white' : 'text-[#786A60]'} />
                        </div>
                        <div>
                          <p className="font-semibold text-[#2C2420] text-sm">{label}</p>
                          <p className="text-xs text-[#786A60]">{desc}</p>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Right: Order Summary */}
              <div className="lg:col-span-5">
                <div className="sticky top-28 bg-white border border-[#E8E0D5] p-8" data-testid="order-summary">
                  <h2 className="font-serif text-xl text-[#2C2420] mb-6">Order Summary</h2>

                  <div className="space-y-4 mb-6 pb-6 border-b border-[#E8E0D5]">
                    {items.map((item) => (
                      <div key={item.product_id} className="flex items-center justify-between" data-testid={`summary-item-${item.product_id}`}>
                        <div className="flex items-center gap-3">
                          <div className="w-12 h-12 bg-[#F3EFEA] overflow-hidden flex-shrink-0">{item.image_url && <img src={item.image_url} alt={item.product_name} className="w-full h-full object-cover" />}</div>
                          <div><p className="text-sm font-medium text-[#2C2420]">{item.product_name}</p><p className="text-xs text-[#786A60]">Qty: {item.quantity}</p></div>
                        </div>
                        <p className="text-sm font-medium text-[#2C2420]">₹{(item.price * item.quantity).toLocaleString()}</p>
                      </div>
                    ))}
                  </div>

                  <div className="space-y-2 mb-6 pb-6 border-b border-[#E8E0D5] text-sm">
                    <div className="flex justify-between"><span className="text-[#786A60]">Subtotal</span><span className="text-[#2C2420]">₹{subtotal.toLocaleString()}</span></div>
                    <div className="flex justify-between"><span className="text-[#786A60]">Tax (5%)</span><span className="text-[#2C2420]">₹{tax.toLocaleString()}</span></div>
                    <div className="flex justify-between"><span className="text-[#786A60]">Delivery</span><span className={deliveryCharge === 0 ? 'text-[#A3B18A]' : 'text-[#2C2420]'}>{deliveryCharge === 0 ? 'Free' : `₹${deliveryCharge}`}</span></div>
                  </div>

                  <div className="flex justify-between mb-8">
                    <span className="font-serif text-lg text-[#2C2420]">Total</span>
                    <span className="font-serif text-xl text-[#2C2420]" data-testid="checkout-total">₹{total.toLocaleString()}</span>
                  </div>

                  <button type="submit" disabled={submitting} className="w-full bg-[#4A3B32] text-white py-4 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#332822] transition-colors duration-300 disabled:opacity-50" data-testid="place-order-button">
                    {submitting ? 'Processing...' : 'Place Order'}
                  </button>

                  {subtotal < 500 && <p className="text-xs text-[#D4A373] text-center mt-3">Add ₹{(500 - subtotal).toLocaleString()} more for free delivery</p>}
                </div>
              </div>
            </div>
          </form>
        </div>
      </main>

      <BakeryFooter />
    </div>
  );
};

export default CheckoutPage;
