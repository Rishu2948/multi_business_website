import { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import apiClient from '../utils/api';
import { CheckCircle, Package, Download } from 'lucide-react';

const OrderSuccessPage = () => {
  const [searchParams] = useSearchParams();
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [paymentStatus, setPaymentStatus] = useState('pending');

  const orderId = searchParams.get('order_id');
  const sessionId = searchParams.get('session_id');
  const paymentMethod = searchParams.get('payment_method');

  useEffect(() => {
    const fetchOrderDetails = async () => {
      try {
        if (sessionId && paymentMethod !== 'cod') {
          // Poll payment status for online payments
          const statusResponse = await apiClient.get(`/payments/checkout-status/${sessionId}`);
          setPaymentStatus(statusResponse.data.payment_status);
        }

        if (orderId) {
          const orderResponse = await apiClient.get(`/orders/${orderId}`);
          setOrder(orderResponse.data);
        }
      } catch (error) {
        console.error('Error fetching order:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchOrderDetails();

    // Poll payment status every 2 seconds for online payments
    let interval;
    if (sessionId && paymentMethod !== 'cod') {
      interval = setInterval(async () => {
        try {
          const statusResponse = await apiClient.get(`/payments/checkout-status/${sessionId}`);
          if (statusResponse.data.payment_status === 'paid') {
            setPaymentStatus('paid');
            clearInterval(interval);
          }
        } catch (error) {
          console.error('Error polling status:', error);
        }
      }, 2000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [orderId, sessionId, paymentMethod]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-muted">Processing your order...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface py-12" data-testid="order-success-page">
      <div className="max-w-3xl mx-auto px-8">
        {/* Success Message */}
        <div className="bg-white border border-border p-8 text-center mb-8">
          <CheckCircle size={64} className="mx-auto text-green-600 mb-6" strokeWidth={1.5} />
          <h1 className="text-4xl font-black text-primary uppercase mb-4">
            {paymentMethod === 'cod' ? 'ORDER PLACED!' : paymentStatus === 'paid' ? 'PAYMENT SUCCESSFUL!' : 'ORDER RECEIVED!'}
          </h1>
          <p className="text-base text-muted mb-6">
            {paymentMethod === 'cod' 
              ? 'Your order has been placed successfully. Pay cash on delivery.'
              : paymentStatus === 'paid'
              ? 'Thank you for your payment. Your order is confirmed!'
              : 'We are processing your payment. You will receive a confirmation email shortly.'}
          </p>
          {order && (
            <div className="inline-block bg-surface px-6 py-3">
              <p className="text-sm text-muted mb-1">Order ID</p>
              <p className="text-xl font-bold text-primary">{order.order_id}</p>
            </div>
          )}
        </div>

        {/* Order Details */}
        {order && (
          <div className="bg-white border border-border p-6 mb-8">
            <h2 className="text-xl font-bold text-primary mb-6">ORDER DETAILS</h2>
            
            {/* Items */}
            <div className="space-y-4 mb-6">
              {order.items.map((item) => (
                <div key={`${item.product_id}-${item.variant_id}`} className="flex gap-4 pb-4 border-b border-border last:border-0">
                  <div className="w-16 h-16 bg-surface flex-shrink-0">
                    {item.image_url && <img src={item.image_url} alt={item.product_name} className="w-full h-full object-cover" />}
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-primary">{item.product_name}</h3>
                    <p className="text-sm text-muted">Quantity: {item.quantity}</p>
                    <p className="text-sm font-semibold text-primary">₹{item.subtotal.toFixed(2)}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Totals */}
            <div className="space-y-2 pt-4 border-t border-border">
              <div className="flex justify-between text-sm">
                <span className="text-muted">Subtotal</span>
                <span className="font-semibold text-primary">₹{order.subtotal.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted">Tax</span>
                <span className="font-semibold text-primary">₹{order.tax.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted">Delivery</span>
                <span className="font-semibold text-primary">₹{order.delivery_charge.toFixed(2)}</span>
              </div>
              <div className="flex justify-between pt-2 border-t border-border">
                <span className="font-bold text-primary">Total</span>
                <span className="text-xl font-black text-primary">₹{order.total.toFixed(2)}</span>
              </div>
            </div>
          </div>
        )}

        {/* Delivery Information */}
        {order && order.delivery_info && (
          <div className="bg-white border border-border p-6 mb-8">
            <h2 className="text-xl font-bold text-primary mb-6">DELIVERY INFORMATION</h2>
            <div className="space-y-2 text-sm">
              <p><span className="font-semibold text-primary">Name:</span> {order.delivery_info.name}</p>
              <p><span className="font-semibold text-primary">Phone:</span> {order.delivery_info.phone}</p>
              <p><span className="font-semibold text-primary">Email:</span> {order.delivery_info.email}</p>
              <p><span className="font-semibold text-primary">Address:</span> {order.delivery_info.address}, {order.delivery_info.city}, {order.delivery_info.state} - {order.delivery_info.pincode}</p>
              {order.delivery_info.delivery_date && (
                <p><span className="font-semibold text-primary">Delivery Date:</span> {order.delivery_info.delivery_date}</p>
              )}
              {order.delivery_info.delivery_time && (
                <p><span className="font-semibold text-primary">Delivery Time:</span> {order.delivery_info.delivery_time}</p>
              )}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-wrap gap-4 justify-center">
          <Link
            to="/my-orders"
            className="inline-flex items-center gap-2 bg-primary text-white hover:bg-[#333333] transition-all border border-primary px-8 py-3 font-bold tracking-wide"
            data-testid="view-orders-button"
          >
            <Package size={20} />
            VIEW MY ORDERS
          </Link>
          <Link
            to="/business/whisked_words/catalog"
            className="inline-flex items-center gap-2 bg-transparent text-primary hover:bg-secondary transition-all border border-border px-8 py-3 font-bold tracking-wide"
            data-testid="continue-shopping-button"
          >
            CONTINUE SHOPPING
          </Link>
        </div>
      </div>
    </div>
  );
};

export default OrderSuccessPage;