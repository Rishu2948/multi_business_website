import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import BakeryNavbar from '../components/common/BakeryNavbar';
import BakeryFooter from '../components/common/BakeryFooter';
import apiClient from '../utils/api';
import { Package, ChevronRight } from 'lucide-react';

const statusStyles = {
  pending: 'bg-[#D4A373]/20 text-[#A67C52]',
  confirmed: 'bg-[#A3B18A]/20 text-[#5A7247]',
  processing: 'bg-blue-50 text-blue-600',
  shipped: 'bg-violet-50 text-violet-600',
  delivered: 'bg-[#A3B18A]/20 text-[#5A7247]',
  cancelled: 'bg-red-50 text-red-600'
};

const MyOrdersPage = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) { navigate('/login'); return; }
    const fetchOrders = async () => {
      try {
        const res = await apiClient.get('/orders/my-orders');
        setOrders(res.data.orders);
      } catch (error) { console.error('Error:', error); }
      finally { setLoading(false); }
    };
    fetchOrders();
  }, [isAuthenticated, navigate]);

  if (loading) {
    return (<div className="min-h-screen flex flex-col bg-[#FAF8F5]"><BakeryNavbar /><div className="flex-1 flex items-center justify-center"><div className="w-12 h-12 border-4 border-[#4A3B32] border-t-transparent rounded-full animate-spin" /></div></div>);
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5]" data-testid="my-orders-page">
      <BakeryNavbar />

      <main className="flex-1 py-16 md:py-24">
        <div className="max-w-4xl mx-auto px-6 md:px-12">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <p className="text-xs tracking-[0.2em] uppercase text-[#D4A373] font-semibold mb-2">Order History</p>
            <h1 className="font-serif text-4xl md:text-5xl text-[#2C2420] mb-12">My Orders</h1>
          </motion.div>

          {orders.length === 0 ? (
            <div className="bg-white border border-[#E8E0D5] p-16 text-center">
              <Package size={48} className="mx-auto text-[#786A60] mb-6" strokeWidth={1} />
              <h2 className="font-serif text-2xl text-[#2C2420] mb-3">No Orders Yet</h2>
              <p className="text-sm text-[#786A60] mb-8">Discover our collection and place your first order</p>
              <Link to="/business/whisked_words/catalog" className="bg-[#4A3B32] text-white px-8 py-4 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#332822] transition-colors inline-block">Browse Products</Link>
            </div>
          ) : (
            <div className="space-y-4" data-testid="orders-list">
              {orders.map((order, i) => (
                <motion.div
                  key={order.order_id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="bg-white border border-[#E8E0D5] hover:shadow-md transition-shadow"
                  data-testid={`order-${order.order_id}`}
                >
                  <div className="p-6">
                    <div className="flex items-start justify-between mb-4">
                      <div>
                        <p className="font-serif text-base text-[#2C2420] mb-0.5">Order #{order.order_id}</p>
                        <p className="text-xs text-[#786A60]">
                          {new Date(order.created_at).toLocaleDateString('en-IN', { year: 'numeric', month: 'long', day: 'numeric' })}
                        </p>
                      </div>
                      <span className={`text-xs px-3 py-1 font-semibold ${statusStyles[order.order_status] || 'bg-gray-100 text-gray-700'}`}>
                        {order.order_status?.toUpperCase()}
                      </span>
                    </div>

                    {/* Items */}
                    <div className="space-y-2 mb-4 pb-4 border-b border-[#E8E0D5]">
                      {order.items?.map((item, idx) => (
                        <div key={idx} className="flex justify-between text-sm">
                          <span className="text-[#786A60]">{item.product_name} <span className="text-[#D4A373]">x{item.quantity}</span></span>
                          <span className="text-[#2C2420] font-medium">₹{item.subtotal?.toLocaleString()}</span>
                        </div>
                      ))}
                    </div>

                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4 text-sm">
                        <span className="text-[#786A60]">Payment: <span className="font-medium text-[#2C2420] uppercase">{order.payment_method}</span></span>
                        <span className="text-[#786A60]">Total: <span className="font-serif font-medium text-[#2C2420]">₹{order.total?.toLocaleString()}</span></span>
                      </div>
                      <Link to={`/track/${order.order_id}`} className="text-xs text-[#D4A373] hover:text-[#4A3B32] font-semibold flex items-center gap-1 transition-colors">
                        Track <ChevronRight size={14} />
                      </Link>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </div>
      </main>

      <BakeryFooter />
    </div>
  );
};

export default MyOrdersPage;
