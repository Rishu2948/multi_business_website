/**
 * OffersManager — Admin page
 * Full CRUD for offers. Scope selector pulls from live API categories/collections.
 * Mobile-responsive: form opens as bottom sheet.
 */

import { useState, useEffect, useCallback } from 'react';
import { Plus, Edit2, Trash2, Tag } from 'lucide-react';
import Navbar from '../../components/common/Navbar';
import { useBusiness } from '../../context/BusinessContext';
import apiClient from '../../utils/api';

// ── Helpers ────────────────────────────────────────────────────────────────

const OFFER_TYPES = [
  { value: 'percentage',   label: '% Percentage off' },
  { value: 'flat_amount',  label: '₹ Flat amount off' },
  { value: 'free_delivery',label: '🚚 Free delivery' },
];

const SCOPE_OPTIONS = [
  { value: 'all_products',          label: 'All products' },
  { value: 'specific_categories',   label: 'Specific categories' },
  { value: 'specific_products',     label: 'Specific products' },
  { value: 'specific_collections',  label: 'Specific collections' },
];

const fmt = dt => dt ? new Date(dt).toLocaleDateString('en-IN', { day:'numeric', month:'short', year:'numeric' }) : '—';
const isExpired = offer => new Date(offer.valid_until) < new Date();

const StatusBadge = ({ offer }) => {
  if (!offer.is_active) return <span className="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 font-bold">INACTIVE</span>;
  if (isExpired(offer)) return <span className="text-[10px] bg-red-100 text-red-600 px-1.5 py-0.5 font-bold">EXPIRED</span>;
  return <span className="text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 font-bold">ACTIVE</span>;
};

// ── Offer form ─────────────────────────────────────────────────────────────

