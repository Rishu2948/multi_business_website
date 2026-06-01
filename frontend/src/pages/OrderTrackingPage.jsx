import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import BakeryNavbar from '../components/common/BakeryNavbar';
import BakeryFooter from '../components/common/BakeryFooter';
import apiClient from '../utils/api';
import { Package, CheckCircle, Circle, AlertCircle, Truck, ArrowLeft, Phone } from 'lucide-react';

const statusIcons = {
  pending: Package, confirmed: CheckCircle, preparing: Package,
  on_the_way: Truck, reached_doorstep: Truck, delivered: CheckCircle,
  cancelled: AlertCircle, not_delivered: AlertCircle
};

const OrderTrackingPage = () => {
  const { orderId } = useParams();
  const { isAuthenticated } = useAuth();
  const [trackingData, setTrackingData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTracking = async () => {
      try {
        const res = await apiClient.get(`/order-management/track/${orderId}`);
        setTrackingData(res.data);
      } catch (error) { console.error(error); }
      finally { setLoading(false); }
    };
    if (orderId) fetchTracking();
  }, [orderId]);

  if (loading) {
    return (<div className="min-h-screen flex flex-col bg-[#FAF8F5]"><BakeryNavbar /><div className="flex-1 flex items-center justify-center"><div className="w-12 h-12 border-4 border-[#4A3B32] border-t-transparent rounded-full animate-spin" /></div></div>);
  }

  if (!trackingData) {
    return (<div className="min-h-screen flex flex-col bg-[#FAF8F5]"><BakeryNavbar /><div className="flex-1 flex items-center justify-center"><p className="text-[#786A60]">Order not found</p></div></div>);
  }

  const { order, timeline, delivery_agent, current_status } = trackingData;
  const isFailed = ['cancelled', 'not_delivered'].includes(current_status);

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5]" data-testid="order-tracking-page">
      <BakeryNavbar />

      <main className="flex-1 py-16 md:py-24">
        <div className="max-w-3xl mx-auto px-6 md:px-12">
          <Link to="/my-orders" className="inline-flex items-center gap-2 text-xs tracking-[0.1em] uppercase text-[#D4A373] hover:text-[#4A3B32] font-semibold transition-colors mb-10" data-testid="back-to-orders"><ArrowLeft size={14} /> My Orders</Link>

          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <p className="text-xs tracking-[0.2em] uppercase text-[#D4A373] font-semibold mb-2">Order Tracking</p>
            <h1 className="font-serif text-3xl md:text-4xl text-[#2C2420] mb-2">#{orderId}</h1>
            <p className="text-sm text-[#786A60] mb-12">{new Date(order.created_at).toLocaleDateString('en-IN', { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</p>
          </motion.div>

          {/* Timeline */}
          <div className="bg-white border border-[#E8E0D5] p-8 mb-10" data-testid="tracking-timeline">
            <div className="relative">
              {timeline.map((step, i) => {
                const Icon = step.completed ? CheckCircle : (step.status === 'not_delivered' || step.status === 'cancelled') ? AlertCircle : Circle;
                const isLast = i === timeline.length - 1;
                const isCurrent = step.status === current_status;

                return (
                  <div key={step.status} className="flex gap-5 relative" data-testid={`timeline-step-${step.status}`}>
                    {/* Line */}
                    {!isLast && (
                      <div className={`absolute left-[15px] top-[32px] w-[2px] h-[calc(100%-16px)] ${step.completed ? 'bg-[#A3B18A]' : 'bg-[#E8E0D5]'}`} />
                    )}

                    {/* Dot */}
                    <div className="flex-shrink-0 z-10">
                      <motion.div
                        initial={isCurrent ? { scale: 0.8 } : {}}
                        animate={isCurrent ? { scale: [0.8, 1.1, 1] } : {}}
                        transition={{ duration: 0.5 }}
                      >
                        <Icon size={30} className={`${
                          step.completed
                            ? (step.status === 'not_delivered' || step.status === 'cancelled') ? 'text-red-500' : 'text-[#A3B18A]'
                            : 'text-[#E8E0D5]'
                        }`} strokeWidth={1.5} />
                      </motion.div>
                    </div>

                    {/* Content */}
                    <div className={`pb-8 ${isLast ? 'pb-0' : ''}`}>
                      <p className={`font-semibold text-sm ${step.completed ? 'text-[#2C2420]' : 'text-[#786A60]'}`}>{step.label}</p>
                      {step.timestamp && (
                        <p className="text-xs text-[#786A60] mt-0.5">
                          {new Date(step.timestamp).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                        </p>
                      )}
                      {step.reason && (
                        <p className="text-xs text-red-500 mt-1">Reason: {step.reason}{step.custom_reason ? ` - ${step.custom_reason}` : ''}</p>
                      )}
                      {isCurrent && step.completed && (
                        <span className="inline-block mt-1 text-[10px] tracking-[0.15em] uppercase font-semibold text-[#D4A373] bg-[#D4A373]/10 px-2 py-0.5">Current</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Delivery Agent */}
          {delivery_agent && (
            <div className="bg-white border border-[#E8E0D5] p-6 mb-10" data-testid="delivery-agent-info">
              <p className="text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-3">Delivery Partner</p>
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-[#FAF8F5] flex items-center justify-center"><Truck size={20} className="text-[#D4A373]" /></div>
                <div>
                  <p className="font-semibold text-[#2C2420]">{delivery_agent.name}</p>
                  {delivery_agent.phone && (
                    <a href={`tel:${delivery_agent.phone}`} className="text-sm text-[#D4A373] hover:text-[#4A3B32] flex items-center gap-1 transition-colors"><Phone size={12} />{delivery_agent.phone}</a>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Order Details */}
          <div className="bg-white border border-[#E8E0D5]" data-testid="order-details">
            <div className="p-6 border-b border-[#E8E0D5]"><h2 className="font-serif text-xl text-[#2C2420]">Order Details</h2></div>
            <div className="p-6">
              {order.items?.map((item, i) => (
                <div key={i} className="flex justify-between py-2 text-sm border-b border-[#E8E0D5] last:border-0">
                  <span className="text-[#2C2420]">{item.product_name} <span className="text-[#D4A373]">x{item.quantity}</span></span>
                  <span className="font-medium text-[#2C2420]">₹{item.subtotal?.toLocaleString()}</span>
                </div>
              ))}
              <div className="mt-4 pt-4 border-t border-[#E8E0D5] space-y-1 text-sm">
                <div className="flex justify-between"><span className="text-[#786A60]">Subtotal</span><span className="text-[#2C2420]">₹{order.subtotal?.toLocaleString()}</span></div>
                <div className="flex justify-between"><span className="text-[#786A60]">Tax</span><span className="text-[#2C2420]">₹{order.tax?.toLocaleString()}</span></div>
                <div className="flex justify-between"><span className="text-[#786A60]">Delivery</span><span className="text-[#2C2420]">₹{order.delivery_charge?.toLocaleString()}</span></div>
                <div className="flex justify-between pt-2 border-t border-[#E8E0D5]"><span className="font-serif text-lg text-[#2C2420]">Total</span><span className="font-serif text-lg text-[#2C2420]">₹{order.total?.toLocaleString()}</span></div>
              </div>
            </div>
          </div>
        </div>
      </main>

      <BakeryFooter />
    </div>
  );
};

export default OrderTrackingPage;
