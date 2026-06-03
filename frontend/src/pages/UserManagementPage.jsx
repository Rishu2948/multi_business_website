import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import Navbar from '../components/common/Navbar';
import apiClient from '../utils/api';
import { toast } from 'sonner';
import { ArrowLeft, Search, UserCog } from 'lucide-react';

const GLOBAL_ROLES = ['customer', 'staff', 'delivery_agent', 'business_admin', 'super_admin'];
const BUSINESS_ROLES = ['staff', 'delivery_agent', 'business_admin'];

const UserManagementPage = () => {
  const [users, setUsers] = useState([]);
  const [businesses, setBusinesses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchEmail, setSearchEmail] = useState('');
  const [selectedUser, setSelectedUser] = useState(null);
  const [globalRole, setGlobalRole] = useState('customer');
  const [businessId, setBusinessId] = useState('');
  const [businessRole, setBusinessRole] = useState('staff');

  const fetchUsers = useCallback(async () => {
    try {
      const res = await apiClient.get('/users');
      setUsers(res.data.users || []);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to load users');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const load = async () => {
      try {
        const bizRes = await apiClient.get('/businesses');
        setBusinesses(bizRes.data.businesses || []);
        if (bizRes.data.businesses?.length) {
          setBusinessId(bizRes.data.businesses[0].business_id);
        }
      } catch (e) {
        console.error(e);
      }
      await fetchUsers();
    };
    load();
  }, [fetchUsers]);

  const handleSearch = async () => {
    if (!searchEmail.trim()) {
      fetchUsers();
      return;
    }
    try {
      const res = await apiClient.get(`/users/search?email=${encodeURIComponent(searchEmail)}`);
      setUsers(res.data.users || []);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Search failed');
    }
  };

  const selectUser = (user) => {
    setSelectedUser(user);
    setGlobalRole(user.role || 'customer');
  };

  const saveGlobalRole = async () => {
    if (!selectedUser) return;
    try {
      await apiClient.patch(`/users/${selectedUser.user_id}`, { role: globalRole });
      toast.success('Global role updated');
      fetchUsers();
      setSelectedUser((u) => (u ? { ...u, role: globalRole } : null));
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update role');
    }
  };

  const assignBusinessRole = async () => {
    if (!selectedUser || !businessId) {
      toast.error('Select a user and business');
      return;
    }
    try {
      await apiClient.post(`/users/${selectedUser.user_id}/role`, {
        business_id: businessId,
        role: businessRole,
      });
      toast.success('Business role assigned');
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to assign business role');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col">
        <Navbar />
        <div className="flex-1 flex items-center justify-center">
          <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-surface">
      <Navbar />
      <main className="flex-1 py-8" data-testid="user-management-page">
        <div className="max-w-7xl mx-auto px-8">
          <Link to="/super-admin" className="inline-flex items-center gap-2 text-sm text-muted hover:text-primary mb-6">
            <ArrowLeft size={16} /> Back to dashboard
          </Link>

          <h1 className="text-4xl font-black tracking-tight text-primary uppercase mb-2">USER MANAGEMENT</h1>
          <p className="text-sm text-muted mb-8">Assign global and per-business roles without database access</p>

          <div className="flex gap-2 mb-6">
            <input
              type="email"
              placeholder="Search by email"
              value={searchEmail}
              onChange={(e) => setSearchEmail(e.target.value)}
              className="flex-1 border border-border px-4 py-2 bg-white"
              data-testid="user-search-input"
            />
            <button
              type="button"
              onClick={handleSearch}
              className="px-4 py-2 bg-primary text-white font-bold flex items-center gap-2"
              data-testid="user-search-btn"
            >
              <Search size={18} /> Search
            </button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="bg-white border border-border">
              <div className="p-4 border-b border-border font-bold text-primary">USERS ({users.length})</div>
              <div className="max-h-[480px] overflow-y-auto">
                {users.map((u) => (
                  <button
                    key={u.user_id}
                    type="button"
                    onClick={() => selectUser(u)}
                    className={`w-full text-left p-4 border-b border-border hover:bg-surface transition-colors ${
                      selectedUser?.user_id === u.user_id ? 'bg-surface' : ''
                    }`}
                    data-testid={`user-row-${u.user_id}`}
                  >
                    <p className="font-semibold text-primary">{u.name || u.email}</p>
                    <p className="text-xs text-muted">{u.email}</p>
                    <p className="text-xs mt-1">
                      <span className="font-bold">{u.role}</span>
                      {u.business_access?.length > 0 && (
                        <span className="text-muted"> · {u.business_access.length} business(es)</span>
                      )}
                    </p>
                  </button>
                ))}
              </div>
            </div>

            <div className="bg-white border border-border p-6">
              {selectedUser ? (
                <>
                  <div className="flex items-center gap-3 mb-6">
                    <UserCog className="text-primary" size={28} />
                    <div>
                      <p className="font-bold text-primary">{selectedUser.email}</p>
                      <p className="text-xs text-muted">{selectedUser.user_id}</p>
                    </div>
                  </div>

                  <div className="mb-6">
                    <label className="text-xs font-bold uppercase text-muted block mb-2">Global role</label>
                    <div className="flex gap-2">
                      <select
                        value={globalRole}
                        onChange={(e) => setGlobalRole(e.target.value)}
                        className="flex-1 border border-border px-3 py-2"
                        data-testid="global-role-select"
                      >
                        {GLOBAL_ROLES.map((r) => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
                      <button
                        type="button"
                        onClick={saveGlobalRole}
                        className="px-4 py-2 bg-primary text-white font-bold"
                        data-testid="save-global-role-btn"
                      >
                        Save
                      </button>
                    </div>
                  </div>

                  <div className="mb-4">
                    <label className="text-xs font-bold uppercase text-muted block mb-2">Per-business role</label>
                    <select
                      value={businessId}
                      onChange={(e) => setBusinessId(e.target.value)}
                      className="w-full border border-border px-3 py-2 mb-2"
                    >
                      {businesses.map((b) => (
                        <option key={b.business_id} value={b.business_id}>{b.business_name}</option>
                      ))}
                    </select>
                    <select
                      value={businessRole}
                      onChange={(e) => setBusinessRole(e.target.value)}
                      className="w-full border border-border px-3 py-2 mb-2"
                    >
                      {BUSINESS_ROLES.map((r) => (
                        <option key={r} value={r}>{r}</option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={assignBusinessRole}
                      className="w-full px-4 py-2 border-2 border-primary text-primary font-bold hover:bg-primary hover:text-white transition-colors"
                      data-testid="assign-business-role-btn"
                    >
                      Assign business role
                    </button>
                  </div>

                  {selectedUser.business_access?.length > 0 && (
                    <div>
                      <p className="text-xs font-bold uppercase text-muted mb-2">Current business access</p>
                      <ul className="text-sm space-y-1">
                        {selectedUser.business_access.map((a) => (
                          <li key={a.business_id} className="text-muted">
                            {a.business_id}: <span className="font-semibold text-primary">{a.role}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-muted text-center py-12">Select a user to manage roles</p>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default UserManagementPage;