const OfferForm = ({ initial, onSave, onCancel, businessId }) => {
  const [categories, setCategories] = useState([]);
  const [collections, setCollections] = useState([]);

  const [form, setForm] = useState(initial || {
    title: '', description: '', promo_code: '',
    offer_type: 'percentage', discount_value: '',
    max_discount_cap: '', min_order_amount: '',
    scope: 'all_products', scope_ids: [],
    valid_from: new Date().toISOString().slice(0,16),
    valid_until: new Date(Date.now() + 30*86400000).toISOString().slice(0,16),
    is_auto_apply: false, usage_limit: '', per_user_limit: 1,
    show_in_offers_panel: true,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    apiClient.get(`/admin/categories/${businessId}`).then(r => setCategories(r.data.categories || [])).catch(() => {});
    apiClient.get(`/admin/collections/${businessId}`).then(r => setCollections(r.data.collections || [])).catch(() => {});
  }, [businessId]);

  const upd = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const toggleScopeId = id => {
    const current = form.scope_ids;
    upd('scope_ids', current.includes(id) ? current.filter(x => x !== id) : [...current, id]);
  };

  const handleSubmit = async e => {
    e.preventDefault();
    if (!form.title.trim()) { setError('Title required'); return; }
    if (!form.discount_value && form.offer_type !== 'free_delivery') { setError('Discount value required'); return; }
    setSaving(true); setError('');
    try {
      const payload = {
        ...form,
        business_id: businessId,
        discount_value: parseFloat(form.discount_value) || 0,
        min_order_amount: parseFloat(form.min_order_amount) || 0,
        max_discount_cap: form.max_discount_cap ? parseFloat(form.max_discount_cap) : null,
        usage_limit: form.usage_limit ? parseInt(form.usage_limit) : null,
        per_user_limit: parseInt(form.per_user_limit) || 1,
        promo_code: form.promo_code ? form.promo_code.toUpperCase().trim() : null,
        valid_from: new Date(form.valid_from).toISOString(),
        valid_until: new Date(form.valid_until).toISOString(),
      };
      await onSave(payload);
    } catch (err) {
      setError(err.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const Label = ({ children, htmlFor }) => (
    <label htmlFor={htmlFor} className="block text-xs font-semibold uppercase tracking-wide text-[#786A60] mb-1">
      {children}
    </label>
  );

  const Input = ({ id, type='text', value, onChange, placeholder, testId }) => (
    <input id={id} type={type} value={value ?? ''} onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#4A3B32] bg-white"
      data-testid={testId} />
  );

  // Scope picker items
  const scopeItems = form.scope === 'specific_categories' ? categories
    : form.scope === 'specific_collections' ? collections
    : [];

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div className="bg-white w-full sm:max-w-2xl max-h-[94vh] overflow-y-auto">
        <div className="p-6">
          <h2 className="font-serif text-xl text-[#2C2420] mb-5">{initial ? 'Edit Offer' : 'New Offer'}</h2>
          {error && <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 mb-4" role="alert">{error}</div>}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Title + Description */}
            <div>
              <Label htmlFor="offer-title">Title *</Label>
              <Input id="offer-title" value={form.title} onChange={v => upd('title', v)}
                placeholder="FLAT 15% OFF on all combos" testId="offer-title-input" />
            </div>
            <div>
              <Label htmlFor="offer-desc">Description (shown in offers panel)</Label>
              <Input id="offer-desc" value={form.description} onChange={v => upd('description', v)}
                placeholder="Valid on minimum order of ₹199" testId="offer-desc-input" />
            </div>

            {/* Promo code + auto-apply */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="promo-code">Promo Code (leave blank for auto-apply)</Label>
                <Input id="promo-code" value={form.promo_code} onChange={v => upd('promo_code', v.toUpperCase())}
                  placeholder="COMBO15" testId="promo-code-input" />
              </div>
              <div className="flex flex-col justify-end pb-1">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={form.is_auto_apply}
                    onChange={e => upd('is_auto_apply', e.target.checked)}
                    className="w-4 h-4 accent-[#4A3B32]" data-testid="auto-apply-cb" />
                  <span className="text-sm text-[#2C2420]">Auto-apply at checkout</span>
                </label>
              </div>
            </div>

            {/* Offer type + value */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <Label htmlFor="offer-type">Offer Type *</Label>
                <select id="offer-type" value={form.offer_type} onChange={e => upd('offer_type', e.target.value)}
                  className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-[#4A3B32]"
                  data-testid="offer-type-select">
                  {OFFER_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              {form.offer_type !== 'free_delivery' && (
                <div>
                  <Label htmlFor="discount-val">Discount Value *</Label>
                  <Input id="discount-val" type="number" value={form.discount_value}
                    onChange={v => upd('discount_value', v)}
                    placeholder={form.offer_type === 'percentage' ? '15' : '200'} testId="discount-val-input" />
                </div>
              )}
              {form.offer_type === 'percentage' && (
                <div>
                  <Label htmlFor="max-cap">Max Cap ₹ (optional)</Label>
                  <Input id="max-cap" type="number" value={form.max_discount_cap}
                    onChange={v => upd('max_discount_cap', v)} placeholder="500" testId="max-cap-input" />
                </div>
              )}
            </div>

            {/* Min order */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="min-order">Min Order Amount ₹</Label>
                <Input id="min-order" type="number" value={form.min_order_amount}
                  onChange={v => upd('min_order_amount', v)} placeholder="0" testId="min-order-input" />
              </div>
              <div>
                <Label htmlFor="per-user">Per User Limit</Label>
                <Input id="per-user" type="number" value={form.per_user_limit}
                  onChange={v => upd('per_user_limit', v)} placeholder="1" testId="per-user-input" />
              </div>
            </div>

            {/* Scope */}
            <div>
              <Label htmlFor="offer-scope">Applies To</Label>
              <select id="offer-scope" value={form.scope} onChange={e => { upd('scope', e.target.value); upd('scope_ids', []); }}
                className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-[#4A3B32]"
                data-testid="offer-scope-select">
                {SCOPE_OPTIONS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>

            {/* Scope ID picker */}
            {scopeItems.length > 0 && (
              <div>
                <Label>Select {form.scope === 'specific_categories' ? 'Categories' : 'Collections'}</Label>
                <div className="flex flex-wrap gap-2 mt-1">
                  {scopeItems.map(item => {
                    const id = item.category_id || item.collection_id;
                    const active = form.scope_ids.includes(id);
                    return (
                      <button key={id} type="button" onClick={() => toggleScopeId(id)}
                        className={`px-3 py-1.5 text-xs font-medium border transition-colors
                          ${active ? 'bg-[#4A3B32] text-white border-[#4A3B32]' : 'bg-white text-[#786A60] border-[#E8E0D5]'}`}
                        data-testid={`scope-id-${id}`}>
                        {item.display_name}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Validity */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="valid-from">Valid From</Label>
                <input type="datetime-local" id="valid-from" value={form.valid_from}
                  onChange={e => upd('valid_from', e.target.value)}
                  className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-[#4A3B32]"
                  data-testid="valid-from-input" />
              </div>
              <div>
                <Label htmlFor="valid-until">Valid Until</Label>
                <input type="datetime-local" id="valid-until" value={form.valid_until}
                  onChange={e => upd('valid_until', e.target.value)}
                  className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-[#4A3B32]"
                  data-testid="valid-until-input" />
              </div>
            </div>

            {/* Options */}
            <div className="flex flex-wrap gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.show_in_offers_panel}
                  onChange={e => upd('show_in_offers_panel', e.target.checked)}
                  className="w-4 h-4 accent-[#4A3B32]" data-testid="show-panel-cb" />
                <span className="text-sm text-[#2C2420]">Show in offers panel</span>
              </label>
            </div>

            <div className="flex gap-3 pt-2">
              <button type="submit" disabled={saving}
                className="flex-1 bg-[#4A3B32] text-white py-3 text-sm font-semibold hover:bg-[#332822] disabled:opacity-60"
                data-testid="offer-save-btn">
                {saving ? 'Saving...' : (initial ? 'Update Offer' : 'Create Offer')}
              </button>
              <button type="button" onClick={onCancel}
                className="px-6 py-3 text-sm text-[#786A60] border border-[#E8E0D5] hover:bg-[#FAF8F5]"
                data-testid="offer-cancel-btn">
                Cancel
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

// ── Main page ──────────────────────────────────────────────────────────────

const OffersManager = () => {
  const { selectedBusiness } = useBusiness();
  const businessId = selectedBusiness?.business_id;

  const [offers, setOffers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingOffer, setEditingOffer] = useState(null);

  const fetch = useCallback(async () => {
    if (!businessId) return;
    try {
      const r = await apiClient.get(`/admin/offers/${businessId}`);
      setOffers(r.data.offers || []);
    } finally {
      setLoading(false);
    }
  }, [businessId]);

  useEffect(() => { fetch(); }, [fetch]);

  const handleCreate = async data => {
    await apiClient.post('/admin/offers', data);
    await fetch();
    setShowForm(false);
  };

  const handleUpdate = async data => {
    const { offer_id, business_id, ...updates } = data;
    await apiClient.put(`/admin/offers/${editingOffer.offer_id}`, updates);
    await fetch();
    setEditingOffer(null);
  };

  const handleDeactivate = async offer => {
    if (!window.confirm(`Deactivate "${offer.title}"?`)) return;
    await apiClient.delete(`/admin/offers/${offer.offer_id}`);
    await fetch();
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

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5]">
      <Navbar />
      <main className="flex-1 py-6" data-testid="offers-manager">
        <div className="max-w-5xl mx-auto px-4 md:px-8">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <div>
              <h1 className="text-2xl font-black tracking-tight text-[#2C2420] uppercase">Offers Manager</h1>
              <p className="text-sm text-[#786A60] mt-1">{selectedBusiness?.business_name}</p>
            </div>
            <button onClick={() => setShowForm(true)}
              className="flex items-center gap-2 bg-[#4A3B32] text-white px-5 py-3 text-sm font-semibold hover:bg-[#332822] self-start"
              data-testid="add-offer-btn">
              <Plus size={16} />
              Create Offer
            </button>
          </div>

          {/* Offers table */}
          <div className="bg-white border border-[#E8E0D5]">
            {offers.length === 0 ? (
              <div className="text-center py-16">
                <Tag size={32} className="mx-auto text-[#786A60] mb-3" strokeWidth={1.5} />
                <p className="text-[#786A60] mb-3">No offers yet.</p>
                <button onClick={() => setShowForm(true)} className="text-sm text-[#4A3B32] underline">
                  Create your first offer
                </button>
              </div>
            ) : (
              offers.map(offer => (
                <div key={offer.offer_id}
                  className="p-4 border-b border-[#E8E0D5] last:border-0"
                  data-testid={`offer-row-${offer.offer_id}`}>
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <StatusBadge offer={offer} />
                        {offer.promo_code && (
                          <code className="text-xs font-mono bg-[#F3EFEA] text-[#4A3B32] px-2 py-0.5">
                            {offer.promo_code}
                          </code>
                        )}
                        {offer.is_auto_apply && (
                          <span className="text-[10px] bg-[#FAF8F5] border border-[#E8E0D5] text-[#786A60] px-1.5 py-0.5">
                            AUTO-APPLY
                          </span>
                        )}
                      </div>
                      <p className="text-sm font-semibold text-[#2C2420]">{offer.title}</p>
                      {offer.description && <p className="text-xs text-[#786A60] mt-0.5">{offer.description}</p>}
                      <div className="flex flex-wrap gap-3 mt-2 text-xs text-[#786A60]">
                        <span>
                          {offer.offer_type === 'percentage' ? `${offer.discount_value}% off`
                            : offer.offer_type === 'flat_amount' ? `₹${offer.discount_value} off`
                            : 'Free delivery'}
                        </span>
                        <span>Scope: {offer.scope?.replace(/_/g,' ')}</span>
                        <span>Valid: {fmt(offer.valid_from)} – {fmt(offer.valid_until)}</span>
                        <span>Used: {offer.usage_count || 0}{offer.usage_limit ? `/${offer.usage_limit}` : ''}</span>
                      </div>
                    </div>
                    <div className="flex gap-2 flex-shrink-0">
                      <button onClick={() => setEditingOffer(offer)}
                        className="p-2 text-[#786A60] hover:text-[#4A3B32] border border-[#E8E0D5]"
                        aria-label="Edit offer" data-testid={`edit-offer-${offer.offer_id}`}>
                        <Edit2 size={14} />
                      </button>
                      <button onClick={() => handleDeactivate(offer)}
                        className="p-2 text-[#786A60] hover:text-red-500 border border-[#E8E0D5]"
                        aria-label="Deactivate offer" data-testid={`delete-offer-${offer.offer_id}`}>
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </main>

      {showForm && (
        <OfferForm businessId={businessId} onSave={handleCreate} onCancel={() => setShowForm(false)} />
      )}
      {editingOffer && (
        <OfferForm initial={editingOffer} businessId={businessId}
          onSave={handleUpdate} onCancel={() => setEditingOffer(null)} />
      )}
    </div>
  );
};

export default OffersManager;
