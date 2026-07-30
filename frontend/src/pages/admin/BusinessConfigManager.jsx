/**
 * BusinessConfigManager — Admin page
 * Manage business-wide settings including Prime membership configuration.
 * Separate from StoreConfigManager which handles per-store operational settings.
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Navbar from '../../components/common/Navbar';
import { useBusiness } from '../../context/BusinessContext';
import { useAuth } from '../../context/AuthContext';
import apiClient from '../../utils/api';
import { Save, ToggleLeft, ToggleRight, Crown } from 'lucide-react';

const FEATURE_KEYS = ['ai_chatbot', 'priority_support', 'free_delivery', 'early_access'];

const FEATURE_LABELS = {
  ai_chatbot: 'AI Catalog Assistant',
  priority_support: 'Priority Customer Support',
  free_delivery: 'Free Delivery',
  early_access: 'Early Access to New Products',
};

const Toggle = ({ checked, onChange, label, testId }) => (
  <button
    type="button"
    onClick={() => onChange(!checked)}
    className={`flex items-center gap-2 text-sm transition-colors ${checked ? 'text-green-700' : 'text-[#786A60]'}`}
    aria-pressed={checked}
    data-testid={testId}
  >
    {checked
      ? <ToggleRight size={24} className="text-green-600" />
      : <ToggleLeft size={24} className="text-[#786A60]" />
    }
    {label}
  </button>
);

const FieldLabel = ({ children, htmlFor }) => (
  <label htmlFor={htmlFor}
    className="block text-xs font-semibold uppercase tracking-wide text-[#786A60] mb-1">
    {children}
  </label>
);

const TextInput = ({ id, value, onChange, placeholder, type = 'text', testId }) => (
  <input
    id={id}
    type={type}
    value={value ?? ''}
    onChange={e => onChange(e.target.value)}
    placeholder={placeholder}
    className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm text-[#2C2420]
               focus:outline-none focus:ring-1 focus:ring-[#4A3B32] bg-white"
    data-testid={testId}
  />
);

const BusinessConfigManager = () => {
  const { selectedBusiness } = useBusiness();
  const { user } = useAuth();
  const { businessId: urlBusinessId } = useParams();
  const navigate = useNavigate();

  // Super admin uses URL param, business admin uses selected business
  const businessId = user?.role === 'super_admin' ? urlBusinessId : selectedBusiness?.business_id;

  // Redirect super admin to selector if no business_id in URL
  useEffect(() => {
    if (user?.role === 'super_admin' && !urlBusinessId) {
      navigate('/admin/business-config');
    }
  }, [user, urlBusinessId, navigate]);

  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!businessId) return;
    apiClient.get(`/admin/business-config/${businessId}`)
      .then(res => setConfig(res.data))
      .catch(() => setError('Failed to load business config'))
      .finally(() => setLoading(false));
  }, [businessId]);

  const update = (field, value) => setConfig(c => ({ ...c, [field]: value }));

  const updatePrime = (field, value) => {
    setConfig(c => ({
      ...c,
      prime: { ...c.prime, [field]: value }
    }));
  };

  const updatePlan = (index, field, value) => {
    const plans = [...(config.prime?.plans || [])];
    plans[index] = { ...plans[index], [field]: value };
    updatePrime('plans', plans);
  };

  const addPlan = () => {
    const plans = [...(config.prime?.plans || [])];
    plans.push({
      plan_id: `plan_${Date.now()}`,
      name: 'New Plan',
      billing_cycle: 'monthly',
      price: 0,
      currency: 'INR',
      is_active: true,
      marketing_features: [],
    });
    updatePrime('plans', plans);
  };

  const removePlan = (index) => {
    const plans = [...(config.prime?.plans || [])];
    plans.splice(index, 1);
    updatePrime('plans', plans);
  };

  const updateFeature = (key, field, value) => {
    const features = { ...(config.prime?.features || {}) };
    features[key] = { ...features[key], [field]: value };
    updatePrime('features', features);
  };

  const handleSave = async e => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      await apiClient.put(`/admin/business-config/${businessId}`, { prime: config.prime });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col">
        <Navbar />
        <div className="flex-1 flex items-center justify-center">
          <div className="w-8 h-8 border-4 border-[#4A3B32] border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  if (!config) return null;

  const prime = config.prime || {
    enabled: false,
    display_name: '',
    tagline: '',
    plans: [],
    features: {},
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5]">
      <Navbar />
      <main className="flex-1 py-6" data-testid="business-config-manager">
        <div className="max-w-3xl mx-auto px-4 md:px-8">
          <div className="mb-6">
            <h1 className="text-2xl font-black tracking-tight text-[#2C2420] uppercase">Business Configuration</h1>
            <p className="text-sm text-[#786A60] mt-1">{selectedBusiness?.business_name}</p>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 mb-4" role="alert">
              {error}
            </div>
          )}

          <form onSubmit={handleSave} className="space-y-6">
            {/* Prime Membership Section */}
            <section className="bg-white border border-[#E8E0D5] p-6">
              <h2 className="font-semibold text-[#2C2420] mb-4 flex items-center gap-2">
                <Crown size={16} className="text-[#4A3B32]" />
                Prime Membership
              </h2>

              <div className="space-y-4">
                <div className="flex flex-wrap gap-6">
                  <Toggle
                    checked={prime.enabled}
                    onChange={v => updatePrime('enabled', v)}
                    label="Enable Prime"
                    testId="prime-enabled-toggle"
                  />
                </div>

                {prime.enabled && (
                  <>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <FieldLabel htmlFor="prime-display-name">Display Name</FieldLabel>
                        <TextInput
                          id="prime-display-name"
                          value={prime.display_name}
                          onChange={v => updatePrime('display_name', v)}
                          placeholder="Whisked Words Prime"
                          testId="prime-display-name-input"
                        />
                      </div>
                      <div>
                        <FieldLabel htmlFor="prime-tagline">Tagline</FieldLabel>
                        <TextInput
                          id="prime-tagline"
                          value={prime.tagline}
                          onChange={v => updatePrime('tagline', v)}
                          placeholder="Unlock premium features"
                          testId="prime-tagline-input"
                        />
                      </div>
                    </div>

                    {/* Plans */}
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <FieldLabel>Subscription Plans</FieldLabel>
                        <button
                          type="button"
                          onClick={addPlan}
                          className="text-sm text-[#4A3B32] hover:underline"
                        >
                          + Add Plan
                        </button>
                      </div>
                      <div className="space-y-3">
                        {prime.plans.map((plan, index) => (
                          <div key={plan.plan_id || index} className="border border-[#E8E0D5] p-4 rounded">
                            <div className="flex justify-between items-start mb-3">
                              <div className="flex-1 grid grid-cols-2 gap-3">
                                <TextInput
                                  value={plan.name}
                                  onChange={v => updatePlan(index, 'name', v)}
                                  placeholder="Plan Name"
                                  testId={`plan-name-${index}`}
                                />
                                <select
                                  value={plan.billing_cycle}
                                  onChange={e => updatePlan(index, 'billing_cycle', e.target.value)}
                                  className="border border-[#E8E0D5] px-3 py-2.5 text-sm text-[#2C2420]
                                             focus:outline-none focus:ring-1 focus:ring-[#4A3B32] bg-white"
                                >
                                  <option value="monthly">Monthly</option>
                                  <option value="annual">Annual</option>
                                </select>
                                <TextInput
                                  type="number"
                                  value={plan.price}
                                  onChange={v => updatePlan(index, 'price', parseFloat(v) || 0)}
                                  placeholder="Price"
                                  testId={`plan-price-${index}`}
                                />
                                <Toggle
                                  checked={plan.is_active}
                                  onChange={v => updatePlan(index, 'is_active', v)}
                                  label="Active"
                                  testId={`plan-active-${index}`}
                                />
                              </div>
                              <button
                                type="button"
                                onClick={() => removePlan(index)}
                                className="text-red-600 hover:text-red-700 text-sm"
                              >
                                Remove
                              </button>
                            </div>
                            <div>
                              <FieldLabel htmlFor={`plan-features-${index}`}>Marketing Features (one per line)</FieldLabel>
                              <textarea
                                id={`plan-features-${index}`}
                                value={plan.marketing_features?.join('\n') || ''}
                                onChange={e => updatePlan(index, 'marketing_features', e.target.value.split('\n').filter(Boolean))}
                                placeholder="AI Catalog Assistant&#10;Priority Support"
                                className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm text-[#2C2420]
                                           focus:outline-none focus:ring-1 focus:ring-[#4A3B32] bg-white"
                                rows={2}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Features */}
                    <div>
                      <FieldLabel>Feature Access</FieldLabel>
                      <div className="space-y-2">
                        {FEATURE_KEYS.map(key => (
                          <div key={key} className="flex items-center justify-between py-2 border-b border-[#F3EFEA]">
                            <span className="text-sm text-[#2C2420]">{FEATURE_LABELS[key]}</span>
                            <div className="flex items-center gap-3">
                              <TextInput
                                value={prime.features[key]?.label || ''}
                                onChange={v => updateFeature(key, 'label', v)}
                                placeholder="Label"
                                className="w-40"
                                testId={`feature-label-${key}`}
                              />
                              <Toggle
                                checked={prime.features[key]?.enabled || false}
                                onChange={v => updateFeature(key, 'enabled', v)}
                                label={prime.features[key]?.enabled ? 'Enabled' : 'Disabled'}
                                testId={`feature-enabled-${key}`}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </div>
            </section>

            {/* Save */}
            <div className="flex items-center gap-4 pb-8">
              <button
                type="submit"
                disabled={saving}
                className="flex items-center gap-2 bg-[#4A3B32] text-white px-8 py-3
                           text-sm font-semibold hover:bg-[#332822] disabled:opacity-60
                           transition-colors min-h-[44px]"
                data-testid="save-business-config"
              >
                <Save size={16} />
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
              {saved && (
                <span className="text-sm text-green-600 font-medium" role="status">
                  ✓ Saved successfully
                </span>
              )}
            </div>
          </form>
        </div>
      </main>
    </div>
  );
};

export default BusinessConfigManager;
