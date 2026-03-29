import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import BakeryNavbar from '../components/common/BakeryNavbar';
import BakeryFooter from '../components/common/BakeryFooter';
import apiClient from '../utils/api';
import { toast } from 'sonner';
import { RefreshCw, Pause, Play, X, Plus, Package, Calendar, Clock } from 'lucide-react';

const SubscriptionsPage = () => {
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuth();
  const [subscriptions, setSubscriptions] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formData, setFormData] = useState({ product_ids: [], frequency: 'weekly', delivery_days: [], delivery_time: 'morning', start_date: '', name: user?.name || '', phone: '', email: user?.email || '', address: '', city: '', state: '', pincode: '' });

  const days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
  const frequencies = [{ value: 'daily', label: 'Daily' }, { value: 'weekly', label: 'Weekly' }, { value: 'monthly', label: 'Monthly' }];

  useEffect(() => {
    if (!isAuthenticated) { navigate('/login'); return; }
    const fetchData = async () => {
      try {
        const [subsRes, productsRes] = await Promise.all([apiClient.get('/subscriptions/my-subscriptions'), apiClient.get('/products?business_id=whisked_words')]);
        setSubscriptions(subsRes.data.subscriptions); setProducts(productsRes.data.products);
      } catch (error) { console.error('Error:', error); }
      finally { setLoading(false); }
    };
    fetchData();
  }, [isAuthenticated, navigate]);

  const handlePause = async (id) => { try { await apiClient.put(`/subscriptions/${id}/pause`); toast.success('Subscription paused'); setSubscriptions(s => s.map(x => x.subscription_id === id ? { ...x, status: 'paused' } : x)); } catch { toast.error('Failed'); } };
  const handleResume = async (id) => { try { await apiClient.put(`/subscriptions/${id}/resume`); toast.success('Subscription resumed'); setSubscriptions(s => s.map(x => x.subscription_id === id ? { ...x, status: 'active' } : x)); } catch { toast.error('Failed'); } };
  const handleCancel = async (id) => { if (!window.confirm('Cancel this subscription?')) return; try { await apiClient.delete(`/subscriptions/${id}`); toast.success('Subscription cancelled'); setSubscriptions(s => s.map(x => x.subscription_id === id ? { ...x, status: 'cancelled' } : x)); } catch { toast.error('Failed'); } };

  const toggleProduct = (pid) => setFormData(p => ({ ...p, product_ids: p.product_ids.includes(pid) ? p.product_ids.filter(id => id !== pid) : [...p.product_ids, pid] }));
  const toggleDay = (day) => setFormData(p => ({ ...p, delivery_days: p.delivery_days.includes(day) ? p.delivery_days.filter(d => d !== day) : [...p.delivery_days, day] }));

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!formData.product_ids.length) { toast.error('Select at least one product'); return; }
    if (!formData.delivery_days.length) { toast.error('Select delivery days'); return; }
    if (!formData.start_date || !formData.name || !formData.phone || !formData.address || !formData.city || !formData.state || !formData.pincode) { toast.error('Fill all required fields'); return; }
    setSubmitting(true);
    try {
      await apiClient.post('/subscriptions/create', { product_ids: formData.product_ids, frequency: formData.frequency, delivery_days: formData.delivery_days, delivery_time: formData.delivery_time, start_date: formData.start_date, delivery_info: { name: formData.name, phone: formData.phone, email: formData.email, address: formData.address, city: formData.city, state: formData.state, pincode: formData.pincode } });
      toast.success('Subscription created!'); setShowCreateForm(false);
      const subsRes = await apiClient.get('/subscriptions/my-subscriptions'); setSubscriptions(subsRes.data.subscriptions);
    } catch (error) { toast.error(error.response?.data?.detail || 'Failed'); }
    finally { setSubmitting(false); }
  };

  const statusStyles = { active: 'bg-[#A3B18A]/20 text-[#5A7247]', paused: 'bg-[#D4A373]/20 text-[#A67C52]', cancelled: 'bg-red-50 text-red-600' };

  if (loading) {
    return (<div className="min-h-screen flex flex-col bg-[#FAF8F5]"><BakeryNavbar /><div className="flex-1 flex items-center justify-center"><div className="w-12 h-12 border-4 border-[#4A3B32] border-t-transparent rounded-full animate-spin" /></div></div>);
  }

  const inputClass = "w-full border border-[#E8E0D5] px-4 py-3 focus:ring-1 focus:ring-[#4A3B32] focus:border-[#4A3B32] transition-all outline-none bg-white text-[#2C2420]";

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5]" data-testid="subscriptions-page">
      <BakeryNavbar />

      <main className="flex-1 py-16 md:py-24">
        <div className="max-w-4xl mx-auto px-6 md:px-12">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex items-end justify-between mb-12">
            <div>
              <p className="text-xs tracking-[0.2em] uppercase text-[#D4A373] font-semibold mb-2">Regular Deliveries</p>
              <h1 className="font-serif text-4xl md:text-5xl text-[#2C2420]">Subscriptions</h1>
            </div>
            {!showCreateForm && (
              <button onClick={() => setShowCreateForm(true)} className="bg-[#4A3B32] text-white px-8 py-4 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#332822] transition-colors duration-300 flex items-center gap-2" data-testid="new-subscription-button">
                <Plus size={16} /> New Subscription
              </button>
            )}
          </motion.div>

          {/* Create Form */}
          {showCreateForm && (
            <motion.form initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} onSubmit={handleCreate} className="bg-white border border-[#E8E0D5] mb-12" data-testid="create-subscription-form">
              <div className="p-8 border-b border-[#E8E0D5]">
                <h2 className="font-serif text-2xl text-[#2C2420]">New Subscription</h2>
              </div>
              <div className="p-8 space-y-8">
                {/* Products */}
                <div>
                  <label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-3">Select Products *</label>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {products.map((p) => (
                      <button key={p.product_id} type="button" onClick={() => toggleProduct(p.product_id)} className={`p-4 border text-left flex gap-3 items-center transition-all ${formData.product_ids.includes(p.product_id) ? 'border-[#D4A373] bg-[#D4A373]/5' : 'border-[#E8E0D5] hover:bg-[#FAF8F5]'}`} data-testid={`select-product-${p.product_id}`}>
                        <div className="w-12 h-12 bg-[#F3EFEA] flex-shrink-0 overflow-hidden">{p.images?.[0]?.url ? <img src={p.images[0].url} alt={p.product_name} className="w-full h-full object-cover" /> : <div className="w-full h-full flex items-center justify-center"><Package size={18} className="text-[#786A60]" /></div>}</div>
                        <div><p className="font-serif text-sm text-[#2C2420]">{p.product_name}</p><p className="text-xs text-[#786A60]">₹{p.base_price}</p></div>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Frequency *</label>
                    <select value={formData.frequency} onChange={(e) => setFormData(p => ({ ...p, frequency: e.target.value }))} className={inputClass} data-testid="subscription-frequency">
                      {frequencies.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Delivery Time *</label>
                    <select value={formData.delivery_time} onChange={(e) => setFormData(p => ({ ...p, delivery_time: e.target.value }))} className={inputClass} data-testid="subscription-delivery-time">
                      <option value="morning">Morning (9 AM – 12 PM)</option>
                      <option value="afternoon">Afternoon (12 – 4 PM)</option>
                      <option value="evening">Evening (4 – 8 PM)</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-3">Delivery Days *</label>
                  <div className="flex flex-wrap gap-2">
                    {days.map(day => (
                      <button key={day} type="button" onClick={() => toggleDay(day)} className={`px-5 py-2.5 text-xs tracking-[0.1em] uppercase font-semibold border transition-colors ${formData.delivery_days.includes(day) ? 'bg-[#4A3B32] text-white border-[#4A3B32]' : 'bg-white text-[#4A3B32] border-[#E8E0D5] hover:bg-[#FAF8F5]'}`} data-testid={`day-${day}`}>{day.slice(0, 3)}</button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Start Date *</label>
                  <input type="date" value={formData.start_date} onChange={(e) => setFormData(p => ({ ...p, start_date: e.target.value }))} min={new Date().toISOString().split('T')[0]} className={`${inputClass} max-w-xs`} data-testid="subscription-start-date" />
                </div>

                <div>
                  <h3 className="font-serif text-lg text-[#2C2420] mb-4">Delivery Address</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Name *</label><input type="text" value={formData.name} onChange={(e) => setFormData(p => ({ ...p, name: e.target.value }))} className={inputClass} data-testid="sub-input-name" /></div>
                    <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Phone *</label><input type="tel" value={formData.phone} onChange={(e) => setFormData(p => ({ ...p, phone: e.target.value }))} placeholder="+91-XXXXXXXXXX" className={inputClass} data-testid="sub-input-phone" /></div>
                    <div className="md:col-span-2"><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Email</label><input type="email" value={formData.email} onChange={(e) => setFormData(p => ({ ...p, email: e.target.value }))} className={inputClass} data-testid="sub-input-email" /></div>
                    <div className="md:col-span-2"><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Address *</label><textarea value={formData.address} onChange={(e) => setFormData(p => ({ ...p, address: e.target.value }))} rows="2" className={`${inputClass} resize-none`} data-testid="sub-input-address" /></div>
                    <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">City *</label><input type="text" value={formData.city} onChange={(e) => setFormData(p => ({ ...p, city: e.target.value }))} className={inputClass} data-testid="sub-input-city" /></div>
                    <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">State *</label><input type="text" value={formData.state} onChange={(e) => setFormData(p => ({ ...p, state: e.target.value }))} className={inputClass} data-testid="sub-input-state" /></div>
                    <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Pincode *</label><input type="text" value={formData.pincode} onChange={(e) => setFormData(p => ({ ...p, pincode: e.target.value }))} className={inputClass} data-testid="sub-input-pincode" /></div>
                  </div>
                </div>
              </div>
              <div className="p-8 border-t border-[#E8E0D5] flex gap-3">
                <button type="submit" disabled={submitting} className="bg-[#4A3B32] text-white px-8 py-4 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#332822] transition-colors disabled:opacity-50" data-testid="submit-subscription-button">{submitting ? 'Creating...' : 'Create Subscription'}</button>
                <button type="button" onClick={() => setShowCreateForm(false)} className="bg-transparent border border-[#E8E0D5] text-[#4A3B32] px-8 py-4 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#F3EFEA] transition-colors" data-testid="cancel-subscription-form">Cancel</button>
              </div>
            </motion.form>
          )}

          {/* Existing Subscriptions */}
          {subscriptions.length === 0 && !showCreateForm ? (
            <div className="bg-white border border-[#E8E0D5] p-16 text-center">
              <RefreshCw size={48} className="mx-auto text-[#786A60] mb-6" strokeWidth={1} />
              <h2 className="font-serif text-2xl text-[#2C2420] mb-3">No Subscriptions Yet</h2>
              <p className="text-sm text-[#786A60] mb-8">Subscribe for regular deliveries of your favorites</p>
              <button onClick={() => setShowCreateForm(true)} className="bg-[#4A3B32] text-white px-8 py-4 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#332822] transition-colors" data-testid="create-first-subscription">Create Your First Subscription</button>
            </div>
          ) : (
            <div className="space-y-4" data-testid="subscriptions-list">
              {subscriptions.map((sub) => (
                <motion.div key={sub.subscription_id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="bg-white border border-[#E8E0D5] p-6" data-testid={`subscription-${sub.subscription_id}`}>
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <div className="flex items-center gap-3 mb-1">
                        <RefreshCw size={16} className="text-[#D4A373]" />
                        <span className="font-serif text-base text-[#2C2420]">{sub.frequency} Subscription</span>
                      </div>
                      <p className="text-xs text-[#786A60]">ID: {sub.subscription_id}</p>
                    </div>
                    <span className={`text-xs px-3 py-1 font-semibold ${statusStyles[sub.status] || 'bg-gray-100 text-gray-800'}`} data-testid={`status-badge-${sub.status}`}>{sub.status.toUpperCase()}</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4 text-sm text-[#786A60]">
                    <div className="flex items-center gap-2"><Calendar size={14} />Started: {sub.start_date || 'N/A'}</div>
                    <div className="flex items-center gap-2"><Clock size={14} />{sub.delivery_time || 'N/A'}</div>
                    <div className="flex items-center gap-2"><Package size={14} />{sub.product_ids?.length || 0} product(s)</div>
                  </div>
                  {sub.delivery_days?.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-4">{sub.delivery_days.map(day => <span key={day} className="text-xs px-2 py-1 bg-[#F3EFEA] font-medium text-[#786A60]">{day.slice(0, 3).toUpperCase()}</span>)}</div>
                  )}
                  {sub.status !== 'cancelled' && (
                    <div className="flex gap-2 pt-4 border-t border-[#E8E0D5]">
                      {sub.status === 'active' ? (
                        <button onClick={() => handlePause(sub.subscription_id)} className="flex items-center gap-1 px-4 py-2 text-xs font-semibold tracking-wide border border-[#E8E0D5] text-[#4A3B32] hover:bg-[#F3EFEA] transition-colors" data-testid={`pause-sub-${sub.subscription_id}`}><Pause size={13} /> Pause</button>
                      ) : sub.status === 'paused' ? (
                        <button onClick={() => handleResume(sub.subscription_id)} className="flex items-center gap-1 px-4 py-2 text-xs font-semibold tracking-wide border border-[#D4A373] text-[#D4A373] hover:bg-[#D4A373]/10 transition-colors" data-testid={`resume-sub-${sub.subscription_id}`}><Play size={13} /> Resume</button>
                      ) : null}
                      <button onClick={() => handleCancel(sub.subscription_id)} className="flex items-center gap-1 px-4 py-2 text-xs font-semibold tracking-wide border border-red-200 text-red-500 hover:bg-red-50 transition-colors" data-testid={`cancel-sub-${sub.subscription_id}`}><X size={13} /> Cancel</button>
                    </div>
                  )}
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

export default SubscriptionsPage;
