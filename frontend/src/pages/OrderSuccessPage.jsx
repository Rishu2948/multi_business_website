import { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import BakeryNavbar from '../components/common/BakeryNavbar';
import BakeryFooter from '../components/common/BakeryFooter';
import apiClient from '../utils/api';
import { CheckCircle, Package, CreditCard, MapPin } from 'lucide-react';

const OrderSuccessPage = () => {
  const [searchParams] = useSearchParams();
  const orderId = searchParams.get('orderId');
  const method = searchParams.get('method');
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!orderId) { setLoading(false); return; }
    const fetchOrder = async () => {
      try {
        const res = await apiClient.get(`/orders/${orderId}`);
        setOrder(res.data);
      } catch (error) { console.error('Error:', error); }
      finally { setLoading(false); }
    };
    fetchOrder();
  }, [orderId]);

  if (loading) {
    return (<div className="min-h-screen flex flex-col bg-[#FAF8F5]"><BakeryNavbar /><div className="flex-1 flex items-center justify-center"><div className="w-12 h-12 border-4 border-[#4A3B32] border-t-transparent rounded-full animate-spin" /></div></div>);
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5]" data-testid="order-success-page">
      <BakeryNavbar />

      <main className="flex-1 py-16 md:py-24">
        <div className="max-w-3xl mx-auto px-6 md:px-12">
          {/* Thank You Hero */}
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.6 }} className="text-center mb-16">
            <div className="w-20 h-20 bg-[#A3B18A]/20 flex items-center justify-center mx-auto mb-6">
              <CheckCircle size={40} className="text-[#A3B18A]" strokeWidth={1.5} />
            </div>
            <h1 className="font-serif text-5xl md:text-6xl text-[#2C2420] italic mb-4">Thank You</h1>
            <p className="text-base text-[#786A60]">Your order has been placed successfully</p>
            {orderId && <p className="text-sm text-[#D4A373] mt-2 font-semibold tracking-wide">Order #{orderId}</p>}
          </motion.div>

          {order && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
              {/* Order Details */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
                <div className="bg-white border border-[#E8E0D5] p-6" data-testid="order-status-card">
                  <Package size={20} className="text-[#D4A373] mb-3" strokeWidth={1.5} />
                  <p className="text-xs tracking-[0.15em] uppercase text-[#786A60] font-semibold mb-1">Status</p>
                  <p className="font-serif text-lg text-[#2C2420] capitalize">{order.order_status}</p>
                </div>
                <div className="bg-white border border-[#E8E0D5] p-6" data-testid="payment-method-card">
                  <CreditCard size={20} className="text-[#D4A373] mb-3" strokeWidth={1.5} />
                  <p className="text-xs tracking-[0.15em] uppercase text-[#786A60] font-semibold mb-1">Payment</p>
                  <p className="font-serif text-lg text-[#2C2420] uppercase">{method || order.payment_method}</p>
                </div>
                <div className="bg-white border border-[#E8E0D5] p-6" data-testid="order-total-card">
                  <MapPin size={20} className="text-[#D4A373] mb-3" strokeWidth={1.5} />
                  <p className="text-xs tracking-[0.15em] uppercase text-[#786A60] font-semibold mb-1">Total</p>
                  <p className="font-serif text-lg text-[#2C2420]">₹{order.total?.toLocaleString()}</p>
                </div>
              </div>

              {/* Items */}
              <div className="bg-white border border-[#E8E0D5] mb-10" data-testid="order-items-section">
                <div className="p-6 border-b border-[#E8E0D5]"><h2 className="font-serif text-xl text-[#2C2420]">Order Items</h2></div>
                {order.items?.map((item, i) => (
                  <div key={i} className="px-6 py-4 border-b border-[#E8E0D5] last:border-0 flex justify-between items-center">
                    <div><p className="text-sm font-medium text-[#2C2420]">{item.product_name}</p><p className="text-xs text-[#786A60]">Qty: {item.quantity}</p></div>
                    <p className="text-sm font-medium text-[#2C2420]">₹{item.subtotal?.toLocaleString()}</p>
                  </div>
                ))}
              </div>

              {/* Delivery Info */}
              {order.delivery_info && (
                <div className="bg-white border border-[#E8E0D5] p-6 mb-10" data-testid="delivery-info-card">
                  <h2 className="font-serif text-xl text-[#2C2420] mb-4">Delivery Address</h2>
                  <p className="text-sm text-[#786A60]">{order.delivery_info.name}</p>
                  <p className="text-sm text-[#786A60]">{order.delivery_info.address}</p>
                  <p className="text-sm text-[#786A60]">{order.delivery_info.city}, {order.delivery_info.state} - {order.delivery_info.pincode}</p>
                  <p className="text-sm text-[#786A60]">{order.delivery_info.phone}</p>
                </div>
              )}
            </motion.div>
          )}

          {/* Actions */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link to="/my-orders" className="bg-[#4A3B32] text-white px-8 py-4 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#332822] transition-colors text-center" data-testid="view-orders-button">View My Orders</Link>
            <Link to="/business/whisked_words/catalog" className="bg-transparent border border-[#4A3B32] text-[#4A3B32] px-8 py-4 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#4A3B32] hover:text-white transition-colors text-center" data-testid="continue-shopping-button">Continue Shopping</Link>
          </div>
        </div>
      </main>

      <BakeryFooter />
    </div>
  );
};

export default OrderSuccessPage;
