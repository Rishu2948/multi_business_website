import { useEffect, useState, useCallback, useRef } from 'react';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import BakeryNavbar from '../components/common/BakeryNavbar';
import BakeryFooter from '../components/common/BakeryFooter';
import LiveTrackingMap from '../components/common/LiveTrackingMap';
import apiClient from '../utils/api';
import { toast } from 'sonner';
import { Package, Truck, MapPin, CheckCircle, XCircle, Navigation, Phone, Radio, ExternalLink } from 'lucide-react';

const statusLabels = {
  pending: 'Pending', confirmed: 'Confirmed', preparing: 'Preparing',
  on_the_way: 'On The Way', reached_doorstep: 'At Doorstep',
  delivered: 'Delivered', not_delivered: 'Not Delivered'
};

const NOT_DELIVERED_REASONS = [
  'Customer unavailable', 'Wrong address', 'Customer refused delivery',
  'Address not found', 'Weather/road conditions', 'Other'
];

const DeliveryDashboard = () => {
  const { user } = useAuth();
  const [orders, setOrders] = useState([]);
  const [filter, setFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [updatingOrder, setUpdatingOrder] = useState(null);
  const [notDeliveredData, setNotDeliveredData] = useState({ reason: '', custom_reason: '' });

  // GPS Sharing state
  const [sharingLocation, setSharingLocation] = useState(false);
  const [currentCoords, setCurrentCoords] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const gpsIntervalRef = useRef(null);
  const watchIdRef = useRef(null);
  const [expandedMap, setExpandedMap] = useState(null);

  const fetchOrders = useCallback(async () => {
    try {
      const res = await apiClient.get(`/order-management/delivery/my-orders${filter ? `?status=${filter}` : ''}`);
      setOrders(res.data.orders);
    } catch (error) { console.error(error); }
    finally { setLoading(false); }
  }, [filter]);

  useEffect(() => { fetchOrders(); }, [fetchOrders]);

  // GPS Location Sharing
  const startSharing = () => {
    if (!navigator.geolocation) { toast.error('Geolocation not supported by your browser'); return; }

    setSharingLocation(true);
    toast.success('Location sharing started');

    // Watch position continuously
    watchIdRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        setCurrentCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude });
      },
      (err) => {
        console.error('GPS error:', err);
        toast.error('Unable to access location. Please allow GPS permission.');
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 5000 }
    );

    // Send location updates every 10 seconds
    const sendUpdate = async () => {
      try {
        const pos = await new Promise((resolve, reject) =>
          navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 10000 })
        );
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        setCurrentCoords({ lat, lng });
        await apiClient.put('/locations/agent/update-location', { lat, lng });
        setLastUpdated(new Date());
      } catch (err) {
        console.error('Failed to send location update:', err);
      }
    };

    sendUpdate(); // Send immediately
    gpsIntervalRef.current = setInterval(sendUpdate, 10000);
  };

  const stopSharing = async () => {
    if (watchIdRef.current !== null) {
      navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }
    if (gpsIntervalRef.current) {
      clearInterval(gpsIntervalRef.current);
      gpsIntervalRef.current = null;
    }
    try {
      await apiClient.put('/locations/agent/stop-sharing');
    } catch {}
    setSharingLocation(false);
    setCurrentCoords(null);
    setLastUpdated(null);
    toast.info('Location sharing stopped');
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (watchIdRef.current !== null) navigator.geolocation.clearWatch(watchIdRef.current);
      if (gpsIntervalRef.current) clearInterval(gpsIntervalRef.current);
    };
  }, []);

  const updateStatus = async (orderId, status, extra = {}) => {
    try {
      await apiClient.put(`/order-management/delivery/orders/${orderId}/status`, { status, ...extra });
      toast.success(`Order marked as ${statusLabels[status]}`);
      setUpdatingOrder(null);
      setNotDeliveredData({ reason: '', custom_reason: '' });
      fetchOrders();
    } catch (error) { toast.error(error.response?.data?.detail || 'Failed'); }
  };

  const getNextAction = (status) => {
    switch (status) {
      case 'preparing': return { next: 'on_the_way', label: 'Picked Up', icon: Truck };
      case 'on_the_way': return { next: 'reached_doorstep', label: 'Reached Location', icon: MapPin };
      case 'reached_doorstep': return { next: 'delivered', label: 'Delivered', icon: CheckCircle };
      default: return null;
    }
  };

  const openNavigation = (deliveryInfo) => {
    if (deliveryInfo?.lat && deliveryInfo?.lng) {
      window.open(`https://www.google.com/maps/dir/?api=1&destination=${deliveryInfo.lat},${deliveryInfo.lng}`, '_blank');
    } else {
      const address = `${deliveryInfo?.address || ''}, ${deliveryInfo?.city || ''}, ${deliveryInfo?.pincode || ''}`;
      window.open(`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(address)}`, '_blank');
    }
  };

  if (loading) {
    return (<div className="min-h-screen flex flex-col bg-[#FAF8F5]"><BakeryNavbar /><div className="flex-1 flex items-center justify-center"><div className="w-12 h-12 border-4 border-[#4A3B32] border-t-transparent rounded-full animate-spin" /></div></div>);
  }

  const activeOrders = orders.filter(o => ['preparing', 'on_the_way', 'reached_doorstep'].includes(o.order_status));

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5]" data-testid="delivery-dashboard">
      <BakeryNavbar />

      <main className="flex-1 py-16 md:py-24">
        <div className="max-w-4xl mx-auto px-6 md:px-12">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <p className="text-xs tracking-[0.2em] uppercase text-[#D4A373] font-semibold mb-2">Delivery Dashboard</p>
            <h1 className="font-serif text-4xl text-[#2C2420] mb-2">My Deliveries</h1>
            <p className="text-sm text-[#786A60] mb-10">Welcome, {user?.name}</p>
          </motion.div>

          {/* GPS Location Sharing Control */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className={`mb-8 border p-6 transition-all duration-300 ${
              sharingLocation
                ? 'bg-gradient-to-r from-green-50 to-emerald-50 border-green-200'
                : 'bg-white border-[#E8E0D5]'
            }`}
            data-testid="gps-sharing-section"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className={`w-12 h-12 flex items-center justify-center transition-colors ${
                  sharingLocation ? 'bg-green-500' : 'bg-[#F3EFEA]'
                }`}>
                  {sharingLocation
                    ? <Radio size={20} className="text-white" />
                    : <Radio size={20} className="text-[#786A60] opacity-50" />
                  }
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <p className="font-semibold text-[#2C2420]">Live Location Sharing</p>
                    {sharingLocation && (
                      <span className="relative flex h-2.5 w-2.5">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500"></span>
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-[#786A60] mt-0.5">
                    {sharingLocation
                      ? `Sharing • ${currentCoords ? `${currentCoords.lat.toFixed(4)}, ${currentCoords.lng.toFixed(4)}` : 'Detecting...'}`
                      : `${activeOrders.length} active order${activeOrders.length !== 1 ? 's' : ''} — start sharing to enable customer tracking`
                    }
                  </p>
                  {lastUpdated && (
                    <p className="text-[10px] text-green-600 mt-0.5">
                      Last update: {lastUpdated.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </p>
                  )}
                </div>
              </div>
              <button
                onClick={sharingLocation ? stopSharing : startSharing}
                className={`px-6 py-3 text-xs tracking-[0.1em] uppercase font-semibold transition-colors flex items-center gap-2 ${
                  sharingLocation
                    ? 'bg-red-50 text-red-600 border border-red-200 hover:bg-red-100'
                    : 'bg-[#4A3B32] text-white hover:bg-[#332822]'
                }`}
                data-testid="gps-toggle-btn"
              >
                {sharingLocation ? <><Radio size={14} className="opacity-75" /> Stop Sharing</> : <><Radio size={14} /> Start Sharing</>}
              </button>
            </div>
          </motion.div>

          {/* Filters */}
          <div className="flex flex-wrap gap-2 mb-8">
            {['', 'preparing', 'on_the_way', 'reached_doorstep', 'delivered', 'not_delivered'].map(s => (
              <button key={s} onClick={() => setFilter(s)} className={`px-4 py-2 text-xs tracking-[0.1em] uppercase font-semibold border transition-colors ${filter === s ? 'bg-[#4A3B32] text-white border-[#4A3B32]' : 'bg-white text-[#4A3B32] border-[#E8E0D5] hover:bg-[#FAF8F5]'}`} data-testid={`delivery-filter-${s || 'all'}`}>
                {s ? statusLabels[s] : 'All'}
              </button>
            ))}
          </div>

          {/* Orders */}
          {orders.length === 0 ? (
            <div className="bg-white border border-[#E8E0D5] p-16 text-center">
              <Truck size={48} className="mx-auto text-[#786A60] mb-4" strokeWidth={1} />
              <p className="font-serif text-xl text-[#2C2420]">No deliveries assigned</p>
            </div>
          ) : (
            <div className="space-y-4" data-testid="delivery-orders-list">
              {orders.map(order => {
                const action = getNextAction(order.order_status);
                const isActive = ['preparing', 'on_the_way', 'reached_doorstep'].includes(order.order_status);
                const showMap = expandedMap === order.order_id;
                return (
                  <motion.div key={order.order_id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="bg-white border border-[#E8E0D5]" data-testid={`delivery-order-${order.order_id}`}>
                    <div className="p-6">
                      <div className="flex items-start justify-between mb-4">
                        <div>
                          <p className="font-serif text-base text-[#2C2420] mb-0.5">Order #{order.order_id}</p>
                          <p className="text-xs text-[#786A60]">{new Date(order.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</p>
                        </div>
                        <span className={`text-xs px-3 py-1 font-semibold ${
                          order.order_status === 'on_the_way' ? 'bg-indigo-50 text-indigo-600' :
                          order.order_status === 'reached_doorstep' ? 'bg-teal-50 text-teal-600' :
                          order.order_status === 'delivered' ? 'bg-[#A3B18A]/20 text-[#5A7247]' :
                          order.order_status === 'not_delivered' ? 'bg-red-50 text-red-600' :
                          'bg-violet-50 text-violet-600'
                        }`}>{statusLabels[order.order_status]}</span>
                      </div>

                      {/* Items */}
                      <div className="mb-4 pb-4 border-b border-[#E8E0D5]">
                        {order.items?.map((item, i) => (
                          <p key={i} className="text-sm text-[#2C2420]">{item.product_name} <span className="text-[#D4A373]">x{item.quantity}</span></p>
                        ))}
                        <p className="text-sm font-semibold text-[#2C2420] mt-2">Total: ₹{order.total?.toLocaleString()}</p>
                      </div>

                      {/* Delivery Address */}
                      {order.delivery_info && (
                        <div className="mb-4 flex items-start gap-3">
                          <MapPin size={16} className="text-[#D4A373] mt-0.5 flex-shrink-0" />
                          <div className="flex-1">
                            <p className="text-sm font-medium text-[#2C2420]">{order.delivery_info.name}</p>
                            <p className="text-sm text-[#786A60]">{order.delivery_info.address}, {order.delivery_info.city} - {order.delivery_info.pincode}</p>
                            {order.delivery_info.phone && (
                              <a href={`tel:${order.delivery_info.phone}`} className="text-sm text-[#D4A373] hover:text-[#4A3B32] flex items-center gap-1 mt-1 transition-colors"><Phone size={12} />{order.delivery_info.phone}</a>
                            )}
                            {order.delivery_info.lat && (
                              <p className="text-[10px] text-green-600 mt-1 flex items-center gap-1"><MapPin size={10} />GPS: {order.delivery_info.lat.toFixed(4)}, {order.delivery_info.lng.toFixed(4)}</p>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Navigate & Map Toggle Buttons */}
                      {isActive && order.delivery_info && (
                        <div className="flex flex-wrap gap-2 mb-4">
                          <button
                            onClick={() => openNavigation(order.delivery_info)}
                            className="px-4 py-2.5 text-xs tracking-[0.1em] uppercase font-semibold bg-[#D4A373] text-white hover:bg-[#c49363] transition-colors flex items-center gap-2"
                            data-testid={`navigate-btn-${order.order_id}`}
                          >
                            <Navigation size={14} /> Navigate
                            <ExternalLink size={11} />
                          </button>
                          <button
                            onClick={() => setExpandedMap(showMap ? null : order.order_id)}
                            className="px-4 py-2.5 text-xs tracking-[0.1em] uppercase font-semibold bg-[#FAF8F5] text-[#4A3B32] border border-[#E8E0D5] hover:bg-[#F3EFEA] transition-colors flex items-center gap-2"
                            data-testid={`toggle-map-btn-${order.order_id}`}
                          >
                            <MapPin size={14} /> {showMap ? 'Hide Map' : 'Show Map'}
                          </button>
                        </div>
                      )}

                      {/* Expandable Map */}
                      {showMap && order.delivery_info && (
                        <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="mb-4 overflow-hidden border border-[#E8E0D5]">
                          <LiveTrackingMap
                            agentLocation={currentCoords}
                            customerLocation={order.delivery_info?.lat && order.delivery_info?.lng ? { lat: order.delivery_info.lat, lng: order.delivery_info.lng } : null}
                            agentName="You"
                            etaMinutes={null}
                          />
                        </motion.div>
                      )}

                      {/* Actions */}
                      {!['delivered', 'not_delivered', 'cancelled'].includes(order.order_status) && (
                        <div className="flex flex-wrap gap-2 pt-4 border-t border-[#E8E0D5]">
                          {action && (
                            <button onClick={() => updateStatus(order.order_id, action.next)} className="px-5 py-3 text-xs tracking-[0.1em] uppercase font-semibold bg-[#4A3B32] text-white hover:bg-[#332822] transition-colors flex items-center gap-2" data-testid={`action-${action.next}-${order.order_id}`}>
                              <action.icon size={14} /> {action.label}
                            </button>
                          )}
                          {['on_the_way', 'reached_doorstep'].includes(order.order_status) && (
                            <button onClick={() => setUpdatingOrder(updatingOrder === order.order_id ? null : order.order_id)} className="px-5 py-3 text-xs tracking-[0.1em] uppercase font-semibold bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 transition-colors flex items-center gap-2" data-testid={`not-delivered-btn-${order.order_id}`}>
                              <XCircle size={14} /> Not Delivered
                            </button>
                          )}
                        </div>
                      )}

                      {/* Not Delivered Form */}
                      {updatingOrder === order.order_id && (
                        <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="mt-4 p-4 bg-red-50/50 border border-red-200" data-testid={`not-delivered-form-${order.order_id}`}>
                          <p className="text-xs tracking-[0.1em] uppercase text-red-600 font-semibold mb-3">Reason for Non-Delivery *</p>
                          <div className="grid grid-cols-2 gap-2 mb-3">
                            {NOT_DELIVERED_REASONS.map(r => (
                              <button key={r} onClick={() => setNotDeliveredData(p => ({ ...p, reason: r }))} className={`p-2 text-xs text-left border transition-colors ${notDeliveredData.reason === r ? 'bg-red-100 border-red-300 text-red-700' : 'bg-white border-[#E8E0D5] text-[#4A3B32] hover:bg-[#FAF8F5]'}`} data-testid={`reason-${r.replace(/\s/g, '-').toLowerCase()}`}>{r}</button>
                            ))}
                          </div>
                          {notDeliveredData.reason === 'Other' && (
                            <input type="text" value={notDeliveredData.custom_reason} onChange={(e) => setNotDeliveredData(p => ({ ...p, custom_reason: e.target.value }))} placeholder="Describe the reason..." className="w-full border border-[#E8E0D5] px-4 py-3 text-sm focus:ring-1 focus:ring-red-300 outline-none mb-3" data-testid="custom-reason-input" />
                          )}
                          <div className="flex gap-2">
                            <button onClick={() => { if (!notDeliveredData.reason) { toast.error('Select a reason'); return; } updateStatus(order.order_id, 'not_delivered', notDeliveredData); }} className="px-5 py-2.5 text-xs tracking-[0.1em] uppercase font-semibold bg-red-600 text-white hover:bg-red-700 transition-colors" data-testid={`confirm-not-delivered-${order.order_id}`}>Confirm</button>
                            <button onClick={() => { setUpdatingOrder(null); setNotDeliveredData({ reason: '', custom_reason: '' }); }} className="px-5 py-2.5 text-xs tracking-[0.1em] uppercase font-semibold text-[#786A60] hover:text-[#4A3B32]">Cancel</button>
                          </div>
                        </motion.div>
                      )}
                    </div>
                  </motion.div>
                );
              })}
            </div>
          )}
        </div>
      </main>

      <BakeryFooter />
    </div>
  );
};

export default DeliveryDashboard;
