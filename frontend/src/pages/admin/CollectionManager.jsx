/**
 * CollectionManager — Admin page
 * Manage product groupings: Gifting, Festive, Corporate, etc.
 * show_in_nav toggle controls whether collection appears in navbar.
 * show_on_homepage controls the homepage tiles.
 */

import { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, ToggleLeft, ToggleRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import Navbar from '../../components/common/Navbar';
import { useBusiness } from '../../context/BusinessContext';
import apiClient from '../../utils/api';

const CollectionForm = ({ initial, onSave, onCancel, businessId }) => {
  const [form, setForm] = useState(initial || {
    display_name: '',
    description: '',
    banner_image_url: '',
    illustration_url: '',
    sort_order: 999,
    show_in_nav: false,
    show_on_homepage: true,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const upd = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleSubmit = async e => {
    e.preventDefault();
    if (!form.display_name.trim()) { setError('Name required'); return; }
    setSaving(true); setError('');
    try {
      await onSave({ ...form, business_id: businessId, sort_order: parseInt(form.sort_order) || 999 });
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

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div className="bg-white w-full sm:max-w-lg max-h-[92vh] overflow-y-auto">
        <div className="p-6">
          <h2 className="font-serif text-xl text-[#2C2420] mb-5">{initial ? 'Edit Collection' : 'New Collection'}</h2>
          {error && <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 mb-4">{error}</div>}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label htmlFor="col-name">Name *</Label>
              <input id="col-name" type="text" value={form.display_name}
                onChange={e => upd('display_name', e.target.value)}
                placeholder="Gifting, Festive, Corporate..."
                className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#4A3B32]"
                data-testid="col-name-input" />
              {form.display_name && (
                <p className="text-xs text-[#786A60] mt-1">
                  ID: <code className="text-[#4A3B32]">
                    {form.display_name.toLowerCase().replace(/[^a-z0-9]+/g,'_').replace(/^_+|_+$/g,'')}
                  </code>
                </p>
              )}
            </div>

            <div>
              <Label htmlFor="col-desc">Description</Label>
              <textarea id="col-desc" value={form.description}
                onChange={e => upd('description', e.target.value)}
                rows={2} placeholder="Your search for the perfect gift ends here..."
                className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#4A3B32] resize-none"
                data-testid="col-desc-input" />
            </div>

            <div>
              <Label htmlFor="col-banner">Banner Image URL</Label>
              <input id="col-banner" type="url" value={form.banner_image_url}
                onChange={e => upd('banner_image_url', e.target.value)} placeholder="https://..."
                className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#4A3B32]"
                data-testid="col-banner-input" />
            </div>

            <div>
              <Label htmlFor="col-illus">Illustration URL</Label>
              <input id="col-illus" type="url" value={form.illustration_url}
                onChange={e => upd('illustration_url', e.target.value)} placeholder="https://..."
                className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#4A3B32]"
                data-testid="col-illus-input" />
            </div>

            <div>
              <Label htmlFor="col-order">Sort Order</Label>
              <input id="col-order" type="number" value={form.sort_order}
                onChange={e => upd('sort_order', e.target.value)}
                className="w-32 border border-[#E8E0D5] px-3 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#4A3B32]"
                data-testid="col-order-input" />
            </div>

            <div className="flex flex-col gap-3">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.show_in_nav}
                  onChange={e => upd('show_in_nav', e.target.checked)}
                  className="w-4 h-4 accent-[#4A3B32]" data-testid="col-nav-cb" />
                <span className="text-sm text-[#2C2420]">Show in navbar</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.show_on_homepage}
                  onChange={e => upd('show_on_homepage', e.target.checked)}
                  className="w-4 h-4 accent-[#4A3B32]" data-testid="col-homepage-cb" />
                <span className="text-sm text-[#2C2420]">Show on homepage tiles</span>
              </label>
            </div>

            <div className="flex gap-3 pt-2">
              <button type="submit" disabled={saving}
                className="flex-1 bg-[#4A3B32] text-white py-3 text-sm font-semibold hover:bg-[#332822] disabled:opacity-60"
                data-testid="col-save-btn">
                {saving ? 'Saving...' : (initial ? 'Update' : 'Create Collection')}
              </button>
              <button type="button" onClick={onCancel}
                className="px-6 py-3 text-sm text-[#786A60] border border-[#E8E0D5] hover:bg-[#FAF8F5]"
                data-testid="col-cancel-btn">
                Cancel
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

const CollectionManager = () => {
  const { selectedBusiness } = useBusiness();
  const businessId = selectedBusiness?.business_id;

  const [collections, setCollections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingCol, setEditingCol] = useState(null);

  const fetch = async () => {
    if (!businessId) return;
    try {
      const r = await apiClient.get(`/admin/collections/${businessId}`);
      setCollections(r.data.collections || []);
    } finally { setLoading(false); }
  };

  useEffect(() => { fetch(); }, [businessId]);

  const handleCreate = async data => {
    await apiClient.post('/admin/collections', data);
    await fetch();
    setShowForm(false);
  };

  const handleUpdate = async data => {
    const { collection_id, business_id, ...updates } = data;
    await apiClient.put(`/admin/collections/${businessId}/${editingCol.collection_id}`, updates);
    await fetch();
    setEditingCol(null);
  };

  const handleDelete = async col => {
    if (!window.confirm(`Deactivate "${col.display_name}"?`)) return;
    await apiClient.delete(`/admin/collections/${businessId}/${col.collection_id}`);
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
      <main className="flex-1 py-6" data-testid="collection-manager">
        <div className="max-w-4xl mx-auto px-4 md:px-8">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <div>
              <h1 className="text-2xl font-black tracking-tight text-[#2C2420] uppercase">Collections</h1>
              <p className="text-sm text-[#786A60] mt-1">{selectedBusiness?.business_name}</p>
            </div>
            <button onClick={() => setShowForm(true)}
              className="flex items-center gap-2 bg-[#4A3B32] text-white px-5 py-3 text-sm font-semibold hover:bg-[#332822] self-start"
              data-testid="add-collection-btn">
              <Plus size={16} />
              New Collection
            </button>
          </div>

          <p className="text-xs text-[#786A60] mb-4">
            ℹ️ Tag products to collections from the Product Manager. Collections are filter views — products aren't stored here.
          </p>

          <div className="bg-white border border-[#E8E0D5]">
            {collections.length === 0 ? (
              <div className="text-center py-16">
                <p className="text-[#786A60] mb-2">No collections yet.</p>
                <button onClick={() => setShowForm(true)} className="text-sm text-[#4A3B32] underline">
                  Create Gifting, Festive...
                </button>
              </div>
            ) : (
              collections.map(col => (
                <div key={col.collection_id}
                  className={`p-4 border-b border-[#E8E0D5] last:border-0 ${!col.is_active ? 'opacity-50' : ''}`}
                  data-testid={`col-row-${col.collection_id}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3 min-w-0">
                      {col.banner_image_url && (
                        <img src={col.banner_image_url} alt={col.display_name}
                          className="w-12 h-12 object-cover flex-shrink-0" />
                      )}
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-[#2C2420]">{col.display_name}</p>
                        <code className="text-[11px] text-[#786A60]">{col.collection_id}</code>
                        {col.description && <p className="text-xs text-[#786A60] line-clamp-1">{col.description}</p>}
                        <div className="flex gap-2 mt-1 flex-wrap">
                          {col.show_in_nav && (
                            <span className="text-[10px] bg-[#FAF8F5] border border-[#E8E0D5] text-[#786A60] px-1.5 py-0.5">In Nav</span>
                          )}
                          {col.show_on_homepage && (
                            <span className="text-[10px] bg-[#FAF8F5] border border-[#E8E0D5] text-[#786A60] px-1.5 py-0.5">Homepage</span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-1 flex-shrink-0">
                      <Link to={`/business/${businessId}/collections/${col.collection_id}`}
                        target="_blank" rel="noopener noreferrer"
                        className="p-2 text-[#786A60] hover:text-[#4A3B32] border border-[#E8E0D5]"
                        aria-label="Preview">
                        ↗
                      </Link>
                      <button onClick={() => setEditingCol(col)}
                        className="p-2 text-[#786A60] hover:text-[#4A3B32] border border-[#E8E0D5]"
                        aria-label="Edit" data-testid={`edit-col-${col.collection_id}`}>
                        <Edit2 size={14} />
                      </button>
                      <button onClick={() => handleDelete(col)}
                        className="p-2 text-[#786A60] hover:text-red-500 border border-[#E8E0D5]"
                        aria-label="Delete" data-testid={`delete-col-${col.collection_id}`}>
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

      {showForm && <CollectionForm businessId={businessId} onSave={handleCreate} onCancel={() => setShowForm(false)} />}
      {editingCol && <CollectionForm initial={editingCol} businessId={businessId} onSave={handleUpdate} onCancel={() => setEditingCol(null)} />}
    </div>
  );
};

export default CollectionManager;
