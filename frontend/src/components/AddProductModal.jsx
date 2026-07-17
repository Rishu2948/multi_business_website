/**
 * AddProductModal — upgraded for Session 4
 * Supports: is_veg, is_featured, collection_tags, allergens, addons, sort_order.
 * Category dropdown pulls from GET /api/categories/:businessId (API-driven).
 * Collections multi-select from GET /api/collections/:businessId.
 */

import { useState, useEffect } from 'react';
import apiClient from '../utils/api';
import { toast } from 'sonner';
import { X, Plus, Trash2 } from 'lucide-react';

const ALLERGEN_OPTIONS = ['Eggs', 'Wheat', 'Dairy', 'Soy', 'Nuts', 'Gluten', 'Sesame'];

const Label = ({ children, htmlFor }) => (
  <label htmlFor={htmlFor}
    className="block text-xs font-semibold uppercase tracking-wide text-[#786A60] mb-1">
    {children}
  </label>
);

const Input = ({ id, type = 'text', value, onChange, placeholder, required, testId, ...rest }) => (
  <input
    id={id} type={type} value={value ?? ''} onChange={onChange}
    placeholder={placeholder} required={required}
    className="w-full border border-border px-3 py-2.5 text-sm text-primary
               focus:ring-1 focus:ring-accent focus:border-accent outline-none bg-white"
    data-testid={testId}
    {...rest}
  />
);

// Inline addon group builder
const AddonGroupBuilder = ({ addons, onChange }) => {
  const addGroup = () => {
    onChange([...addons, {
      group_id: `grp_${Date.now()}`,
      group_name: '',
      type: 'optional',
      min_select: 0,
      max_select: 1,
      display_label: '',
      items: [],
    }]);
  };

  const removeGroup = (idx) => onChange(addons.filter((_, i) => i !== idx));

  const updateGroup = (idx, field, value) => {
    const updated = [...addons];
    updated[idx] = { ...updated[idx], [field]: value };
    onChange(updated);
  };

  const addItem = (groupIdx) => {
    const updated = [...addons];
    updated[groupIdx].items = [...(updated[groupIdx].items || []), {
      addon_item_id: `item_${Date.now()}`,
      name: '', price: 0, is_veg: null, is_available: true,
    }];
    onChange(updated);
  };

  const removeItem = (groupIdx, itemIdx) => {
    const updated = [...addons];
    updated[groupIdx].items = updated[groupIdx].items.filter((_, i) => i !== itemIdx);
    onChange(updated);
  };

  const updateItem = (groupIdx, itemIdx, field, value) => {
    const updated = [...addons];
    updated[groupIdx].items[itemIdx] = { ...updated[groupIdx].items[itemIdx], [field]: value };
    onChange(updated);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <Label>Add-on Groups</Label>
        <button type="button" onClick={addGroup}
          className="text-xs text-[#4A3B32] underline flex items-center gap-1"
          data-testid="add-addon-group-btn">
          <Plus size={12} /> Add Group
        </button>
      </div>

      {addons.length === 0 && (
        <p className="text-xs text-[#786A60] py-2">No add-on groups yet. Add one for combo selections.</p>
      )}

      {addons.map((group, gi) => (
        <div key={group.group_id} className="border border-[#E8E0D5] p-3 mb-3 bg-[#FAF8F5]">
          <div className="flex items-start gap-2 mb-2">
            <input type="text" value={group.group_name}
              onChange={e => updateGroup(gi, 'group_name', e.target.value)}
              placeholder="Group name (e.g. COLD BEVERAGES)"
              className="flex-1 border border-[#E8E0D5] px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#4A3B32]"
              data-testid={`group-name-${gi}`}
            />
            <select value={group.type} onChange={e => updateGroup(gi, 'type', e.target.value)}
              className="border border-[#E8E0D5] px-2 py-1.5 text-xs bg-white"
              data-testid={`group-type-${gi}`}>
              <option value="optional">Optional</option>
              <option value="required">Required</option>
            </select>
            <input type="number" value={group.max_select}
              onChange={e => updateGroup(gi, 'max_select', parseInt(e.target.value) || 1)}
              className="w-16 border border-[#E8E0D5] px-2 py-1.5 text-xs"
              min="1" title="Max selections"
              data-testid={`group-max-${gi}`}
            />
            <button type="button" onClick={() => removeGroup(gi)}
              className="p-1 text-[#786A60] hover:text-red-500"
              aria-label="Remove group">
              <X size={14} />
            </button>
          </div>

          {/* Items */}
          {(group.items || []).map((item, ii) => (
            <div key={item.addon_item_id} className="flex items-center gap-2 mb-1.5 pl-2">
              <input type="text" value={item.name}
                onChange={e => updateItem(gi, ii, 'name', e.target.value)}
                placeholder="Item name"
                className="flex-1 border border-[#E8E0D5] px-2 py-1 text-xs focus:outline-none"
                data-testid={`item-name-${gi}-${ii}`}
              />
              <span className="text-xs text-[#786A60]">+₹</span>
              <input type="number" value={item.price}
                onChange={e => updateItem(gi, ii, 'price', parseFloat(e.target.value) || 0)}
                className="w-16 border border-[#E8E0D5] px-2 py-1 text-xs"
                min="0" step="0.5"
                data-testid={`item-price-${gi}-${ii}`}
              />
              <select value={item.is_veg === null ? 'null' : String(item.is_veg)}
                onChange={e => updateItem(gi, ii, 'is_veg', e.target.value === 'null' ? null : e.target.value === 'true')}
                className="border border-[#E8E0D5] px-1 py-1 text-xs bg-white">
                <option value="null">—</option>
                <option value="true">Veg</option>
                <option value="false">Non-Veg</option>
              </select>
              <button type="button" onClick={() => removeItem(gi, ii)}
                className="p-1 text-[#786A60] hover:text-red-500" aria-label="Remove item">
                <Trash2 size={12} />
              </button>
            </div>
          ))}

          <button type="button" onClick={() => addItem(gi)}
            className="text-xs text-[#786A60] flex items-center gap-1 mt-1 hover:text-[#4A3B32]"
            data-testid={`add-item-${gi}`}>
            <Plus size={11} /> Add item
          </button>
        </div>
      ))}
    </div>
  );
};

