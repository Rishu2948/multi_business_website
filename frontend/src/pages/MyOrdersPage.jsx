import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import apiClient from '../utils/api';
import { Package, Clock, CheckCircle, Truck, XCircle } from 'lucide-react';

const MyOrdersPage = () => {
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuth();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }

    const fetchOrders = async () => {
      try {
        const response = await apiClient.get('/orders/my-orders');
        setOrders(response.data.orders);
      } catch (error) {
        console.error('Error fetching orders:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchOrders();
  }, [isAuthenticated, navigate]);

  const getStatusIcon = (status) => {
    switch (status) {
      case 'pending':
        return <Clock size={20} className="text-yellow-600" />;
      case 'confirmed':
        return <CheckCircle size={20} className="text-green-600" />;
      case 'preparing':
        return <Package size={20} className="text-blue-600" />;
      case 'out_for_delivery':
        return <Truck size={20} className="text-purple-600" />;
      case 'delivered':
        return <CheckCircle size={20} className="text-green-600" />;
      case 'cancelled':
        return <XCircle size={20} className="text-red-600" />;
      default:
        return <Package size={20} className="text-muted" />;
    }
  };

  const getStatusText = (status) => {
    return status.replace('_', ' ').toUpperCase();
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'pending':
        return 'bg-yellow-100 text-yellow-800';
      case 'confirmed':
        return 'bg-green-100 text-green-800';
      case 'preparing':
        return 'bg-blue-100 text-blue-800';
      case 'out_for_delivery':
        return 'bg-purple-100 text-purple-800';
      case 'delivered':
        return 'bg-green-100 text-green-800';
      case 'cancelled':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-muted">Loading orders...</p>
        </div>
      </div>
    );
  }

  if (orders.length === 0) {
    return (
      <div className="min-h-screen flex flex-col bg-white">
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center max-w-md">
            <Package size={64} className="mx-auto text-muted mb-6" strokeWidth={1.5} />
            <h1 className="text-3xl font-black text-primary mb-4">NO ORDERS YET</h1>
            <p className="text-muted mb-8">You haven't placed any orders yet. Start shopping!</p>
            <button
              onClick={() => navigate('/business/whisked_words/catalog')}
              className="bg-primary text-white hover:bg-[#333333] transition-all border border-primary px-8 py-4 font-bold tracking-wide"
              data-testid="browse-products-button"
            >
              BROWSE PRODUCTS
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface py-12" data-testid="my-orders-page">
      <div className="max-w-7xl mx-auto px-8">
        <h1 className="text-4xl font-black text-primary uppercase mb-8">MY ORDERS</h1>

        <div className="space-y-6">
          {orders.map((order) => (
            <div key={order.order_id} className="bg-white border border-border" data-testid={`order-${order.order_id}`}>
              {/* Order Header */}
              <div className="p-6 border-b border-border">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <p className="text-xs text-muted mb-1">ORDER ID</p>
                    <p className="text-lg font-bold text-primary">{order.order_id}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted mb-1">DATE</p>
                    <p className="text-sm font-semibold text-primary">
                      {new Date(order.created_at).toLocaleDateString('en-IN', {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric'
                      })}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted mb-1">TOTAL</p>
                    <p className="text-lg font-bold text-primary">₹{order.total.toFixed(2)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted mb-1">STATUS</p>
                    <div className="flex items-center gap-2">
                      {getStatusIcon(order.order_status)}
                      <span className={`text-xs px-3 py-1 font-bold ${getStatusColor(order.order_status)}`}>
                        {getStatusText(order.order_status)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Order Items */}
              <div className="p-6">
                <div className="space-y-4">
                  {order.items.map((item, index) => (
                    <div key={index} className="flex gap-4">
                      <div className="w-16 h-16 bg-surface flex-shrink-0">
                        {item.image_url && (
                          <img src={item.image_url} alt={item.product_name} className="w-full h-full object-cover" />
                        )}
                      </div>
                      <div className="flex-1">
                        <h3 className="font-semibold text-primary">{item.product_name}</h3>
                        <p className="text-sm text-muted">Quantity: {item.quantity}</p>
                        <p className="text-sm font-semibold text-primary">₹{item.subtotal.toFixed(2)}</p>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Payment Info */}
                <div className="mt-6 pt-6 border-t border-border">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-muted">Payment Method</p>
                      <p className="font-semibold text-primary">
                        {order.payment_method === 'cod' ? 'Cash on Delivery' : order.payment_method.toUpperCase()}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-muted">Payment Status</p>
                      <span className={`text-xs px-3 py-1 font-bold ${
                        order.payment_status === 'paid' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
                      }`}>
                        {order.payment_status.toUpperCase()}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default MyOrdersPage;