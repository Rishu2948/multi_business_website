/**
 * ProductManager — Admin page (Session 6)
 * Full product CRUD with inline addon group builder.
 * Category dropdown and collection tags from live API.
 * Mobile: card layout + bottom-sheet form.
 * Desktop: table + side-panel form.
 */

import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Plus, Edit2, Trash2, Search, Filter,
  Package, ChevronDown, ChevronUp, X,
} from 'lucide-react';
import Navbar from '../../components/common/Navbar';
import { useBusiness } from '../../context/BusinessContext';
import apiClient from '../../utils/api';
import { toast } from 'sonner';

const ALLERGEN_OPTIONS = ['Eggs','Wheat','Dairy','Soy','Nuts','Gluten','Sesame'];

// ── Shared helpers ─────────────────────────────────────────────────────────

const Label = ({ children, htmlFor }) => (
  <label htmlFor={htmlFor}
    className="block text-xs font-semibold uppercase tracking-wide text-[#786A60] mb-1">
    {children}
  </label>
);

const Input = ({ id, type = 'text', value, onChange, placeholder, required, testId, ...rest }) => (
  <input id={id} type={type} value={value ?? ''} onChange={onChange}
    placeholder={placeholder} required={required}
    className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm text-[#2C2420]
               focus:ring-1 focus:ring-[#4A3B32] focus:outline-none bg-white"
    data-testid={testId} {...rest} />
);

// ── Addon group builder ────────────────────────────────────────────────────

const AddonGroupBuilder = ({ addons, onChange }) => {
  const addGroup = () => onChange([...addons, {
    group_id: `grp_${Date.now()}`, group_name: '',
    type: 'optional', min_select: 0, max_select: 1,
    display_label: '', items: [],
  }]);

  const removeGroup = idx => onChange(addons.filter((_, i) => i !== idx));
  const upd = (idx, k, v) => {
    const a = [...addons]; a[idx] = { ...a[idx], [k]: v }; onChange(a);
  };
  const addItem = gi => {
    const a = [...addons];
    a[gi].items = [...(a[gi].items || []),
      { addon_item_id: `item_${Date.now()}`, name: '', price: 0, is_veg: null, is_available: true }];
    onChange(a);
  };
  const removeItem = (gi, ii) => {
    const a = [...addons]; a[gi].items = a[gi].items.filter((_, i) => i !== ii); onChange(a);
  };
  const updItem = (gi, ii, k, v) => {
    const a = [...addons]; a[gi].items[ii] = { ...a[gi].items[ii], [k]: v }; onChange(a);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <Label>Add-on Groups</Label>
        <button type="button" onClick={addGroup}
          className="text-xs text-[#4A3B32] underline flex items-center gap-1"
          data-testid="add-addon-group">
          <Plus size={11} /> Add Group
        </button>
      </div>
      {addons.length === 0 && (
        <p className="text-xs text-[#786A60] py-1">
          No add-ons. Add groups for combo / beverage pairings.
        </p>
      )}
      {addons.map((group, gi) => (
        <div key={group.group_id}
          className="border border-[#E8E0D5] p-3 mb-2 bg-[#FAF8F5]">
          <div className="flex gap-2 mb-2">
            <input type="text" value={group.group_name}
              onChange={e => upd(gi, 'group_name', e.target.value)}
              placeholder="Group name (e.g. HOT BEVERAGES)"
              className="flex-1 border border-[#E8E0D5] px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-[#4A3B32]"
              data-testid={`group-name-${gi}`} />
            <select value={group.type} onChange={e => upd(gi, 'type', e.target.value)}
              className="border border-[#E8E0D5] px-2 py-1.5 text-xs bg-white">
              <option value="optional">Optional</option>
              <option value="required">Required</option>
            </select>
            <input type="number" value={group.max_select}
              onChange={e => upd(gi, 'max_select', parseInt(e.target.value) || 1)}
              className="w-14 border border-[#E8E0D5] px-2 py-1.5 text-xs"
              min="1" title="Max select" />
            <button type="button" onClick={() => removeGroup(gi)}
              className="p-1 text-[#786A60] hover:text-red-500">
              <X size={13} />
            </button>
          </div>
          {(group.items || []).map((item, ii) => (
            <div key={item.addon_item_id}
              className="flex items-center gap-2 mb-1.5 pl-2">
              <input type="text" value={item.name}
                onChange={e => updItem(gi, ii, 'name', e.target.value)}
                placeholder="Item name"
                className="flex-1 border border-[#E8E0D5] px-2 py-1 text-xs focus:outline-none" />
              <span className="text-xs text-[#786A60]">+₹</span>
              <input type="number" value={item.price}
                onChange={e => updItem(gi, ii, 'price', parseFloat(e.target.value) || 0)}
                className="w-16 border border-[#E8E0D5] px-2 py-1 text-xs" min="0" step="0.5" />
              <select value={item.is_veg === null ? 'null' : String(item.is_veg)}
                onChange={e => updItem(gi, ii, 'is_veg', e.target.value === 'null' ? null : e.target.value === 'true')}
                className="border border-[#E8E0D5] px-1 py-1 text-xs bg-white">
                <option value="null">—</option>
                <option value="true">Veg</option>
                <option value="false">Non-veg</option>
              </select>
              <button type="button" onClick={() => removeItem(gi, ii)}
                className="p-1 text-[#786A60] hover:text-red-500">
                <Trash2 size={11} />
              </button>
            </div>
          ))}
          <button type="button" onClick={() => addItem(gi)}
            className="text-xs text-[#786A60] flex items-center gap-1 mt-1 hover:text-[#4A3B32]">
            <Plus size={10} /> Add item
          </button>
        </div>
      ))}
    </div>
  );
};

// ── Product form ───────────────────────────────────────────────────────────

const ProductForm = ({ initial, categories, collections, businessId, onSave, onCancel }) => {
  const [form, setForm] = useState(initial || {
    product_name: '', description: '', base_price: '',
    category_id: '', sort_order: '', inventory_count: '',
    is_veg: '', is_featured: false, is_bestseller: false,
    collection_tags: [], allergens: [], addons: [],
    images: [{ url: '', alt: '', is_primary: true }],
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const upd = (k, v) => setForm(f => ({ ...f, [k]: v }));
  const toggleTag = tag => upd('collection_tags',
    form.collection_tags.includes(tag)
      ? form.collection_tags.filter(t => t !== tag)
      : [...form.collection_tags, tag]);
  const toggleAllergen = a => upd('allergens',
    form.allergens.includes(a)
      ? form.allergens.filter(x => x !== a)
      : [...form.allergens, a]);

  const handleSubmit = async e => {
    e.preventDefault();
    if (!form.product_name || !form.base_price) {
      setError('Name and price are required'); return;
    }
    setSaving(true); setError('');
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
        attributes: {},
        variants: [],
        inventory_count: parseInt(form.inventory_count) || 0,
        is_veg: form.is_veg === '' ? null : form.is_veg === 'true',
        is_featured: form.is_featured,
        is_bestseller: form.is_bestseller,
        collection_tags: form.collection_tags,
        allergens: form.allergens,
        addons: form.addons,
      };
      await onSave(payload, form.product_id);
    } catch (err) {
      setError(err.response?.data?.detail || 'Save failed');
    } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div className="bg-white w-full sm:max-w-2xl max-h-[94vh] overflow-y-auto">
        <div className="sticky top-0 bg-white p-4 sm:p-6 border-b border-[#E8E0D5] flex items-center justify-between z-10">
          <h2 className="text-lg font-bold text-[#2C2420] uppercase">
            {initial ? 'Edit Product' : 'New Product'}
          </h2>
          <button onClick={onCancel} className="p-2 text-[#786A60]" aria-label="Close" data-testid="close-form">
            <X size={20} />
          </button>
        </div>

        {error && (
          <div className="mx-4 sm:mx-6 mt-4 bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2" role="alert">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="p-4 sm:p-6 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="sm:col-span-2">
              <Label htmlFor="pname">Product Name *</Label>
              <Input id="pname" value={form.product_name}
                onChange={e => upd('product_name', e.target.value)}
                required placeholder="e.g. Overload Brownie [1 Piece]" testId="pname-input" />
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="pdesc">Description</Label>
              <textarea id="pdesc" value={form.description}
                onChange={e => upd('description', e.target.value)} rows={2}
                className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm focus:ring-1 focus:ring-[#4A3B32] outline-none resize-none"
                data-testid="pdesc-input" />
            </div>
            <div>
              <Label htmlFor="pprice">Price ₹ *</Label>
              <Input id="pprice" type="number" value={form.base_price}
                onChange={e => upd('base_price', e.target.value)}
                required min="0" step="0.5" testId="pprice-input" placeholder="130" />
            </div>
            <div>
              <Label htmlFor="pstock">Initial Stock</Label>
              <Input id="pstock" type="number" value={form.inventory_count}
                onChange={e => upd('inventory_count', e.target.value)}
                min="0" testId="pstock-input" placeholder="50" />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <Label htmlFor="pcat">Category</Label>
              <select id="pcat" value={form.category_id}
                onChange={e => upd('category_id', e.target.value)}
                className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm bg-white focus:ring-1 focus:ring-[#4A3B32] outline-none"
                data-testid="pcat-select">
                <option value="">— Select —</option>
                {categories.map(c => (
                  <option key={c.category_id} value={c.category_id}>{c.display_name}</option>
                ))}
              </select>
            </div>
            <div>
              <Label htmlFor="psort">Sort Order</Label>
              <Input id="psort" type="number" value={form.sort_order}
                onChange={e => upd('sort_order', e.target.value)}
                placeholder="999" testId="psort-input" />
            </div>
          </div>

          <div>
            <Label htmlFor="pimg">Image URL</Label>
            <Input id="pimg" type="url" value={form.images[0]?.url || ''}
              onChange={e => {
                const imgs = [...form.images]; imgs[0] = { ...imgs[0], url: e.target.value };
                upd('images', imgs);
              }}
              placeholder="https://..." testId="pimg-input" />
          </div>

          <div>
            <Label htmlFor="pveg">Veg / Non-Veg</Label>
            <select id="pveg" value={form.is_veg}
              onChange={e => upd('is_veg', e.target.value)}
              className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm bg-white focus:ring-1 focus:ring-[#4A3B32] outline-none"
              data-testid="pveg-select">
              <option value="">— Not specified —</option>
              <option value="true">Vegetarian</option>
              <option value="false">Non-Vegetarian</option>
            </select>
          </div>

          <div className="flex flex-wrap gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={form.is_featured}
                onChange={e => upd('is_featured', e.target.checked)}
                className="w-4 h-4 accent-[#4A3B32]" data-testid="pfeatured-cb" />
              <span className="text-sm text-[#2C2420]">Featured</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={form.is_bestseller}
                onChange={e => upd('is_bestseller', e.target.checked)}
                className="w-4 h-4 accent-[#4A3B32]" data-testid="pbestseller-cb" />
              <span className="text-sm text-[#2C2420]">Best Seller</span>
            </label>
          </div>

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

          <div>
            <Label>Allergens</Label>
            <div className="flex flex-wrap gap-2">
              {ALLERGEN_OPTIONS.map(a => {
                const active = form.allergens.includes(a);
                return (
                  <button key={a} type="button" onClick={() => toggleAllergen(a)}
                    className={`px-3 py-1.5 text-xs font-medium border transition-colors
                      ${active ? 'bg-red-100 text-red-700 border-red-300' : 'bg-white text-[#786A60] border-[#E8E0D5] hover:border-red-200'}`}
                    data-testid={`allergen-${a.toLowerCase()}`}>
                    {a}
                  </button>
                );
              })}
            </div>
          </div>

          <AddonGroupBuilder addons={form.addons} onChange={v => upd('addons', v)} />

          <div className="flex gap-3 pt-4 border-t border-[#E8E0D5]">
            <button type="button" onClick={onCancel}
              className="flex-1 border border-[#E8E0D5] py-3 text-sm font-semibold text-[#786A60] hover:bg-[#FAF8F5]"
              data-testid="cancel-product-btn">Cancel</button>
            <button type="submit" disabled={saving}
              className="flex-1 bg-[#4A3B32] text-white py-3 text-sm font-semibold hover:bg-[#332822] disabled:opacity-60"
              data-testid="save-product-btn">
              {saving ? 'Saving...' : (initial ? 'Update Product' : 'Add Product')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// ── Main page ──────────────────────────────────────────────────────────────

const ProductManager = () => {
  const { selectedBusiness } = useBusiness();
  const businessId = selectedBusiness?.business_id;

  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [collections, setCollections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [search, setSearch] = useState('');
  const [filterCat, setFilterCat] = useState('');
  const [filterStatus, setFilterStatus] = useState('active');

  const fetchAll = useCallback(async () => {
    if (!businessId) return;
    setLoading(true);
    try {
      const params = new URLSearchParams({ business_id: businessId, status: filterStatus, limit: 200 });
      if (filterCat) params.set('category_id', filterCat);
      const [prodRes, catRes, colRes] = await Promise.all([
        apiClient.get(`/products?${params}`),
        apiClient.get(`/admin/categories/${businessId}`),
        apiClient.get(`/admin/collections/${businessId}`),
      ]);
      setProducts(prodRes.data.products || []);
      setCategories(catRes.data.categories || []);
      setCollections(colRes.data.collections || []);
    } catch (err) {
      toast.error('Failed to load products');
    } finally { setLoading(false); }
  }, [businessId, filterCat, filterStatus]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleCreate = async (payload) => {
    await apiClient.post('/products', payload);
    toast.success('Product created');
    await fetchAll();
    setShowForm(false);
  };

  const handleUpdate = async (payload, productId) => {
    await apiClient.put(`/products/${productId}`, payload);
    toast.success('Product updated');
    await fetchAll();
    setEditingProduct(null);
  };

  const handleToggleActive = async (product) => {
    const newStatus = product.status === 'active' ? 'inactive' : 'active';
    await apiClient.put(`/products/${product.product_id}`, { status: newStatus });
    toast.success(`Product ${newStatus}`);
    await fetchAll();
  };

  const handleDelete = async (product) => {
    if (!window.confirm(`Delete "${product.product_name}"?`)) return;
    await apiClient.delete(`/products/${product.product_id}`);
    toast.success('Product deleted');
    await fetchAll();
  };

  const filtered = products.filter(p => {
    if (!search) return true;
    const q = search.toLowerCase();
    return p.product_name?.toLowerCase().includes(q) || p.category_id?.toLowerCase().includes(q);
  });

  const getCatName = catId => categories.find(c => c.category_id === catId)?.display_name || catId;

  if (loading) return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <div className="flex-1 flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-[#4A3B32] border-t-transparent rounded-full animate-spin" />
      </div>
    </div>
  );

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5]">
      <Navbar />
      <main className="flex-1 py-6" data-testid="product-manager">
        <div className="max-w-7xl mx-auto px-4 md:px-8">

          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <div>
              <h1 className="text-2xl font-black tracking-tight text-[#2C2420] uppercase">Product Manager</h1>
              <p className="text-sm text-[#786A60] mt-1">
                {selectedBusiness?.business_name} — {filtered.length} product{filtered.length !== 1 ? 's' : ''}
              </p>
            </div>
            <button onClick={() => setShowForm(true)}
              className="flex items-center gap-2 bg-[#4A3B32] text-white px-5 py-3 text-sm font-semibold hover:bg-[#332822] self-start"
              data-testid="add-product-btn">
              <Plus size={16} /> Add Product
            </button>
          </div>

          {/* Filters */}
          <div className="flex flex-wrap gap-3 mb-5">
            <div className="flex items-center gap-2 border border-[#E8E0D5] bg-white px-3 py-2 flex-1 min-w-[180px]">
              <Search size={14} className="text-[#786A60]" />
              <input type="text" value={search} onChange={e => setSearch(e.target.value)}
                placeholder="Search products..."
                className="text-sm outline-none flex-1 bg-transparent text-[#2C2420]"
                data-testid="product-search" />
            </div>
            <select value={filterCat} onChange={e => setFilterCat(e.target.value)}
              className="border border-[#E8E0D5] bg-white px-3 py-2 text-sm focus:outline-none"
              data-testid="filter-category">
              <option value="">All categories</option>
              {categories.map(c => <option key={c.category_id} value={c.category_id}>{c.display_name}</option>)}
            </select>
            <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
              className="border border-[#E8E0D5] bg-white px-3 py-2 text-sm focus:outline-none"
              data-testid="filter-status">
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>

          {/* Products table */}
          <div className="bg-white border border-[#E8E0D5]">
            {filtered.length === 0 ? (
              <div className="text-center py-16">
                <Package size={36} className="mx-auto text-[#786A60] mb-3" strokeWidth={1.5} />
                <p className="text-[#786A60] text-sm mb-2">No products found</p>
                <button onClick={() => setShowForm(true)} className="text-sm text-[#4A3B32] underline">
                  Add the first one
                </button>
              </div>
            ) : (
              <>
                {/* Desktop header */}
                <div className="hidden md:grid grid-cols-12 gap-2 px-4 py-2 bg-[#FAF8F5] border-b border-[#E8E0D5]
                                text-xs font-bold uppercase tracking-wide text-[#786A60]">
                  <div className="col-span-4">Product</div>
                  <div className="col-span-2">Category</div>
                  <div className="col-span-2 text-right">Price</div>
                  <div className="col-span-2 text-center">Flags</div>
                  <div className="col-span-2 text-right">Actions</div>
                </div>

                {filtered.map(product => (
                  <div key={product.product_id}
                    className={`border-b border-[#E8E0D5] last:border-0 ${product.status !== 'active' ? 'opacity-50' : ''}`}
                    data-testid={`product-row-${product.product_id}`}>

                    {/* Desktop row */}
                    <div className="hidden md:grid grid-cols-12 gap-2 items-center px-4 py-3">
                      <div className="col-span-4 flex items-center gap-3 min-w-0">
                        {product.images?.[0]?.url ? (
                          <img src={product.images[0].url} alt={product.product_name}
                            className="w-10 h-10 object-cover flex-shrink-0" />
                        ) : (
                          <div className="w-10 h-10 bg-[#F3EFEA] flex items-center justify-center flex-shrink-0">
                            <Package size={14} className="text-[#786A60]" />
                          </div>
                        )}
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-[#2C2420] line-clamp-1">{product.product_name}</p>
                          <p className="text-xs text-[#786A60] font-mono">{product.product_id?.slice(0, 14)}</p>
                        </div>
                      </div>
                      <div className="col-span-2">
                        <span className="text-xs text-[#786A60]">{getCatName(product.category_id)}</span>
                      </div>
                      <div className="col-span-2 text-right">
                        <span className="text-sm font-semibold text-[#2C2420]">₹{product.base_price?.toLocaleString()}</span>
                      </div>
                      <div className="col-span-2 flex justify-center gap-1 flex-wrap">
                        {product.is_veg === true && <span className="text-[9px] bg-green-100 text-green-700 px-1 py-0.5 font-bold">VEG</span>}
                        {product.is_veg === false && <span className="text-[9px] bg-red-100 text-red-700 px-1 py-0.5 font-bold">NON-VEG</span>}
                        {product.is_featured && <span className="text-[9px] bg-[#FAF8F5] border border-[#D4A373] text-[#D4A373] px-1 py-0.5 font-bold">★</span>}
                        {product.is_bestseller && <span className="text-[9px] bg-orange-100 text-orange-700 px-1 py-0.5 font-bold">BS</span>}
                      </div>
                      <div className="col-span-2 flex items-center justify-end gap-1">
                        <button onClick={() => handleToggleActive(product)}
                          className={`text-[10px] px-2 py-1 font-bold border transition-colors
                            ${product.status === 'active' ? 'border-green-300 text-green-700 hover:bg-green-50' : 'border-gray-300 text-gray-500 hover:bg-gray-50'}`}
                          data-testid={`toggle-${product.product_id}`}>
                          {product.status === 'active' ? 'Active' : 'Off'}
                        </button>
                        <button onClick={() => setEditingProduct(product)}
                          className="p-2 text-[#786A60] hover:text-[#4A3B32]"
                          aria-label="Edit" data-testid={`edit-${product.product_id}`}>
                          <Edit2 size={13} />
                        </button>
                        <button onClick={() => handleDelete(product)}
                          className="p-2 text-[#786A60] hover:text-red-500"
                          aria-label="Delete" data-testid={`delete-${product.product_id}`}>
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>

                    {/* Mobile card */}
                    <div className="md:hidden p-4">
                      <div className="flex items-start gap-3">
                        {product.images?.[0]?.url ? (
                          <img src={product.images[0].url} alt={product.product_name}
                            className="w-12 h-12 object-cover flex-shrink-0" />
                        ) : (
                          <div className="w-12 h-12 bg-[#F3EFEA] flex items-center justify-center flex-shrink-0">
                            <Package size={16} className="text-[#786A60]" />
                          </div>
                        )}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-semibold text-[#2C2420] line-clamp-1">{product.product_name}</p>
                          <p className="text-xs text-[#786A60]">{getCatName(product.category_id)} · ₹{product.base_price?.toLocaleString()}</p>
                          <div className="flex gap-1 mt-1 flex-wrap">
                            {product.is_veg === true && <span className="text-[9px] bg-green-100 text-green-700 px-1 py-0.5 font-bold">VEG</span>}
                            {product.is_featured && <span className="text-[9px] bg-[#FAF8F5] border border-[#D4A373] text-[#D4A373] px-1 py-0.5 font-bold">★ Featured</span>}
                          </div>
                        </div>
                        <div className="flex gap-1 flex-shrink-0">
                          <button onClick={() => setEditingProduct(product)}
                            className="p-2 text-[#786A60]" aria-label="Edit">
                            <Edit2 size={15} />
                          </button>
                          <button onClick={() => handleDelete(product)}
                            className="p-2 text-[#786A60]" aria-label="Delete">
                            <Trash2 size={15} />
                          </button>
                        </div>
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
              <Link to={`/business/${businessId}/catalog`} target="_blank" rel="noopener noreferrer"
                className="text-sm text-[#4A3B32] underline">
                Preview catalog →
              </Link>
            </div>
          )}
        </div>
      </main>

      {showForm && (
        <ProductForm
          categories={categories} collections={collections} businessId={businessId}
          onSave={handleCreate} onCancel={() => setShowForm(false)}
        />
      )}
      {editingProduct && (
        <ProductForm
          initial={editingProduct}
          categories={categories} collections={collections} businessId={businessId}
          onSave={handleUpdate} onCancel={() => setEditingProduct(null)}
        />
      )}
    </div>
  );
};

export default ProductManager;