// Main modal
const AddProductModal = ({ isOpen, onClose, businessId, onProductAdded }) => {
  const [loading, setLoading] = useState(false);
  const [categories, setCategories] = useState([]);
  const [collections, setCollections] = useState([]);

  const [form, setForm] = useState({
    product_name: '', description: '', base_price: '',
    category_id: '', sort_order: '', inventory_count: '',
    is_veg: '', is_featured: false, is_bestseller: false,
    collection_tags: [],
    allergens: [],
    addons: [],
    images: [{ url: '', alt: '', is_primary: true }],
    attributes: {},
  });

  useEffect(() => {
    if (!isOpen || !businessId) return;
    apiClient.get(`/categories/${businessId}`)
      .then(r => setCategories(r.data.categories || []))
      .catch(() => {});
    apiClient.get(`/collections/${businessId}`)
      .then(r => setCollections(r.data.collections || []))
      .catch(() => {});
  }, [isOpen, businessId]);

  const upd = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const toggleTag = (tag) =>
    upd('collection_tags', form.collection_tags.includes(tag)
      ? form.collection_tags.filter(t => t !== tag)
      : [...form.collection_tags, tag]);

  const toggleAllergen = (a) =>
    upd('allergens', form.allergens.includes(a)
      ? form.allergens.filter(x => x !== a)
      : [...form.allergens, a]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.product_name || !form.base_price) {
      toast.error('Product name and price are required');
      return;
    }
    setLoading(true);
    try {
      const payload = {
        business_id: businessId,
        product_name: form.product_name,
        description: form.description,
        base_price: parseFloat(form.base_price),
        currency: 'INR',
        category_id: form.category_id || null,
        sort_order: form.sort_order ? parseInt(form.sort_order) : 999,
        images: form.images.filter(i => i.url),
        attributes: form.attributes,
        variants: [],
        inventory_count: parseInt(form.inventory_count) || 0,
        is_veg: form.is_veg === '' ? null : form.is_veg === 'true',
        is_featured: form.is_featured,
        is_bestseller: form.is_bestseller,
        collection_tags: form.collection_tags,
        allergens: form.allergens,
        addons: form.addons,
      };
      await apiClient.post('/products', payload);
      toast.success('Product added successfully');
      onProductAdded();
      onClose();
      setForm({
        product_name: '', description: '', base_price: '',
        category_id: '', sort_order: '', inventory_count: '',
        is_veg: '', is_featured: false, is_bestseller: false,
        collection_tags: [], allergens: [], addons: [],
        images: [{ url: '', alt: '', is_primary: true }],
        attributes: {},
      });
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to add product');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-end sm:items-center justify-center z-50 p-0 sm:p-4"
         data-testid="add-product-modal">
      <div className="bg-white w-full sm:max-w-2xl max-h-[94vh] overflow-y-auto sm:border sm:border-border">
        {/* Header */}
        <div className="sticky top-0 bg-white p-4 sm:p-6 border-b border-border flex items-center justify-between z-10">
          <h2 className="text-xl font-bold text-primary uppercase tracking-tight">Add New Product</h2>
          <button onClick={onClose} className="text-muted hover:text-primary" data-testid="close-modal">
            <X size={22} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 sm:p-6 space-y-5">
          {/* Basic */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="sm:col-span-2">
              <Label htmlFor="pname">Product Name *</Label>
              <Input id="pname" value={form.product_name} onChange={e => upd('product_name', e.target.value)}
                required testId="input-product-name" placeholder="e.g. Overload Brownie [1 Piece]" />
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="pdesc">Description</Label>
              <textarea id="pdesc" value={form.description}
                onChange={e => upd('description', e.target.value)} rows={2}
                className="w-full border border-border px-3 py-2.5 text-sm focus:ring-1 focus:ring-accent outline-none resize-none"
                data-testid="input-description" />
            </div>
            <div>
              <Label htmlFor="pprice">Price ₹ *</Label>
              <Input id="pprice" type="number" value={form.base_price}
                onChange={e => upd('base_price', e.target.value)}
                required min="0" step="0.5" testId="input-price" placeholder="130" />
            </div>
            <div>
              <Label htmlFor="pstock">Initial Stock</Label>
              <Input id="pstock" type="number" value={form.inventory_count}
                onChange={e => upd('inventory_count', e.target.value)}
                min="0" testId="input-stock" placeholder="50" />
            </div>
          </div>

          {/* Category + Sort */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <Label htmlFor="pcat">Category</Label>
              <select id="pcat" value={form.category_id}
                onChange={e => upd('category_id', e.target.value)}
                className="w-full border border-border px-3 py-2.5 text-sm bg-white focus:ring-1 focus:ring-accent outline-none"
                data-testid="input-category">
                <option value="">— Select category —</option>
                {categories.map(c => (
                  <option key={c.category_id} value={c.category_id}>{c.display_name}</option>
                ))}
              </select>
            </div>
            <div>
              <Label htmlFor="psort">Sort Order (within category)</Label>
              <Input id="psort" type="number" value={form.sort_order}
                onChange={e => upd('sort_order', e.target.value)}
                min="0" testId="input-sort-order" placeholder="999 = last" />
            </div>
          </div>

          {/* Image */}
          <div>
            <Label htmlFor="pimg">Image URL</Label>
            <Input id="pimg" type="url" value={form.images[0].url}
              onChange={e => {
                const imgs = [...form.images];
                imgs[0].url = e.target.value;
                upd('images', imgs);
              }}
              placeholder="https://..." testId="input-image-url" />
          </div>

          {/* Veg + toggles */}
          <div>
            <Label htmlFor="pveg">Veg / Non-Veg</Label>
            <select id="pveg" value={form.is_veg}
              onChange={e => upd('is_veg', e.target.value)}
              className="w-full border border-border px-3 py-2.5 text-sm bg-white focus:ring-1 focus:ring-accent outline-none"
              data-testid="input-is-veg">
              <option value="">— Not specified —</option>
              <option value="true">Vegetarian</option>
              <option value="false">Non-Vegetarian</option>
            </select>
          </div>

          <div className="flex flex-wrap gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={form.is_featured}
                onChange={e => upd('is_featured', e.target.checked)}
                className="w-4 h-4 accent-[#4A3B32]" data-testid="input-is-featured" />
              <span className="text-sm text-primary">Mark as Featured</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={form.is_bestseller}
                onChange={e => upd('is_bestseller', e.target.checked)}
                className="w-4 h-4 accent-[#4A3B32]" data-testid="input-is-bestseller" />
              <span className="text-sm text-primary">Mark as Best Seller</span>
            </label>
          </div>

          {/* Collection tags */}
          {collections.length > 0 && (
            <div>
              <Label>Collection Tags</Label>
              <div className="flex flex-wrap gap-2">
                {collections.map(col => {
                  const active = form.collection_tags.includes(col.collection_id);
                  return (
                    <button key={col.collection_id} type="button" onClick={() => toggleTag(col.collection_id)}
                      className={`px-3 py-1.5 text-xs font-medium border transition-colors
                        ${active ? 'bg-[#4A3B32] text-white border-[#4A3B32]' : 'bg-white text-[#786A60] border-[#E8E0D5] hover:border-[#4A3B32]'}`}
                      data-testid={`tag-${col.collection_id}`}>
                      {col.display_name}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Allergens */}
          <div>
            <Label>Allergens</Label>
            <div className="flex flex-wrap gap-2">
              {ALLERGEN_OPTIONS.map(a => {
                const active = form.allergens.includes(a);
                return (
                  <button key={a} type="button" onClick={() => toggleAllergen(a)}
                    className={`px-3 py-1.5 text-xs font-medium border transition-colors
                      ${active ? 'bg-red-100 text-red-700 border-red-300' : 'bg-white text-[#786A60] border-[#E8E0D5] hover:border-red-300'}`}
                    data-testid={`allergen-${a.toLowerCase()}`}>
                    {a}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Add-ons */}
          <AddonGroupBuilder addons={form.addons} onChange={v => upd('addons', v)} />

          {/* Actions */}
          <div className="flex gap-3 pt-4 border-t border-border">
            <button type="button" onClick={onClose}
              className="flex-1 border border-border py-3 text-sm font-semibold text-[#786A60] hover:bg-[#FAF8F5]"
              data-testid="cancel-button">
              Cancel
            </button>
            <button type="submit" disabled={loading}
              className="flex-1 bg-[#4A3B32] text-white py-3 text-sm font-semibold hover:bg-[#332822] disabled:opacity-60"
              data-testid="submit-button">
              {loading ? 'Adding...' : 'Add Product'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AddProductModal;
