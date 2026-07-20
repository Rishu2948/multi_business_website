import { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import BakeryNavbar from '../components/common/BakeryNavbar';
import BakeryFooter from '../components/common/BakeryFooter';
import apiClient from '../utils/api';
import { toast } from 'sonner';
import { Package, TrendingUp, Clock, CheckCircle, Truck, User, ChevronDown, ChevronUp, UserPlus, Search } from 'lucide-react';

const statusColors = {
  pending: 'bg-[#D4A373]/20 text-[#A67C52]',
  confirmed: 'bg-blue-50 text-blue-600',
  preparing: 'bg-violet-50 text-violet-600',
  on_the_way: 'bg-indigo-50 text-indigo-600',
  reached_doorstep: 'bg-teal-50 text-teal-600',
  delivered: 'bg-[#A3B18A]/20 text-[#5A7247]',
  cancelled: 'bg-red-50 text-red-600',
  not_delivered: 'bg-red-50 text-red-600'
};

const statusLabels = {
  pending: 'Pending', confirmed: 'Confirmed', preparing: 'Preparing',
  on_the_way: 'On The Way', reached_doorstep: 'At Doorstep',
  delivered: 'Delivered', cancelled: 'Cancelled', not_delivered: 'Not Delivered'
};

const AdminOrdersDashboard = () => {
  const { user } = useAuth();
  const [orders, setOrders] = useState([]);
  const [customOrders, setCustomOrders] = useState([]);
  const [stats, setStats] = useState(null);
  const [agents, setAgents] = useState([]);
  const [filter, setFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [expandedOrder, setExpandedOrder] = useState(null);
  const [showAgentModal, setShowAgentModal] = useState(false);
  const [agentSearch, setAgentSearch] = useState('');
  const [assigningOrder, setAssigningOrder] = useState(null);
  const [newAgentEmail, setNewAgentEmail] = useState('');
  const [newAgentPhone, setNewAgentPhone] = useState('');
  const [newAgentPincode, setNewAgentPincode] = useState('');
  const [activeTab, setActiveTab] = useState('regular');
  const [quotePrice, setQuotePrice] = useState('');
  const [quoteNotes, setQuoteNotes] = useState('');
  const [quotingOrder, setQuotingOrder] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const [ordersRes, statsRes, agentsRes, customRes] = await Promise.all([
        apiClient.get(`/order-management/orders${filter ? `?status=${filter}` : ''}`),
        apiClient.get('/order-management/orders/stats'),
        apiClient.get('/order-management/delivery-agents'),
        apiClient.get('/custom-orders/admin/all').catch(e => ({ data: { orders: [] } }))
      ]);
      setOrders(ordersRes.data.orders);
      setStats(statsRes.data);
      setAgents(agentsRes.data.agents);
      setCustomOrders(customRes.data.orders || []);
    } catch (error) { console.error(error); }
    finally { setLoading(false); }
  }, [filter]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const updateStatus = async (orderId, status) => {
    try {
      await apiClient.put(`/order-management/orders/${orderId}/status`, { status });
      toast.success(`Order ${status}`);
      fetchData();
    } catch (error) { toast.error(error.response?.data?.detail || 'Failed'); }
  };

  const assignAgent = async (orderId, agentId) => {
    try {
      await apiClient.put(`/order-management/orders/${orderId}/assign`, { delivery_agent_id: agentId });
      toast.success('Delivery agent assigned');
      setAssigningOrder(null);
      fetchData();
    } catch (error) { toast.error(error.response?.data?.detail || 'Failed'); }
  };

  const makeDeliveryAgent = async () => {
    if (!newAgentEmail) { toast.error('Email required'); return; }
    try {
      // Find user by email
      const users = await apiClient.get(`/users/search?email=${encodeURIComponent(newAgentEmail)}`);
      if (!users.data.users?.length) { toast.error('User not found. They must sign in first.'); return; }
      const userId = users.data.users[0].user_id;
      await apiClient.put(`/order-management/users/${userId}/make-delivery-agent`, { phone: newAgentPhone, base_pincode: newAgentPincode });
      toast.success('User promoted to delivery agent');
      setNewAgentEmail(''); setNewAgentPhone(''); setNewAgentPincode(''); setShowAgentModal(false);
      fetchData();
    } catch (error) { toast.error(error.response?.data?.detail || 'Failed to assign role'); }
  };

  const updateCustomOrderStatus = async (orderId, status, price = null, notes = null) => {
    try {
      await apiClient.put(`/custom-orders/${orderId}/status`, { status, price, admin_notes: notes });
      toast.success(`Custom order ${status}`);
      setQuotingOrder(null);
      setQuotePrice('');
      setQuoteNotes('');
      fetchData();
    } catch (error) { toast.error(error.response?.data?.detail || 'Failed'); }
  };

  const submitQuote = async () => {
    if (!quotePrice || isNaN(quotePrice)) { toast.error('Valid price required'); return; }
    await updateCustomOrderStatus(quotingOrder, 'quoted', parseFloat(quotePrice), quoteNotes);
  };

  const inputClass = "w-full border border-[#E8E0D5] px-4 py-3 focus:ring-1 focus:ring-[#4A3B32] focus:border-[#4A3B32] transition-all outline-none bg-white text-[#2C2420]";

  if (loading) {
    return (<div className="min-h-screen flex flex-col bg-[#FAF8F5]"><BakeryNavbar /><div className="flex-1 flex items-center justify-center"><div className="w-12 h-12 border-4 border-[#4A3B32] border-t-transparent rounded-full animate-spin" /></div></div>);
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5]" data-testid="admin-orders-dashboard">
      <BakeryNavbar />

      <main className="flex-1 py-16 md:py-24">
        <div className="max-w-7xl mx-auto px-6 md:px-12">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <p className="text-xs tracking-[0.2em] uppercase text-[#D4A373] font-semibold mb-2">Admin Dashboard</p>
            <h1 className="font-serif text-4xl md:text-5xl text-[#2C2420] mb-12">Order Management</h1>
          </motion.div>

          {/* Stats */}
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10" data-testid="order-stats">
              <div className="bg-white border border-[#E8E0D5] p-6">
                <Package size={20} className="text-[#D4A373] mb-3" strokeWidth={1.5} />
                <p className="font-serif text-3xl text-[#2C2420]">{stats.total_orders}</p>
                <p className="text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mt-1">Total Orders</p>
              </div>
              <div className="bg-white border border-[#E8E0D5] p-6">
                <TrendingUp size={20} className="text-[#A3B18A] mb-3" strokeWidth={1.5} />
                <p className="font-serif text-3xl text-[#2C2420]">₹{stats.total_revenue?.toLocaleString()}</p>
                <p className="text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mt-1">Revenue</p>
              </div>
              <div className="bg-white border border-[#E8E0D5] p-6">
                <Clock size={20} className="text-[#D4A373] mb-3" strokeWidth={1.5} />
                <p className="font-serif text-3xl text-[#2C2420]">{stats.by_status?.pending?.count || 0}</p>
                <p className="text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mt-1">Pending</p>
              </div>
              <div className="bg-white border border-[#E8E0D5] p-6">
                <CheckCircle size={20} className="text-[#A3B18A] mb-3" strokeWidth={1.5} />
                <p className="font-serif text-3xl text-[#2C2420]">{stats.by_status?.delivered?.count || 0}</p>
                <p className="text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mt-1">Delivered</p>
              </div>
            </div>
          )}

          {/* Tabs */}
          <div className="flex gap-4 mb-8 border-b border-[#E8E0D5]">
            <button onClick={() => setActiveTab('regular')} className={`pb-4 px-2 text-xs tracking-[0.1em] uppercase font-semibold transition-colors ${activeTab === 'regular' ? 'text-[#4A3B32] border-b-2 border-[#4A3B32]' : 'text-[#786A60] hover:text-[#4A3B32]'}`}>Regular Orders</button>
            <button onClick={() => setActiveTab('custom')} className={`pb-4 px-2 text-xs tracking-[0.1em] uppercase font-semibold transition-colors ${activeTab === 'custom' ? 'text-[#4A3B32] border-b-2 border-[#4A3B32]' : 'text-[#786A60] hover:text-[#4A3B32]'}`}>Custom Orders ({customOrders.length})</button>
          </div>

          {/* Filters + Agent Button (Regular Orders) */}
          {activeTab === 'regular' && (
            <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
              <div className="flex flex-wrap gap-2">
                {['', 'pending', 'confirmed', 'preparing', 'on_the_way', 'delivered', 'cancelled'].map((s) => (
                  <button key={s} onClick={() => setFilter(s)} className={`px-4 py-2 text-xs tracking-[0.1em] uppercase font-semibold border transition-colors ${filter === s ? 'bg-[#4A3B32] text-white border-[#4A3B32]' : 'bg-white text-[#4A3B32] border-[#E8E0D5] hover:bg-[#FAF8F5]'}`} data-testid={`filter-${s || 'all'}`}>
                    {s ? statusLabels[s] : 'All'}
                  </button>
                ))}
              </div>
              <button onClick={() => setShowAgentModal(true)} className="bg-[#4A3B32] text-white px-6 py-3 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#332822] transition-colors flex items-center gap-2" data-testid="add-delivery-agent-btn">
                <UserPlus size={16} /> Add Delivery Agent
              </button>
            </div>
          )}

          {/* Delivery Agents Bar */}
          {agents.length > 0 && (
            <div className="bg-white border border-[#E8E0D5] p-4 mb-8" data-testid="delivery-agents-bar">
              <p className="text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-3">Delivery Agents ({agents.length})</p>
              <div className="flex flex-wrap gap-3">
                {agents.map(a => (
                  <div key={a.user_id} className="flex items-center gap-2 px-3 py-2 bg-[#FAF8F5] text-sm" data-testid={`agent-card-${a.user_id}`}>
                    <Truck size={14} className="text-[#D4A373]" />
                    <span className="font-medium text-[#2C2420]">{a.name}</span>
                    {a.phone && <span className="text-xs text-[#786A60]">{a.phone}</span>}
                    {a.base_pincode && <span className="text-xs text-[#D4A373]">PIN: {a.base_pincode}</span>}
                    <span className="text-xs text-[#786A60]">{a.active_orders || 0} active</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Orders */}
          {activeTab === 'regular' ? (
            <div className="space-y-3" data-testid="orders-list">
              {orders.length === 0 ? (
                <div className="bg-white border border-[#E8E0D5] p-16 text-center">
                  <Package size={48} className="mx-auto text-[#786A60] mb-4" strokeWidth={1} />
                  <p className="font-serif text-xl text-[#2C2420]">No orders found</p>
                </div>
              ) : orders.map((order) => (
              <motion.div key={order.order_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="bg-white border border-[#E8E0D5]" data-testid={`admin-order-${order.order_id}`}>
                {/* Header */}
                <button onClick={() => setExpandedOrder(expandedOrder === order.order_id ? null : order.order_id)} className="w-full p-5 flex items-center justify-between text-left hover:bg-[#FAF8F5]/50 transition-colors" data-testid={`toggle-order-${order.order_id}`}>
                  <div className="flex items-center gap-4">
                    <span className={`text-xs px-3 py-1 font-semibold ${statusColors[order.order_status]}`}>{statusLabels[order.order_status]}</span>
                    <span className="font-serif text-sm text-[#2C2420]">#{order.order_id}</span>
                    <span className="text-xs text-[#786A60]">{new Date(order.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="font-serif text-sm text-[#2C2420]">₹{order.total?.toLocaleString()}</span>
                    {order.delivery_agent && <span className="text-xs text-[#D4A373] flex items-center gap-1"><Truck size={12} />{order.delivery_agent.name}</span>}
                    {expandedOrder === order.order_id ? <ChevronUp size={16} className="text-[#786A60]" /> : <ChevronDown size={16} className="text-[#786A60]" />}
                  </div>
                </button>

                {/* Expanded Details */}
                <AnimatePresence>
                  {expandedOrder === order.order_id && (
                    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                      <div className="px-5 pb-5 border-t border-[#E8E0D5]">
                        {/* Items */}
                        <div className="py-4">
                          <p className="text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Items</p>
                          {order.items?.map((item, i) => (
                            <div key={i} className="flex justify-between py-1 text-sm">
                              <span className="text-[#2C2420]">{item.product_name} <span className="text-[#D4A373]">x{item.quantity}</span></span>
                              <span className="text-[#2C2420] font-medium">₹{item.subtotal?.toLocaleString()}</span>
                            </div>
                          ))}
                        </div>

                        {/* Delivery Info */}
                        {order.delivery_info && (
                          <div className="py-4 border-t border-[#E8E0D5]">
                            <p className="text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Delivery</p>
                            <p className="text-sm text-[#2C2420]">{order.delivery_info.name} &bull; {order.delivery_info.phone}</p>
                            <p className="text-sm text-[#786A60]">{order.delivery_info.address}, {order.delivery_info.city}</p>
                          </div>
                        )}

                        {/* Actions */}
                        <div className="flex flex-wrap gap-2 pt-4 border-t border-[#E8E0D5]">
                          {order.order_status === 'pending' && (
                            <button onClick={() => updateStatus(order.order_id, 'confirmed')} className="px-5 py-2.5 text-xs tracking-[0.1em] uppercase font-semibold bg-blue-50 text-blue-600 border border-blue-200 hover:bg-blue-100 transition-colors" data-testid={`confirm-order-${order.order_id}`}>Confirm</button>
                          )}
                          {order.order_status === 'confirmed' && (
                            <button onClick={() => updateStatus(order.order_id, 'preparing')} className="px-5 py-2.5 text-xs tracking-[0.1em] uppercase font-semibold bg-violet-50 text-violet-600 border border-violet-200 hover:bg-violet-100 transition-colors" data-testid={`preparing-order-${order.order_id}`}>Mark Preparing</button>
                          )}
                          {['pending', 'confirmed', 'preparing'].includes(order.order_status) && (
                            <button onClick={() => updateStatus(order.order_id, 'cancelled')} className="px-5 py-2.5 text-xs tracking-[0.1em] uppercase font-semibold bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 transition-colors" data-testid={`cancel-order-${order.order_id}`}>Cancel</button>
                          )}
                          {['confirmed', 'preparing'].includes(order.order_status) && !order.delivery_agent_id && (
                            <button onClick={() => setAssigningOrder(order.order_id)} className="px-5 py-2.5 text-xs tracking-[0.1em] uppercase font-semibold bg-[#4A3B32] text-white hover:bg-[#332822] transition-colors flex items-center gap-1" data-testid={`assign-agent-${order.order_id}`}><Truck size={13} /> Assign Agent</button>
                          )}
                          {order.delivery_agent_id && (
                            <span className="px-5 py-2.5 text-xs tracking-[0.1em] uppercase font-semibold bg-[#FAF8F5] text-[#786A60] flex items-center gap-1"><User size={13} /> {order.delivery_agent?.name || 'Assigned'}</span>
                          )}
                        </div>

                        {/* Assign Agent Inline */}
                        {assigningOrder === order.order_id && (
                          <div className="mt-4 p-4 bg-[#FAF8F5] border border-[#E8E0D5]" data-testid={`assign-panel-${order.order_id}`}>
                            <p className="text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-3">Select Delivery Agent</p>
                            {agents.length === 0 ? (
                              <p className="text-sm text-[#786A60]">No delivery agents yet. Add one first.</p>
                            ) : (
                              <div className="space-y-2">
                                {agents.map(a => (
                                  <button key={a.user_id} onClick={() => assignAgent(order.order_id, a.user_id)} className="w-full p-3 bg-white border border-[#E8E0D5] hover:border-[#D4A373] transition-colors text-left flex items-center gap-3" data-testid={`select-agent-${a.user_id}`}>
                                    <Truck size={16} className="text-[#D4A373]" />
                                    <div><p className="text-sm font-medium text-[#2C2420]">{a.name}</p>{a.phone && <p className="text-xs text-[#786A60]">{a.phone}</p>}</div>
                                  </button>
                                ))}
                              </div>
                            )}
                            <button onClick={() => setAssigningOrder(null)} className="mt-3 text-xs text-[#D4A373] hover:text-[#4A3B32] font-semibold">Cancel</button>
                          </div>
                        )}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            ))}
            </div>
          ) : (
            /* Custom Orders */
            <div className="space-y-3" data-testid="custom-orders-list">
              {customOrders.length === 0 ? (
                <div className="bg-white border border-[#E8E0D5] p-16 text-center">
                  <Package size={48} className="mx-auto text-[#786A60] mb-4" strokeWidth={1} />
                  <p className="font-serif text-xl text-[#2C2420]">No custom orders found</p>
                </div>
              ) : customOrders.map((order) => (
                <motion.div key={order.custom_order_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="bg-white border border-[#E8E0D5]" data-testid={`admin-custom-order-${order.custom_order_id}`}>
                  {/* Header */}
                  <button onClick={() => setExpandedOrder(expandedOrder === order.custom_order_id ? null : order.custom_order_id)} className="w-full p-5 flex items-center justify-between text-left hover:bg-[#FAF8F5]/50 transition-colors" data-testid={`toggle-custom-order-${order.custom_order_id}`}>
                    <div className="flex items-center gap-4">
                      <span className={`text-xs px-3 py-1 font-semibold ${order.status === 'pending_quote' ? 'bg-[#D4A373]/20 text-[#A67C52]' : order.status === 'quoted' ? 'bg-blue-50 text-blue-600' : order.status === 'confirmed' ? 'bg-[#A3B18A]/20 text-[#5A7247]' : 'bg-red-50 text-red-600'}`}>
                        {order.status === 'pending_quote' ? 'Quote Pending' : order.status === 'quoted' ? 'Quoted' : order.status === 'confirmed' ? 'Confirmed' : 'Rejected'}
                      </span>
                      <span className="font-serif text-sm text-[#2C2420]">#{order.custom_order_id}</span>
                      <span className="text-xs text-[#786A60]">{new Date(order.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="font-serif text-sm text-[#2C2420]">₹{order.price?.toLocaleString()}</span>
                      {expandedOrder === order.custom_order_id ? <ChevronUp size={16} className="text-[#786A60]" /> : <ChevronDown size={16} className="text-[#786A60]" />}
                    </div>
                  </button>

                  {/* Expanded Details */}
                  <AnimatePresence>
                    {expandedOrder === order.custom_order_id && (
                      <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                        <div className="px-5 pb-5 border-t border-[#E8E0D5]">
                          {/* Cake Details */}
                          <div className="py-4">
                            <p className="text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Cake Details</p>
                            <div className="grid grid-cols-2 gap-2 text-sm">
                              <span className="text-[#786A60]">Type: <span className="text-[#2C2420]">{order.cake_type}</span></span>
                              <span className="text-[#786A60]">Flavor: <span className="text-[#2C2420]">{order.flavor}</span></span>
                              <span className="text-[#786A60]">Weight: <span className="text-[#2C2420]">{order.weight}</span></span>
                              <span className="text-[#786A60]">Shape: <span className="text-[#2C2420]">{order.shape}</span></span>
                            </div>
                            {order.message_on_cake && <p className="text-sm text-[#2C2420] mt-2">Message: {order.message_on_cake}</p>}
                            {order.special_instructions && <p className="text-sm text-[#786A60] mt-1">Notes: {order.special_instructions}</p>}
                          </div>

                          {/* Delivery Info */}
                          {order.delivery_info && (
                            <div className="py-4 border-t border-[#E8E0D5]">
                              <p className="text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Delivery</p>
                              <p className="text-sm text-[#2C2420]">{order.delivery_info.name} &bull; {order.delivery_info.phone}</p>
                              <p className="text-sm text-[#786A60]">{order.delivery_info.address}, {order.delivery_info.city}</p>
                              <p className="text-sm text-[#786A60]">{order.delivery_date} at {order.delivery_time}</p>
                            </div>
                          )}

                          {/* Actions */}
                          <div className="flex flex-wrap gap-2 pt-4 border-t border-[#E8E0D5]">
                            {order.status === 'pending_quote' && (
                              <button onClick={() => setQuotingOrder(order.custom_order_id)} className="px-5 py-2.5 text-xs tracking-[0.1em] uppercase font-semibold bg-[#4A3B32] text-white hover:bg-[#332822] transition-colors">Provide Quote</button>
                            )}
                            {order.status === 'quoted' && (
                              <>
                                <button onClick={() => updateCustomOrderStatus(order.custom_order_id, 'confirmed')} className="px-5 py-2.5 text-xs tracking-[0.1em] uppercase font-semibold bg-[#A3B18A] text-white border border-[#A3B18A] hover:bg-[#5A7247] transition-colors">Confirm Order</button>
                                <button onClick={() => updateCustomOrderStatus(order.custom_order_id, 'rejected')} className="px-5 py-2.5 text-xs tracking-[0.1em] uppercase font-semibold bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 transition-colors">Reject</button>
                              </>
                            )}
                            {['pending_quote', 'quoted'].includes(order.status) && (
                              <button onClick={() => updateCustomOrderStatus(order.custom_order_id, 'rejected')} className="px-5 py-2.5 text-xs tracking-[0.1em] uppercase font-semibold bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 transition-colors">Reject</button>
                            )}
                          </div>

                          {/* Quote Form */}
                          {quotingOrder === order.custom_order_id && (
                            <div className="mt-4 p-4 bg-[#FAF8F5] border border-[#E8E0D5]" data-testid={`quote-panel-${order.custom_order_id}`}>
                              <p className="text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-3">Provide Quote</p>
                              <div className="space-y-3">
                                <div><label className="block text-xs text-[#786A60] mb-1">Price (₹)</label><input type="number" value={quotePrice} onChange={(e) => setQuotePrice(e.target.value)} placeholder="Enter price" className={inputClass} /></div>
                                <div><label className="block text-xs text-[#786A60] mb-1">Notes (optional)</label><textarea value={quoteNotes} onChange={(e) => setQuoteNotes(e.target.value)} rows="2" placeholder="Any additional notes..." className={`${inputClass} resize-none`} /></div>
                              </div>
                              <div className="flex gap-2 mt-3">
                                <button onClick={submitQuote} className="bg-[#4A3B32] text-white px-4 py-2 text-xs tracking-[0.1em] uppercase font-semibold hover:bg-[#332822] transition-colors">Submit Quote</button>
                                <button onClick={() => { setQuotingOrder(null); setQuotePrice(''); setQuoteNotes(''); }} className="text-xs text-[#D4A373] hover:text-[#4A3B32] font-semibold">Cancel</button>
                              </div>
                            </div>
                          )}

                          {/* Admin Notes */}
                          {order.admin_notes && (
                            <div className="mt-4 p-3 bg-[#FAF8F5] border border-[#E8E0D5]">
                              <p className="text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-1">Admin Notes</p>
                              <p className="text-sm text-[#2C2420]">{order.admin_notes}</p>
                            </div>
                          )}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              ))}
            </div>
          )}
        </div>
      </main>

      {/* Add Delivery Agent Modal */}
      <AnimatePresence>
        {showAgentModal && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 bg-black/30 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={() => setShowAgentModal(false)}>
            <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }} className="bg-white border border-[#E8E0D5] max-w-md w-full" onClick={(e) => e.stopPropagation()} data-testid="add-agent-modal">
              <div className="p-6 border-b border-[#E8E0D5]">
                <h2 className="font-serif text-xl text-[#2C2420]">Add Delivery Agent</h2>
                <p className="text-xs text-[#786A60] mt-1">User must have signed in via Google OAuth first</p>
              </div>
              <div className="p-6 space-y-4">
                <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">User Email *</label><input type="email" value={newAgentEmail} onChange={(e) => setNewAgentEmail(e.target.value)} placeholder="agent@gmail.com" className={inputClass} data-testid="agent-email-input" /></div>
                <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Phone Number</label><input type="tel" value={newAgentPhone} onChange={(e) => setNewAgentPhone(e.target.value)} placeholder="+91-XXXXXXXXXX" className={inputClass} data-testid="agent-phone-input" /></div>
                <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Base Pincode (for auto-assignment)</label><input type="text" value={newAgentPincode} onChange={(e) => setNewAgentPincode(e.target.value)} placeholder="400001" maxLength={6} className={inputClass} data-testid="agent-pincode-input" /></div>
              </div>
              <div className="p-6 border-t border-[#E8E0D5] flex gap-3">
                <button onClick={makeDeliveryAgent} className="bg-[#4A3B32] text-white px-6 py-3 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#332822] transition-colors" data-testid="confirm-add-agent">Add Agent</button>
                <button onClick={() => setShowAgentModal(false)} className="bg-transparent border border-[#E8E0D5] text-[#4A3B32] px-6 py-3 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#F3EFEA] transition-colors">Cancel</button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <BakeryFooter />
    </div>
  );
};

export default AdminOrdersDashboard;
