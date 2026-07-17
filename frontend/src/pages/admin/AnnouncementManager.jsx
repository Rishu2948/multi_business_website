/**
 * AnnouncementManager — Admin page
 * Create / edit / delete announcement bar messages.
 * Includes a live preview of how the bar will look.
 */

import { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, Eye, EyeOff } from 'lucide-react';
import Navbar from '../../components/common/Navbar';
import { useBusiness } from '../../context/BusinessContext';
import apiClient from '../../utils/api';

const Preview = ({ form }) => (
  <div
    style={{ backgroundColor: form.bg_color || '#4A3B32', color: form.text_color || '#FAF8F5' }}
    className="text-xs py-2 px-4 text-center rounded"
    aria-label="Preview"
  >
    {form.message || 'Your announcement message will appear here'}
    {form.link_text && (
      <span className="underline ml-1 font-semibold">{form.link_text}</span>
    )}
    <span className="ml-2 opacity-60">×</span>
  </div>
);

const AnnouncementForm = ({ initial, onSave, onCancel }) => {
  const [form, setForm] = useState(initial || {
    message: '',
    link_url: '',
    link_text: '',
    bg_color: '#4A3B32',
    text_color: '#FAF8F5',
    priority: 0,
    valid_from: '',
    valid_until: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const upd = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleSubmit = async e => {
    e.preventDefault();
    if (!form.message.trim()) { setError('Message required'); return; }
    setSaving(true); setError('');
    try {
      await onSave({
        ...form,
        priority: parseInt(form.priority) || 0,
        valid_from: form.valid_from ? new Date(form.valid_from).toISOString() : null,
        valid_until: form.valid_until ? new Date(form.valid_until).toISOString() : null,
      });
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
          <h2 className="font-serif text-xl text-[#2C2420] mb-4">
            {initial ? 'Edit Announcement' : 'New Announcement'}
          </h2>

          {error && <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 mb-4">{error}</div>}

          {/* Live preview */}
          <div className="mb-4">
            <p className="text-xs text-[#786A60] mb-2 uppercase tracking-wide font-semibold">Preview</p>
            <Preview form={form} />
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label htmlFor="ann-msg">Message *</Label>
              <input id="ann-msg" type="text" value={form.message}
                onChange={e => upd('message', e.target.value)}
                placeholder="Upto Rs. 200 OFF on the First Order. T&C apply."
                className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#4A3B32]"
                data-testid="ann-message-input" />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="ann-link-url">Link URL (optional)</Label>
                <input id="ann-link-url" type="url" value={form.link_url}
                  onChange={e => upd('link_url', e.target.value)}
                  placeholder="https://..."
                  className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#4A3B32]"
                  data-testid="ann-link-url-input" />
              </div>
              <div>
                <Label htmlFor="ann-link-text">Link Text</Label>
                <input id="ann-link-text" type="text" value={form.link_text}
                  onChange={e => upd('link_text', e.target.value)}
                  placeholder="Shop Now"
                  className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#4A3B32]"
                  data-testid="ann-link-text-input" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="ann-bg">Background Color</Label>
                <div className="flex gap-2 items-center">
                  <input type="color" value={form.bg_color} onChange={e => upd('bg_color', e.target.value)}
                    className="w-10 h-10 border border-[#E8E0D5] cursor-pointer" data-testid="ann-bg-color" />
                  <input type="text" value={form.bg_color} onChange={e => upd('bg_color', e.target.value)}
                    className="flex-1 border border-[#E8E0D5] px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#4A3B32]" />
                </div>
              </div>
              <div>
                <Label htmlFor="ann-text-color">Text Color</Label>
                <div className="flex gap-2 items-center">
                  <input type="color" value={form.text_color} onChange={e => upd('text_color', e.target.value)}
                    className="w-10 h-10 border border-[#E8E0D5] cursor-pointer" data-testid="ann-text-color" />
                  <input type="text" value={form.text_color} onChange={e => upd('text_color', e.target.value)}
                    className="flex-1 border border-[#E8E0D5] px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#4A3B32]" />
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <Label htmlFor="ann-priority">Priority (higher = shown first)</Label>
                <input id="ann-priority" type="number" value={form.priority}
                  onChange={e => upd('priority', e.target.value)}
                  className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#4A3B32]"
                  data-testid="ann-priority-input" />
              </div>
              <div>
                <Label htmlFor="ann-valid-from">Valid From (optional)</Label>
                <input id="ann-valid-from" type="datetime-local" value={form.valid_from}
                  onChange={e => upd('valid_from', e.target.value)}
                  className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#4A3B32]"
                  data-testid="ann-valid-from-input" />
              </div>
              <div>
                <Label htmlFor="ann-valid-until">Valid Until (optional)</Label>
                <input id="ann-valid-until" type="datetime-local" value={form.valid_until}
                  onChange={e => upd('valid_until', e.target.value)}
                  className="w-full border border-[#E8E0D5] px-3 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#4A3B32]"
                  data-testid="ann-valid-until-input" />
              </div>
            </div>

            <div className="flex gap-3 pt-2">
              <button type="submit" disabled={saving}
                className="flex-1 bg-[#4A3B32] text-white py-3 text-sm font-semibold hover:bg-[#332822] disabled:opacity-60"
                data-testid="ann-save-btn">
                {saving ? 'Saving...' : (initial ? 'Update' : 'Create Announcement')}
              </button>
              <button type="button" onClick={onCancel}
                className="px-6 py-3 text-sm text-[#786A60] border border-[#E8E0D5] hover:bg-[#FAF8F5]"
                data-testid="ann-cancel-btn">
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

const AnnouncementManager = () => {
  const { selectedBusiness } = useBusiness();
  const businessId = selectedBusiness?.business_id;

  const [announcements, setAnnouncements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingAnn, setEditingAnn] = useState(null);

  const fetch = async () => {
    if (!businessId) return;
    try {
      const r = await apiClient.get(`/admin/announcements/${businessId}`);
      setAnnouncements(r.data.announcements || []);
    } finally { setLoading(false); }
  };

  useEffect(() => { fetch(); }, [businessId]);

  const handleCreate = async data => {
    await apiClient.post('/admin/announcements', { ...data, business_id: businessId });
    await fetch();
    setShowForm(false);
  };

  const handleUpdate = async data => {
    const { announcement_id, business_id, ...updates } = data;
    await apiClient.put(`/admin/announcements/${editingAnn.announcement_id}`, updates);
    await fetch();
    setEditingAnn(null);
  };

  const handleToggle = async ann => {
    await apiClient.put(`/admin/announcements/${ann.announcement_id}`, { is_active: !ann.is_active });
    await fetch();
  };

  const handleDelete = async ann => {
    if (!window.confirm('Delete this announcement?')) return;
    await apiClient.delete(`/admin/announcements/${ann.announcement_id}`);
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
      <main className="flex-1 py-6" data-testid="announcement-manager">
        <div className="max-w-4xl mx-auto px-4 md:px-8">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <div>
              <h1 className="text-2xl font-black tracking-tight text-[#2C2420] uppercase">Announcements</h1>
              <p className="text-sm text-[#786A60] mt-1">{selectedBusiness?.business_name}</p>
            </div>
            <button onClick={() => setShowForm(true)}
              className="flex items-center gap-2 bg-[#4A3B32] text-white px-5 py-3 text-sm font-semibold hover:bg-[#332822] self-start"
              data-testid="add-ann-btn">
              <Plus size={16} />
              New Announcement
            </button>
          </div>

          <div className="bg-white border border-[#E8E0D5]">
            {announcements.length === 0 ? (
              <div className="text-center py-16">
                <p className="text-[#786A60] mb-3">No announcements.</p>
                <button onClick={() => setShowForm(true)} className="text-sm text-[#4A3B32] underline">
                  Create your first one
                </button>
              </div>
            ) : (
              announcements.map(ann => (
                <div key={ann.announcement_id}
                  className={`p-4 border-b border-[#E8E0D5] last:border-0 ${!ann.is_active ? 'opacity-60' : ''}`}
                  data-testid={`ann-row-${ann.announcement_id}`}>
                  <Preview form={ann} />
                  <div className="flex items-center justify-between mt-3 gap-2 flex-wrap">
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] font-bold px-1.5 py-0.5
                        ${ann.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                        {ann.is_active ? 'ACTIVE' : 'INACTIVE'}
                      </span>
                      <span className="text-xs text-[#786A60]">Priority: {ann.priority}</span>
                    </div>
                    <div className="flex gap-1">
                      <button onClick={() => handleToggle(ann)}
                        className="p-2 text-[#786A60] hover:text-[#4A3B32] border border-[#E8E0D5]"
                        aria-label={ann.is_active ? 'Deactivate' : 'Activate'}
                        data-testid={`toggle-ann-${ann.announcement_id}`}>
                        {ann.is_active ? <Eye size={14} /> : <EyeOff size={14} />}
                      </button>
                      <button onClick={() => setEditingAnn(ann)}
                        className="p-2 text-[#786A60] hover:text-[#4A3B32] border border-[#E8E0D5]"
                        aria-label="Edit" data-testid={`edit-ann-${ann.announcement_id}`}>
                        <Edit2 size={14} />
                      </button>
                      <button onClick={() => handleDelete(ann)}
                        className="p-2 text-[#786A60] hover:text-red-500 border border-[#E8E0D5]"
                        aria-label="Delete" data-testid={`delete-ann-${ann.announcement_id}`}>
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

      {showForm && <AnnouncementForm onSave={handleCreate} onCancel={() => setShowForm(false)} />}
      {editingAnn && <AnnouncementForm initial={editingAnn} onSave={handleUpdate} onCancel={() => setEditingAnn(null)} />}
    </div>
  );
};

export default AnnouncementManager;
