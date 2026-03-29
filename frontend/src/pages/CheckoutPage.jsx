import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCart } from '../context/CartContext';
import { useAuth } from '../context/AuthContext';
import apiClient from '../utils/api';
import { toast } from 'sonner';
import { CreditCard, Wallet, Truck } from 'lucide-react';

const CheckoutPage = () => {
  const navigate = useNavigate();
  const { cart } = useCart();
  const { user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState('stripe');

  const [deliveryInfo, setDeliveryInfo] = useState({
    name: user?.name || '',
    phone: '',
    email: user?.email || '',
    address: '',
    city: '',
    state: '',
    pincode: '',
    delivery_date: '',
    delivery_time: '',
    special_instructions: ''
  });

  const [subtotal, setSubtotal] = useState(0);
  const [tax, setTax] = useState(0);
  const [deliveryCharge] = useState(50);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    if (!cart || !cart.items || cart.items.length === 0) {
      navigate('/cart');
      return;
    }

    const sub = cart.items.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    const taxAmount = sub * 0.05;
    setSubtotal(sub);
    setTax(taxAmount);
    setTotal(sub + taxAmount + deliveryCharge);
  }, [cart, deliveryCharge, navigate]);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setDeliveryInfo(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Validate form
      if (!deliveryInfo.name || !deliveryInfo.phone || !deliveryInfo.email || 
          !deliveryInfo.address || !deliveryInfo.city || !deliveryInfo.state || !deliveryInfo.pincode) {
        toast.error('Please fill all required fields');
        setLoading(false);
        return;
      }

      // Create order
      const orderData = {
        items: cart.items.map(item => ({
          product_id: item.product_id,
          variant_id: item.variant_id,
          product_name: item.product_name,
          quantity: item.quantity,
          price: item.price,
          subtotal: item.price * item.quantity,
          image_url: item.image_url
        })),
        delivery_info: deliveryInfo,
        payment_method: paymentMethod,
        subtotal: subtotal,
        tax: tax,
        delivery_charge: deliveryCharge,
        total: total
      };

      const orderResponse = await apiClient.post('/orders/create', orderData);
      const orderId = orderResponse.data.order_id;

      if (paymentMethod === 'cod') {
        // For COD, order is created, navigate to success page
        toast.success('Order placed successfully!');
        navigate(`/order-success?order_id=${orderId}&payment_method=cod`);
      } else {
        // For online payment, create checkout session
        const originUrl = window.location.origin;
        const paymentResponse = await apiClient.post('/payments/create-checkout-session', {
          order_id: orderId,
          payment_method: paymentMethod,
          origin_url: originUrl
        });

        // Redirect to payment gateway
        if (paymentResponse.data.url) {
          window.location.href = paymentResponse.data.url;
        } else {
          throw new Error('Payment URL not received');
        }
      }
    } catch (error) {
      console.error('Checkout error:', error);
      toast.error(error.response?.data?.detail || 'Failed to process order');
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface py-12" data-testid="checkout-page">
      <div className="max-w-7xl mx-auto px-8">
        <h1 className="text-4xl font-black text-primary uppercase mb-8">CHECKOUT</h1>

        <form onSubmit={handleSubmit}>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Delivery Information */}
            <div className="lg:col-span-2 space-y-6">
              {/* Contact Information */}
              <div className="bg-white border border-border p-6">
                <h2 className="text-xl font-bold text-primary mb-6">CONTACT INFORMATION</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-primary mb-2">Full Name *</label>
                    <input
                      type="text"
                      name="name"
                      value={deliveryInfo.name}
                      onChange={handleInputChange}
                      required
                      className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
                      data-testid="input-name"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-primary mb-2">Phone *</label>
                    <input
                      type="tel"
                      name="phone"
                      value={deliveryInfo.phone}
                      onChange={handleInputChange}
                      required
                      placeholder="+91-XXXXXXXXXX"
                      className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
                      data-testid="input-phone"
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-primary mb-2">Email *</label>
                    <input
                      type="email"
                      name="email"
                      value={deliveryInfo.email}
                      onChange={handleInputChange}
                      required
                      className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
                      data-testid="input-email"
                    />
                  </div>
                </div>
              </div>

              {/* Delivery Address */}
              <div className="bg-white border border-border p-6">
                <h2 className="text-xl font-bold text-primary mb-6">DELIVERY ADDRESS</h2>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-primary mb-2">Address *</label>
                    <textarea
                      name="address"
                      value={deliveryInfo.address}
                      onChange={handleInputChange}
                      required
                      rows="3"
                      className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none resize-none"
                      data-testid="input-address"
                    />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-primary mb-2">City *</label>
                      <input
                        type="text"
                        name="city"
                        value={deliveryInfo.city}
                        onChange={handleInputChange}
                        required
                        className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
                        data-testid="input-city"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-primary mb-2">State *</label>
                      <input
                        type="text"
                        name="state"
                        value={deliveryInfo.state}
                        onChange={handleInputChange}
                        required
                        className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
                        data-testid="input-state"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-primary mb-2">Pincode *</label>
                      <input
                        type="text"
                        name="pincode"
                        value={deliveryInfo.pincode}
                        onChange={handleInputChange}
                        required
                        pattern="[0-9]{6}"
                        className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
                        data-testid="input-pincode"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Delivery Schedule */}
              <div className="bg-white border border-border p-6">
                <h2 className="text-xl font-bold text-primary mb-6">DELIVERY SCHEDULE (OPTIONAL)</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-primary mb-2">Preferred Date</label>
                    <input
                      type="date"
                      name="delivery_date"
                      value={deliveryInfo.delivery_date}
                      onChange={handleInputChange}
                      min={new Date().toISOString().split('T')[0]}
                      className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
                      data-testid="input-delivery-date"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-primary mb-2">Preferred Time</label>
                    <select
                      name="delivery_time"
                      value={deliveryInfo.delivery_time}
                      onChange={handleInputChange}
                      className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
                      data-testid="input-delivery-time"
                    >
                      <option value="">Any Time</option>
                      <option value="morning">Morning (9 AM - 12 PM)</option>
                      <option value="afternoon">Afternoon (12 PM - 4 PM)</option>
                      <option value="evening">Evening (4 PM - 8 PM)</option>
                    </select>
                  </div>
                </div>
                <div className="mt-4">
                  <label className="block text-sm font-medium text-primary mb-2">Special Instructions</label>
                  <textarea
                    name="special_instructions"
                    value={deliveryInfo.special_instructions}
                    onChange={handleInputChange}
                    rows="2"
                    placeholder="Any special delivery instructions..."
                    className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none resize-none"
                    data-testid="input-special-instructions"
                  />
                </div>
              </div>

              {/* Payment Method */}
              <div className="bg-white border border-border p-6">
                <h2 className="text-xl font-bold text-primary mb-6">PAYMENT METHOD</h2>
                <div className="space-y-3">
                  <label className="flex items-center gap-4 p-4 border border-border cursor-pointer hover:bg-surface transition-all">
                    <input
                      type="radio"
                      name="payment_method"
                      value="stripe"
                      checked={paymentMethod === 'stripe'}
                      onChange={(e) => setPaymentMethod(e.target.value)}
                      className="w-5 h-5"
                      data-testid="payment-stripe"
                    />
                    <CreditCard size={24} className="text-primary" />
                    <div className="flex-1">
                      <p className="font-semibold text-primary">Credit/Debit Card (Stripe)</p>
                      <p className="text-sm text-muted">Secure payment via Stripe</p>
                    </div>
                  </label>

                  <label className="flex items-center gap-4 p-4 border border-border cursor-pointer hover:bg-surface transition-all">
                    <input
                      type="radio"
                      name="payment_method"
                      value="razorpay"
                      checked={paymentMethod === 'razorpay'}
                      onChange={(e) => setPaymentMethod(e.target.value)}
                      className="w-5 h-5"
                      data-testid="payment-razorpay"
                    />
                    <Wallet size={24} className="text-primary" />
                    <div className="flex-1">
                      <p className="font-semibold text-primary">UPI / Cards / Wallets (Razorpay)</p>
                      <p className="text-sm text-muted">Pay with UPI, cards, netbanking, wallets</p>
                    </div>
                  </label>

                  <label className="flex items-center gap-4 p-4 border border-border cursor-pointer hover:bg-surface transition-all">
                    <input
                      type="radio"
                      name="payment_method"
                      value="cod"
                      checked={paymentMethod === 'cod'}
                      onChange={(e) => setPaymentMethod(e.target.value)}
                      className="w-5 h-5"
                      data-testid="payment-cod"
                    />
                    <Truck size={24} className="text-primary" />
                    <div className="flex-1">
                      <p className="font-semibold text-primary">Cash on Delivery</p>
                      <p className="text-sm text-muted">Pay when you receive</p>
                    </div>
                  </label>
                </div>
              </div>
            </div>

            {/* Order Summary */}
            <div className="lg:col-span-1">
              <div className="bg-white border border-border p-6 sticky top-24">
                <h2 className="text-xl font-bold text-primary mb-6">ORDER SUMMARY</h2>

                {/* Items */}
                <div className="space-y-4 mb-6 max-h-64 overflow-y-auto">
                  {cart?.items?.map((item) => (
                    <div key={`${item.product_id}-${item.variant_id}`} className="flex gap-3">
                      <div className="w-16 h-16 bg-surface flex-shrink-0">
                        {item.image_url && <img src={item.image_url} alt={item.product_name} className="w-full h-full object-cover" />}
                      </div>
                      <div className="flex-1">
                        <p className="text-sm font-medium text-primary line-clamp-2">{item.product_name}</p>
                        <p className="text-xs text-muted">Qty: {item.quantity}</p>
                        <p className="text-sm font-semibold text-primary">₹{(item.price * item.quantity).toFixed(2)}</p>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Totals */}
                <div className="space-y-3 mb-6 pt-4 border-t border-border">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted">Subtotal</span>
                    <span className="font-semibold text-primary">₹{subtotal.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted">Tax (5%)</span>
                    <span className="font-semibold text-primary">₹{tax.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted">Delivery</span>
                    <span className="font-semibold text-primary">₹{deliveryCharge.toFixed(2)}</span>
                  </div>
                  <div className="pt-3 border-t border-border flex justify-between">
                    <span className="font-bold text-primary">Total</span>
                    <span className="text-xl font-black text-primary">₹{total.toFixed(2)}</span>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-primary text-white hover:bg-[#333333] transition-all border border-primary px-8 py-4 font-bold tracking-wide disabled:opacity-50"
                  data-testid="place-order-button"
                >
                  {loading ? 'PROCESSING...' : paymentMethod === 'cod' ? 'PLACE ORDER' : 'PROCEED TO PAYMENT'}
                </button>
              </div>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

export default CheckoutPage;