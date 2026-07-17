/**
 * StoreConfigManager — Admin page
 * Edit store display name, location, per-day business hours,
 * order types, delivery settings, and temporarily-closed toggle.
 * All saved to store_config collection — reflects on OrderNavbar instantly.
 */

import { useState, useEffect } from 'react';
import Navbar from '../../components/common/Navbar';
import { useBusiness } from '../../context/BusinessContext';
import apiClient from '../../utils/api';
import { Save, ToggleLeft, ToggleRight, Clock } from 'lucide-react';

const DAYS = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'];
const ORDER_TYPE_OPTIONS = ['delivery','takeaway','dine_in'];

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

const DEFAULT_HOURS = DAYS.map(day => ({
  day, is_open: true, open_time: '08:00', close_time: '22:00',
}));

const StoreConfigManager = () => {
  const { selectedBusiness } = useBusiness();
  const businessId = selectedBusiness?.business_id;

  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!businessId) return;
    apiClient.get(`/admin/store/${businessId}`)
      .then(res => setConfig(res.data))
      .catch(() => setError('Failed to load store config'))
      .finally(() => setLoading(false));
  }, [businessId]);

  const update = (field, value) => setConfig(c => ({ ...c, [field]: value }));

  const updateHours = (dayIndex, field, value) => {
    const hours = [...(config.business_hours || DEFAULT_HOURS)];
    hours[dayIndex] = { ...hours[dayIndex], [field]: value };
    update('business_hours', hours);
  };

  const toggleOrderType = type => {
    const current = config.order_types || ['delivery'];
    const updated = current.includes(type)
      ? current.filter(t => t !== type)
      : [...current, type];
    update('order_types', updated.length ? updated : ['delivery']);
  };

  const handleSave = async e => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const { is_open, business_id, ...payload } = config;
      await apiClient.put(`/admin/store/${businessId}`, payload);
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

  const hours = config.business_hours || DEFAULT_HOURS;

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5]">
      <Navbar />
      <main className="flex-1 py-6" data-testid="store-config-manager">
        <div className="max-w-3xl mx-auto px-4 md:px-8">
          <div className="mb-6">
            <h1 className="text-2xl font-black tracking-tight text-[#2C2420] uppercase">Store Configuration</h1>
            <p className="text-sm text-[#786A60] mt-1">{selectedBusiness?.business_name}</p>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 mb-4" role="alert">
              {error}
            </div>
          )}

          <form onSubmit={handleSave} className="space-y-6">
            {/* Basic Info */}
            <section className="bg-white border border-[#E8E0D5] p-6">
              <h2 className="font-semibold text-[#2C2420] mb-4 flex items-center gap-2">
                <span className="w-2 h-2 bg-[#4A3B32] rounded-full" />
                Basic Info
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <FieldLabel htmlFor="store-name">Display Name</FieldLabel>
                  <TextInput id="store-name" value={config.store_display_name}
                    onChange={v => update('store_display_name', v)}
                    placeholder="Whisked Words" testId="store-name-input" />
                </div>
                <div>
                  <FieldLabel htmlFor="store-location">Location Label</FieldLabel>
                  <TextInput id="store-location" value={config.location_label}
                    onChange={v => update('location_label', v)}
                    placeholder="HSR Layout, Bengaluru" testId="store-location-input" />
                </div>
              </div>

              <div className="mt-4 flex flex-wrap gap-6">
                <Toggle
                  checked={config.is_temporarily_closed}
                  onChange={v => update('is_temporarily_closed', v)}
                  label="Temporarily Closed"
                  testId="temp-closed-toggle"
                />
              </div>

              {config.is_temporarily_closed && (
                <div className="mt-3">
                  <FieldLabel htmlFor="closed-reason">Closed Reason (shown to customers)</FieldLabel>
                  <TextInput id="closed-reason" value={config.closed_reason}
                    onChange={v => update('closed_reason', v)}
                    placeholder="Closed for maintenance — reopening tomorrow"
                    testId="closed-reason-input" />
                </div>
              )}
            </section>

            {/* Business Hours */}
            <section className="bg-white border border-[#E8E0D5] p-6">
              <h2 className="font-semibold text-[#2C2420] mb-4 flex items-center gap-2">
                <Clock size={16} className="text-[#4A3B32]" />
                Business Hours
              </h2>
              <div className="space-y-2">
                {hours.map((dayHours, i) => (
                  <div key={dayHours.day}
                    className="grid grid-cols-12 gap-2 items-center py-2 border-b border-[#F3EFEA] last:border-0">
                    <div className="col-span-3 sm:col-span-2">
                      <span className="text-sm text-[#2C2420] capitalize">{dayHours.day.slice(0,3)}</span>
                    </div>
                    <div className="col-span-3 sm:col-span-2">
                      <Toggle
                        checked={dayHours.is_open}
                        onChange={v => updateHours(i, 'is_open', v)}
                        label={dayHours.is_open ? 'Open' : 'Closed'}
                        testId={`day-toggle-${dayHours.day}`}
                      />
                    </div>
                    {dayHours.is_open && (
                      <>
                        <div className="col-span-3 sm:col-span-4">
                          <input
                            type="time"
                            value={dayHours.open_time}
                            onChange={e => updateHours(i, 'open_time', e.target.value)}
                            className="w-full border border-[#E8E0D5] px-2 py-1.5 text-sm
                                       focus:outline-none focus:ring-1 focus:ring-[#4A3B32]"
                            aria-label={`${dayHours.day} opening time`}
                            data-testid={`open-time-${dayHours.day}`}
                          />
                        </div>
                        <div className="col-span-1 text-center text-xs text-[#786A60]">–</div>
                        <div className="col-span-2 sm:col-span-3">
                          <input
                            type="time"
                            value={dayHours.close_time}
                            onChange={e => updateHours(i, 'close_time', e.target.value)}
                            className="w-full border border-[#E8E0D5] px-2 py-1.5 text-sm
                                       focus:outline-none focus:ring-1 focus:ring-[#4A3B32]"
                            aria-label={`${dayHours.day} closing time`}
                            data-testid={`close-time-${dayHours.day}`}
                          />
                        </div>
                      </>
                    )}
                  </div>
                ))}
              </div>
            </section>

            {/* Order Types */}
            <section className="bg-white border border-[#E8E0D5] p-6">
              <h2 className="font-semibold text-[#2C2420] mb-4">Order Types</h2>
              <div className="flex flex-wrap gap-4">
                {ORDER_TYPE_OPTIONS.map(type => {
                  const active = (config.order_types || []).includes(type);
                  return (
                    <button
                      key={type}
                      type="button"
                      onClick={() => toggleOrderType(type)}
                      className={`px-4 py-2 text-sm font-medium border transition-colors capitalize
                        ${active
                          ? 'bg-[#4A3B32] text-white border-[#4A3B32]'
                          : 'bg-white text-[#786A60] border-[#E8E0D5] hover:border-[#4A3B32]'
                        }`}
                      aria-pressed={active}
                      data-testid={`order-type-${type}`}
                    >
                      {type.replace('_', ' ')}
                    </button>
                  );
                })}
              </div>
            </section>

            {/* Delivery Settings */}
            <section className="bg-white border border-[#E8E0D5] p-6">
              <h2 className="font-semibold text-[#2C2420] mb-4">Delivery Settings</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <FieldLabel htmlFor="min-order">Min Order (Delivery) ₹</FieldLabel>
                  <TextInput id="min-order" type="number" value={config.min_order_delivery}
                    onChange={v => update('min_order_delivery', parseFloat(v) || 0)}
                    placeholder="199" testId="min-order-input" />
                </div>
                <div>
                  <FieldLabel htmlFor="delivery-charge">Delivery Charge ₹</FieldLabel>
                  <TextInput id="delivery-charge" type="number" value={config.delivery_charge}
                    onChange={v => update('delivery_charge', parseFloat(v) || 0)}
                    placeholder="50" testId="delivery-charge-input" />
                </div>
                <div>
                  <FieldLabel htmlFor="free-delivery">Free Delivery Above ₹ (leave blank to disable)</FieldLabel>
                  <TextInput id="free-delivery" type="number" value={config.free_delivery_above ?? ''}
                    onChange={v => update('free_delivery_above', v ? parseFloat(v) : null)}
                    placeholder="499" testId="free-delivery-input" />
                </div>
                <div>
                  <FieldLabel htmlFor="delivery-radius">Delivery Radius (km)</FieldLabel>
                  <TextInput id="delivery-radius" type="number" value={config.delivery_radius_km}
                    onChange={v => update('delivery_radius_km', parseFloat(v) || 10)}
                    placeholder="10" testId="delivery-radius-input" />
                </div>
                <div>
                  <FieldLabel htmlFor="est-delivery">Est. Delivery Time</FieldLabel>
                  <TextInput id="est-delivery" value={config.estimated_delivery_time}
                    onChange={v => update('estimated_delivery_time', v)}
                    placeholder="30-45 mins" testId="est-delivery-input" />
                </div>
                <div>
                  <FieldLabel htmlFor="est-prep">Est. Prep Time</FieldLabel>
                  <TextInput id="est-prep" value={config.estimated_prep_time}
                    onChange={v => update('estimated_prep_time', v)}
                    placeholder="15-20 mins" testId="est-prep-input" />
                </div>
                <div>
                  <FieldLabel htmlFor="tax-rate">Tax Rate (e.g. 0.05 = 5%)</FieldLabel>
                  <TextInput id="tax-rate" type="number" value={config.tax_rate}
                    onChange={v => update('tax_rate', parseFloat(v) || 0.05)}
                    placeholder="0.05" testId="tax-rate-input" />
                </div>
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
                data-testid="save-store-config"
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

export default StoreConfigManager;
