import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Navbar from '../components/common/Navbar';
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

  const [formData, setFormData] = useState({
    product_ids: [],
    frequency: 'weekly',
    delivery_days: [],
    delivery_time: 'morning',
    start_date: '',
    name: user?.name || '',
    phone: '',
    email: user?.email || '',
    address: '',
    city: '',
    state: '',
    pincode: ''
  });

  const days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
  const frequencies = [
    { value: 'daily', label: 'Daily' },
    { value: 'weekly', label: 'Weekly' },
    { value: 'monthly', label: 'Monthly' }
  ];

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }

    const fetchData = async () => {
      try {
        const [subsRes, productsRes] = await Promise.all([
          apiClient.get('/subscriptions/my-subscriptions'),
          apiClient.get('/products?business_id=whisked_words')
        ]);
        setSubscriptions(subsRes.data.subscriptions);
        setProducts(productsRes.data.products);
      } catch (error) {
        console.error('Error fetching data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [isAuthenticated, navigate]);

  const handlePause = async (subscriptionId) => {
    try {
      await apiClient.put(`/subscriptions/${subscriptionId}/pause`);
      toast.success('Subscription paused');
      setSubscriptions(subs =>
        subs.map(s => s.subscription_id === subscriptionId ? { ...s, status: 'paused' } : s)
      );
    } catch (error) {
      toast.error('Failed to pause subscription');
    }
  };

  const handleResume = async (subscriptionId) => {
    try {
      await apiClient.put(`/subscriptions/${subscriptionId}/resume`);
      toast.success('Subscription resumed');
      setSubscriptions(subs =>
        subs.map(s => s.subscription_id === subscriptionId ? { ...s, status: 'active' } : s)
      );
    } catch (error) {
      toast.error('Failed to resume subscription');
    }
  };

  const handleCancel = async (subscriptionId) => {
    if (!window.confirm('Are you sure you want to cancel this subscription?')) return;
    try {
      await apiClient.delete(`/subscriptions/${subscriptionId}`);
      toast.success('Subscription cancelled');
      setSubscriptions(subs =>
        subs.map(s => s.subscription_id === subscriptionId ? { ...s, status: 'cancelled' } : s)
      );
    } catch (error) {
      toast.error('Failed to cancel subscription');
    }
  };

  const toggleProduct = (productId) => {
    setFormData(prev => ({
      ...prev,
      product_ids: prev.product_ids.includes(productId)
        ? prev.product_ids.filter(id => id !== productId)
        : [...prev.product_ids, productId]
    }));
  };

  const toggleDay = (day) => {
    setFormData(prev => ({
      ...prev,
      delivery_days: prev.delivery_days.includes(day)
        ? prev.delivery_days.filter(d => d !== day)
        : [...prev.delivery_days, day]
    }));
  };

  const handleCreateSubscription = async (e) => {
    e.preventDefault();

    if (formData.product_ids.length === 0) {
      toast.error('Please select at least one product');
      return;
    }
    if (formData.delivery_days.length === 0) {
      toast.error('Please select delivery days');
      return;
    }
    if (!formData.start_date || !formData.name || !formData.phone || !formData.address || !formData.city || !formData.state || !formData.pincode) {
      toast.error('Please fill all required fields');
      return;
    }

    setSubmitting(true);
    try {
      await apiClient.post('/subscriptions/create', {
        product_ids: formData.product_ids,
        frequency: formData.frequency,
        delivery_days: formData.delivery_days,
        delivery_time: formData.delivery_time,
        start_date: formData.start_date,
        delivery_info: {
          name: formData.name,
          phone: formData.phone,
          email: formData.email,
          address: formData.address,
          city: formData.city,
          state: formData.state,
          pincode: formData.pincode
        }
      });

      toast.success('Subscription created successfully!');
      setShowCreateForm(false);

      const subsRes = await apiClient.get('/subscriptions/my-subscriptions');
      setSubscriptions(subsRes.data.subscriptions);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create subscription');
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      active: 'bg-green-100 text-green-800',
      paused: 'bg-yellow-100 text-yellow-800',
      cancelled: 'bg-red-100 text-red-800'
    };
    return (
      <span className={`text-xs px-3 py-1 font-bold ${styles[status] || 'bg-gray-100 text-gray-800'}`} data-testid={`status-badge-${status}`}>
        {status.toUpperCase()}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col">
        <Navbar />
        <div className="flex-1 flex items-center justify-center">
          <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-surface" data-testid="subscriptions-page">
      <Navbar />

      <main className="flex-1 py-12">
        <div className="max-w-4xl mx-auto px-8">
          {/* Header */}
          <div className="flex items-start justify-between mb-8">
            <div>
              <h1 className="text-4xl font-black text-primary uppercase mb-2">SUBSCRIPTIONS</h1>
              <p className="text-sm text-muted">Get your favorites delivered on a regular schedule</p>
            </div>
            {!showCreateForm && (
              <button
                onClick={() => setShowCreateForm(true)}
                className="bg-accent text-white hover:bg-[#002280] transition-all border border-accent px-6 py-3 font-bold tracking-wide flex items-center gap-2"
                data-testid="new-subscription-button"
              >
                <Plus size={18} />
                NEW SUBSCRIPTION
              </button>
            )}
          </div>

          {/* Create Subscription Form */}
          {showCreateForm && (
            <form onSubmit={handleCreateSubscription} className="bg-white border border-border mb-8" data-testid="create-subscription-form">
              <div className="p-6 border-b border-border">
                <h2 className="text-xl font-bold text-primary">CREATE NEW SUBSCRIPTION</h2>
              </div>

              <div className="p-6 space-y-6">
                {/* Product Selection */}
                <div>
                  <label className="block text-sm font-medium text-primary mb-3">Select Products *</label>
                  {products.length === 0 ? (
                    <p className="text-sm text-muted">No products available for subscription</p>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {products.map((product) => (
                        <button
                          key={product.product_id}
                          type="button"
                          onClick={() => toggleProduct(product.product_id)}
                          className={`p-4 border text-left transition-all flex gap-3 items-center ${
                            formData.product_ids.includes(product.product_id)
                              ? 'border-accent bg-blue-50'
                              : 'border-border hover:bg-surface'
                          }`}
                          data-testid={`select-product-${product.product_id}`}
                        >
                          <div className="w-12 h-12 bg-surface flex-shrink-0 overflow-hidden">
                            {product.images?.[0]?.url ? (
                              <img src={product.images[0].url} alt={product.product_name} className="w-full h-full object-cover" />
                            ) : (
                              <div className="w-full h-full flex items-center justify-center">
                                <Package size={20} className="text-muted" />
                              </div>
                            )}
                          </div>
                          <div>
                            <p className="font-semibold text-primary text-sm">{product.product_name}</p>
                            <p className="text-xs text-muted">₹{product.base_price}</p>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* Frequency */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-primary mb-2">Frequency *</label>
                    <select
                      value={formData.frequency}
                      onChange={(e) => setFormData(prev => ({ ...prev, frequency: e.target.value }))}
                      className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
                      data-testid="subscription-frequency"
                    >
                      {frequencies.map(f => (
                        <option key={f.value} value={f.value}>{f.label}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-primary mb-2">Delivery Time *</label>
                    <select
                      value={formData.delivery_time}
                      onChange={(e) => setFormData(prev => ({ ...prev, delivery_time: e.target.value }))}
                      className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
                      data-testid="subscription-delivery-time"
                    >
                      <option value="morning">Morning (9 AM - 12 PM)</option>
                      <option value="afternoon">Afternoon (12 PM - 4 PM)</option>
                      <option value="evening">Evening (4 PM - 8 PM)</option>
                    </select>
                  </div>
                </div>

                {/* Delivery Days */}
                <div>
                  <label className="block text-sm font-medium text-primary mb-2">Delivery Days *</label>
                  <div className="flex flex-wrap gap-2">
                    {days.map((day) => (
                      <button
                        key={day}
                        type="button"
                        onClick={() => toggleDay(day)}
                        className={`px-4 py-2 text-xs font-bold tracking-wide border transition-all ${
                          formData.delivery_days.includes(day)
                            ? 'bg-accent text-white border-accent'
                            : 'bg-white text-primary border-border hover:bg-surface'
                        }`}
                        data-testid={`day-${day}`}
                      >
                        {day.slice(0, 3).toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Start Date */}
                <div>
                  <label className="block text-sm font-medium text-primary mb-2">Start Date *</label>
                  <input
                    type="date"
                    value={formData.start_date}
                    onChange={(e) => setFormData(prev => ({ ...prev, start_date: e.target.value }))}
                    min={new Date().toISOString().split('T')[0]}
                    className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none max-w-xs"
                    data-testid="subscription-start-date"
                  />
                </div>

                {/* Delivery Info */}
                <div>
                  <h3 className="text-base font-bold text-primary mb-4">DELIVERY ADDRESS</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-primary mb-2">Full Name *</label>
                      <input
                        type="text"
                        value={formData.name}
                        onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                        className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
                        data-testid="sub-input-name"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-primary mb-2">Phone *</label>
                      <input
                        type="tel"
                        value={formData.phone}
                        onChange={(e) => setFormData(prev => ({ ...prev, phone: e.target.value }))}
                        placeholder="+91-XXXXXXXXXX"
                        className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
                        data-testid="sub-input-phone"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-primary mb-2">Email</label>
                      <input
                        type="email"
                        value={formData.email}
                        onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                        className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
                        data-testid="sub-input-email"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-primary mb-2">Address *</label>
                      <textarea
                        value={formData.address}
                        onChange={(e) => setFormData(prev => ({ ...prev, address: e.target.value }))}
                        rows="2"
                        className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none resize-none"
                        data-testid="sub-input-address"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-primary mb-2">City *</label>
                      <input
                        type="text"
                        value={formData.city}
                        onChange={(e) => setFormData(prev => ({ ...prev, city: e.target.value }))}
                        className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
                        data-testid="sub-input-city"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-primary mb-2">State *</label>
                      <input
                        type="text"
                        value={formData.state}
                        onChange={(e) => setFormData(prev => ({ ...prev, state: e.target.value }))}
                        className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
                        data-testid="sub-input-state"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-primary mb-2">Pincode *</label>
                      <input
                        type="text"
                        value={formData.pincode}
                        onChange={(e) => setFormData(prev => ({ ...prev, pincode: e.target.value }))}
                        pattern="[0-9]{6}"
                        className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
                        data-testid="sub-input-pincode"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Form Actions */}
              <div className="p-6 border-t border-border flex gap-3">
                <button
                  type="submit"
                  disabled={submitting}
                  className="bg-primary text-white hover:bg-[#333333] transition-all border border-primary px-6 py-3 font-bold tracking-wide disabled:opacity-50"
                  data-testid="submit-subscription-button"
                >
                  {submitting ? 'CREATING...' : 'CREATE SUBSCRIPTION'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowCreateForm(false)}
                  className="bg-transparent text-primary hover:bg-secondary transition-all border border-border px-6 py-3 font-bold tracking-wide"
                  data-testid="cancel-subscription-form"
                >
                  CANCEL
                </button>
              </div>
            </form>
          )}

          {/* Existing Subscriptions */}
          {subscriptions.length === 0 && !showCreateForm ? (
            <div className="bg-white border border-border p-12 text-center">
              <RefreshCw size={48} className="mx-auto text-muted mb-4" strokeWidth={1.5} />
              <h2 className="text-2xl font-bold text-primary mb-2">NO SUBSCRIPTIONS YET</h2>
              <p className="text-muted mb-6">Subscribe to your favorite bakery items for regular deliveries</p>
              <button
                onClick={() => setShowCreateForm(true)}
                className="bg-accent text-white hover:bg-[#002280] transition-all border border-accent px-6 py-3 font-bold tracking-wide"
                data-testid="create-first-subscription"
              >
                CREATE YOUR FIRST SUBSCRIPTION
              </button>
            </div>
          ) : (
            <div className="space-y-4" data-testid="subscriptions-list">
              {subscriptions.map((sub) => (
                <div
                  key={sub.subscription_id}
                  className="bg-white border border-border"
                  data-testid={`subscription-${sub.subscription_id}`}
                >
                  <div className="p-6">
                    <div className="flex items-start justify-between mb-4">
                      <div>
                        <div className="flex items-center gap-3 mb-1">
                          <RefreshCw size={18} className="text-accent" />
                          <span className="text-sm font-bold text-primary uppercase">{sub.frequency} Subscription</span>
                        </div>
                        <p className="text-xs text-muted">ID: {sub.subscription_id}</p>
                      </div>
                      {getStatusBadge(sub.status)}
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                      <div className="flex items-center gap-2 text-sm">
                        <Calendar size={16} className="text-muted" />
                        <span className="text-muted">Started: {sub.start_date || 'N/A'}</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <Clock size={16} className="text-muted" />
                        <span className="text-muted">{sub.delivery_time || 'N/A'}</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <Package size={16} className="text-muted" />
                        <span className="text-muted">{sub.product_ids?.length || 0} product(s)</span>
                      </div>
                    </div>

                    {sub.delivery_days?.length > 0 && (
                      <div className="flex flex-wrap gap-1 mb-4">
                        {sub.delivery_days.map(day => (
                          <span key={day} className="text-xs px-2 py-1 bg-surface font-medium text-muted">
                            {day.slice(0, 3).toUpperCase()}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Actions */}
                    {sub.status !== 'cancelled' && (
                      <div className="flex gap-2 pt-4 border-t border-border">
                        {sub.status === 'active' ? (
                          <button
                            onClick={() => handlePause(sub.subscription_id)}
                            className="flex items-center gap-1 px-4 py-2 text-xs font-bold border border-border text-primary hover:bg-surface transition-all"
                            data-testid={`pause-sub-${sub.subscription_id}`}
                          >
                            <Pause size={14} /> PAUSE
                          </button>
                        ) : sub.status === 'paused' ? (
                          <button
                            onClick={() => handleResume(sub.subscription_id)}
                            className="flex items-center gap-1 px-4 py-2 text-xs font-bold border border-accent text-accent hover:bg-blue-50 transition-all"
                            data-testid={`resume-sub-${sub.subscription_id}`}
                          >
                            <Play size={14} /> RESUME
                          </button>
                        ) : null}
                        <button
                          onClick={() => handleCancel(sub.subscription_id)}
                          className="flex items-center gap-1 px-4 py-2 text-xs font-bold border border-destructive text-destructive hover:bg-red-50 transition-all"
                          data-testid={`cancel-sub-${sub.subscription_id}`}
                        >
                          <X size={14} /> CANCEL
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default SubscriptionsPage;
