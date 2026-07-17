/**
 * CategoryManager — Admin page
 * Full CRUD for categories. Adding "Namkeen" is a button click.
 * Changes reflect on the customer sidebar immediately (no redeploy).
 * Mobile: card layout. Desktop: table.
 */

import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Edit2, Trash2, ArrowUp, ArrowDown, Eye, EyeOff, Star } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useBusiness } from '../../context/BusinessContext';
import Navbar from '../../components/common/Navbar';
import apiClient from '../../utils/api';

// ── Form modal ──────────────────────────────────────────────────────────────

const CategoryForm = ({ initial, onSave, onCancel, businessId }) => {
  const [form, setForm] = useState(initial || {
    display_name: '',
    description: '',
    icon_emoji: '',
    image_url: '',
    parent_category_id: '',
    is_featured: false,
    sort_order: 999,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async e => {
    e.preventDefault();
    if (!form.display_name.trim()) { setError('Display name is required'); return; }
    setSaving(true);
    setError('');
    try {
      await onSave({ ...form, business_id: businessId });
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save category');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div className="bg-white w-full sm:max-w-md sm:rounded-none max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <h2 className="font-serif text-xl text-[#2C2420] mb-6">
            {initial ? 'Edit Category' : 'New Category'}
          </h2>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 mb-4" role="alert">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-[#786A60] mb-1"
                     htmlFor="cat-name">
                Display Name *
              </label>
              <input
                id="cat-name"
                type="text"
                value={form.display_name}
                onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))}
                placeholder="e.g. Namkeen, Cakes, Beverages"
                className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm text-[#2C2420]
                           focus:outline-none focus:ring-1 focus:ring-[#4A3B32] bg-white"
                required
                data-testid="cat-name-input"
              />
              {form.display_name && (
                <p className="text-xs text-[#786A60] mt-1">
                  ID will be: <code className="text-[#4A3B32]">
                    {form.display_name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '')}
                  </code>
                </p>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-[#786A60] mb-1"
                     htmlFor="cat-desc">
                Description
              </label>
              <textarea
                id="cat-desc"
                value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                placeholder="Optional subtitle shown below category name"
                rows={2}
                className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm text-[#2C2420]
                           focus:outline-none focus:ring-1 focus:ring-[#4A3B32] bg-white resize-none"
                data-testid="cat-desc-input"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-[#786A60] mb-1"
                       htmlFor="cat-emoji">
                  Icon Emoji
                </label>
                <input
                  id="cat-emoji"
                  type="text"
                  value={form.icon_emoji}
                  onChange={e => setForm(f => ({ ...f, icon_emoji: e.target.value }))}
                  placeholder="🎂"
                  className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm
                             focus:outline-none focus:ring-1 focus:ring-[#4A3B32] bg-white"
                  data-testid="cat-emoji-input"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-[#786A60] mb-1"
                       htmlFor="cat-order">
                  Sort Order
                </label>
                <input
                  id="cat-order"
                  type="number"
                  value={form.sort_order}
                  onChange={e => setForm(f => ({ ...f, sort_order: parseInt(e.target.value) || 999 }))}
                  className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm
                             focus:outline-none focus:ring-1 focus:ring-[#4A3B32] bg-white"
                  data-testid="cat-order-input"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-[#786A60] mb-1"
                     htmlFor="cat-image">
                Category Image URL
              </label>
              <input
                id="cat-image"
                type="url"
                value={form.image_url}
                onChange={e => setForm(f => ({ ...f, image_url: e.target.value }))}
                placeholder="https://..."
                className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm
                           focus:outline-none focus:ring-1 focus:ring-[#4A3B32] bg-white"
                data-testid="cat-image-input"
              />
            </div>

            <div className="flex items-center gap-3">
              <input
                id="cat-featured"
                type="checkbox"
                checked={form.is_featured}
                onChange={e => setForm(f => ({ ...f, is_featured: e.target.checked }))}
                className="w-4 h-4 accent-[#4A3B32]"
                data-testid="cat-featured-checkbox"
              />
              <label htmlFor="cat-featured" className="text-sm text-[#2C2420]">
                Show on homepage tiles (featured)
              </label>
            </div>

            <div className="flex gap-3 pt-2">
              <button
                type="submit"
                disabled={saving}
                className="flex-1 bg-[#4A3B32] text-white py-3 text-sm font-semibold
                           hover:bg-[#332822] disabled:opacity-60 transition-colors"
                data-testid="cat-save-btn"
              >
                {saving ? 'Saving...' : (initial ? 'Update Category' : 'Create Category')}
              </button>
              <button
                type="button"
                onClick={onCancel}
                className="px-6 py-3 text-sm font-semibold text-[#786A60] border border-[#E8E0D5]
                           hover:bg-[#FAF8F5] transition-colors"
                data-testid="cat-cancel-btn"
              >
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

const CategoryManager = () => {
  const { user } = useAuth();
  const { selectedBusiness } = useBusiness();
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingCategory, setEditingCategory] = useState(null);
  const [error, setError] = useState('');

  const businessId = selectedBusiness?.business_id;

  const fetchCategories = useCallback(async () => {
    if (!businessId) return;
    try {
      const res = await apiClient.get(`/admin/categories/${businessId}`);
      setCategories(res.data.categories || []);
    } catch {
      setError('Failed to load categories');
    } finally {
      setLoading(false);
    }
  }, [businessId]);

  useEffect(() => {
    fetchCategories();
  }, [fetchCategories]);

  const handleCreate = async data => {
    await apiClient.post('/admin/categories', data);
    await fetchCategories();
    setShowForm(false);
  };

  const handleUpdate = async data => {
    const { category_id, business_id, ...updates } = data;
    await apiClient.put(`/admin/categories/${business_id}/${editingCategory.category_id}`, updates);
    await fetchCategories();
    setEditingCategory(null);
  };

  const handleToggleActive = async cat => {
    await apiClient.put(
      `/admin/categories/${businessId}/${cat.category_id}`,
      { is_active: !cat.is_active }
    );
    await fetchCategories();
  };

  const handleToggleFeatured = async cat => {
    await apiClient.put(
      `/admin/categories/${businessId}/${cat.category_id}`,
      { is_featured: !cat.is_featured }
    );
    await fetchCategories();
  };

  const handleMove = async (index, direction) => {
    const reordered = [...categories];
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= reordered.length) return;
    [reordered[index], reordered[targetIndex]] = [reordered[targetIndex], reordered[index]];

    const items = reordered.map((cat, i) => ({ category_id: cat.category_id, sort_order: i }));
    await apiClient.put(`/admin/categories/${businessId}/reorder/bulk`, items);
    await fetchCategories();
  };

  const handleDelete = async cat => {
    if (!window.confirm(`Deactivate "${cat.display_name}"? Products won't be deleted.`)) return;
    await apiClient.delete(`/admin/categories/${businessId}/${cat.category_id}`);
    await fetchCategories();
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
      <main className="flex-1 py-6" data-testid="category-manager">
        <div className="max-w-5xl mx-auto px-4 md:px-8">
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <div>
              <h1 className="text-2xl font-black tracking-tight text-[#2C2420] uppercase">
                Category Manager
              </h1>
              <p className="text-sm text-[#786A60] mt-1">
                {selectedBusiness?.business_name} — {categories.length} categories
              </p>
            </div>
            <button
              onClick={() => setShowForm(true)}
              className="flex items-center gap-2 bg-[#4A3B32] text-white px-5 py-3
                         text-sm font-semibold hover:bg-[#332822] transition-colors self-start"
              data-testid="add-category-btn"
            >
              <Plus size={16} />
              Add Category
            </button>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 mb-4" role="alert">
              {error}
            </div>
          )}

          <p className="text-xs text-[#786A60] mb-4">
            ℹ️ Changes reflect on the customer menu sidebar immediately — no redeploy needed.
          </p>

          {/* Category list */}
          <div className="bg-white border border-[#E8E0D5]">
            {categories.length === 0 ? (
              <div className="text-center py-16">
                <p className="text-[#786A60] mb-3">No categories yet.</p>
                <button
                  onClick={() => setShowForm(true)}
                  className="text-sm text-[#4A3B32] underline"
                >
                  Create your first category
                </button>
              </div>
            ) : (
              <>
                {/* Desktop header */}
                <div className="hidden md:grid grid-cols-12 gap-2 px-4 py-2 bg-[#FAF8F5]
                                border-b border-[#E8E0D5] text-xs font-bold uppercase tracking-wide text-[#786A60]">
                  <div className="col-span-1">Order</div>
                  <div className="col-span-4">Category</div>
                  <div className="col-span-2">ID</div>
                  <div className="col-span-2 text-center">Products</div>
                  <div className="col-span-1 text-center">Status</div>
                  <div className="col-span-2 text-right">Actions</div>
                </div>

                {categories.map((cat, index) => (
                  <div
                    key={cat.category_id}
                    className={`border-b border-[#E8E0D5] last:border-0
                      ${!cat.is_active ? 'opacity-50' : ''}`}
                    data-testid={`category-row-${cat.category_id}`}
                  >
                    {/* Desktop row */}
                    <div className="hidden md:grid grid-cols-12 gap-2 items-center px-4 py-3">
                      <div className="col-span-1 flex flex-col gap-0.5">
                        <button onClick={() => handleMove(index, 'up')} disabled={index === 0}
                          className="text-[#786A60] hover:text-[#2C2420] disabled:opacity-30 p-0.5"
                          aria-label="Move up">
                          <ArrowUp size={12} />
                        </button>
                        <button onClick={() => handleMove(index, 'down')} disabled={index === categories.length - 1}
                          className="text-[#786A60] hover:text-[#2C2420] disabled:opacity-30 p-0.5"
                          aria-label="Move down">
                          <ArrowDown size={12} />
                        </button>
                      </div>

                      <div className="col-span-4 flex items-center gap-2">
                        {cat.icon_emoji && <span aria-hidden="true">{cat.icon_emoji}</span>}
                        {cat.image_url && (
                          <img src={cat.image_url} alt="" className="w-7 h-7 object-cover rounded-sm" />
                        )}
                        <div>
                          <p className="text-sm font-medium text-[#2C2420]">{cat.display_name}</p>
                          {cat.description && (
                            <p className="text-xs text-[#786A60] line-clamp-1">{cat.description}</p>
                          )}
                        </div>
                      </div>

                      <div className="col-span-2">
                        <code className="text-xs text-[#786A60] font-mono">{cat.category_id}</code>
                      </div>

                      <div className="col-span-2 text-center">
                        <span className="text-sm text-[#2C2420]">{cat.product_count || 0}</span>
                      </div>

                      <div className="col-span-1 flex items-center justify-center gap-1">
                        <span className={`text-[10px] font-bold px-1.5 py-0.5
                          ${cat.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                          {cat.is_active ? 'ON' : 'OFF'}
                        </span>
                        {cat.is_featured && (
                          <Star size={11} className="text-[#D4A373] fill-[#D4A373]" aria-label="Featured" />
                        )}
                      </div>

                      <div className="col-span-2 flex items-center justify-end gap-1">
                        <button onClick={() => handleToggleFeatured(cat)}
                          className="p-1.5 text-[#786A60] hover:text-[#D4A373]"
                          title={cat.is_featured ? 'Remove from homepage' : 'Show on homepage'}
                          data-testid={`toggle-featured-${cat.category_id}`}>
                          <Star size={14} className={cat.is_featured ? 'fill-[#D4A373] text-[#D4A373]' : ''} />
                        </button>
                        <button onClick={() => handleToggleActive(cat)}
                          className="p-1.5 text-[#786A60] hover:text-[#2C2420]"
                          title={cat.is_active ? 'Deactivate' : 'Activate'}
                          data-testid={`toggle-active-${cat.category_id}`}>
                          {cat.is_active ? <Eye size={14} /> : <EyeOff size={14} />}
                        </button>
                        <button onClick={() => setEditingCategory(cat)}
                          className="p-1.5 text-[#786A60] hover:text-[#4A3B32]"
                          aria-label="Edit category"
                          data-testid={`edit-cat-${cat.category_id}`}>
                          <Edit2 size={14} />
                        </button>
                        <button onClick={() => handleDelete(cat)}
                          className="p-1.5 text-[#786A60] hover:text-red-500"
                          aria-label="Delete category"
                          data-testid={`delete-cat-${cat.category_id}`}>
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>

                    {/* Mobile card */}
                    <div className="md:hidden p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-2 min-w-0">
                          {cat.icon_emoji && <span className="text-xl">{cat.icon_emoji}</span>}
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-[#2C2420]">{cat.display_name}</p>
                            <code className="text-[11px] text-[#786A60]">{cat.category_id}</code>
                            <p className="text-xs text-[#786A60]">{cat.product_count || 0} products</p>
                          </div>
                        </div>
                        <div className="flex gap-1 flex-shrink-0">
                          <button onClick={() => setEditingCategory(cat)}
                            className="p-2 text-[#786A60]" aria-label="Edit">
                            <Edit2 size={16} />
                          </button>
                          <button onClick={() => handleDelete(cat)}
                            className="p-2 text-[#786A60]" aria-label="Delete">
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 mt-2">
                        <span className={`text-[10px] font-bold px-1.5 py-0.5
                          ${cat.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                          {cat.is_active ? 'ACTIVE' : 'INACTIVE'}
                        </span>
                        {cat.is_featured && (
                          <span className="text-[10px] text-[#D4A373] font-bold">★ Featured</span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>

          {/* Preview link */}
          {businessId && (
            <div className="mt-4 text-right">
              <Link
                to={`/business/${businessId}/catalog`}
                className="text-sm text-[#4A3B32] underline"
                target="_blank" rel="noopener noreferrer"
                data-testid="preview-catalog-link"
              >
                Preview customer catalog →
              </Link>
            </div>
          )}
        </div>
      </main>

      {/* Create form */}
      {showForm && (
        <CategoryForm
          businessId={businessId}
          onSave={handleCreate}
          onCancel={() => setShowForm(false)}
        />
      )}

      {/* Edit form */}
      {editingCategory && (
        <CategoryForm
          initial={editingCategory}
          businessId={businessId}
          onSave={handleUpdate}
          onCancel={() => setEditingCategory(null)}
        />
      )}
    </div>
  );
};

export default CategoryManager;
