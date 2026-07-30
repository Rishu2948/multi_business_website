/**
 * Prime Membership Management Dashboard
 * Allows admins to view and manage Prime memberships for their business.
 * Super admins can view memberships across all businesses.
 */

import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import apiClient from '../../utils/api';
import { Crown, Search, Filter, MoreVertical, CheckCircle, XCircle, AlertTriangle, Calendar, RefreshCw, Building2, BarChart3 } from 'lucide-react';

const PrimeMembershipManager = () => {
  const { businessId } = useParams();
  const { user } = useAuth();

  const [memberships, setMemberships] = useState([]);
  const [businesses, setBusinesses] = useState([]);
  const [selectedBusiness, setSelectedBusiness] = useState(businessId || 'all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedMembership, setSelectedMembership] = useState(null);
  const [showActionMenu, setShowActionMenu] = useState(null);
  const [showGrantModal, setShowGrantModal] = useState(false);
  const [grantUserId, setGrantUserId] = useState('');
  const [grantPlanId, setGrantPlanId] = useState('');
  const [plans, setPlans] = useState([]);

  const isSuperAdmin = user?.role === 'super_admin';

  useEffect(() => {
    if (isSuperAdmin) {
      fetchBusinesses();
    }
    fetchMemberships();
    fetchPlans();
  }, [selectedBusiness, statusFilter]);

  const fetchPlans = async () => {
    if (!selectedBusiness || selectedBusiness === 'all') return;
    try {
      const response = await apiClient.get(`/prime/upgrade-info/${selectedBusiness}`);
      setPlans(response.data.plans || []);
    } catch (err) {
      console.error('Error fetching plans:', err);
    }
  };

  const fetchBusinesses = async () => {
    try {
      const response = await apiClient.get('/businesses');
      setBusinesses(response.data.businesses || []);
    } catch (err) {
      console.error('Error fetching businesses:', err);
    }
  };

  const fetchMemberships = async () => {
    setLoading(true);
    try {
      const params = selectedBusiness === 'all' ? {} : { business_id: selectedBusiness };
      const response = await apiClient.get('/prime/admin/memberships', { params });
      setMemberships(response.data.memberships);
    } catch (err) {
      setError('Failed to load memberships');
      console.error('Error fetching memberships:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleGrantMembership = async (userId, planId) => {
    try {
      await apiClient.post(`/prime/admin/grant/${userId}`, {
        business_id: selectedBusiness,
        plan_id: planId,
      });
      await fetchMemberships();
    } catch (err) {
      setError('Failed to grant membership');
      console.error('Error granting membership:', err);
    }
  };

  const handleRevokeMembership = async (userId, businessId) => {
    if (!confirm('Are you sure you want to revoke this membership?')) return;

    try {
      await apiClient.post(`/prime/admin/revoke/${userId}`, {
        business_id: businessId,
      });
      await fetchMemberships();
    } catch (err) {
      setError('Failed to revoke membership');
      console.error('Error revoking membership:', err);
    }
  };

  const filteredMemberships = memberships.filter(m => {
    const matchesSearch = m.user_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         m.plan_name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || m.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const getStatusBadge = (status) => {
    switch (status) {
      case 'active':
        return (
          <span className="flex items-center gap-1 px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs font-medium">
            <CheckCircle size={12} />
            Active
          </span>
        );
      case 'expired':
        return (
          <span className="flex items-center gap-1 px-2 py-1 bg-red-100 text-red-800 rounded-full text-xs font-medium">
            <XCircle size={12} />
            Expired
          </span>
        );
      case 'cancelled':
        return (
          <span className="flex items-center gap-1 px-2 py-1 bg-gray-100 text-gray-800 rounded-full text-xs font-medium">
            <XCircle size={12} />
            Cancelled
          </span>
        );
      case 'pending_payment':
        return (
          <span className="flex items-center gap-1 px-2 py-1 bg-yellow-100 text-yellow-800 rounded-full text-xs font-medium">
            <AlertTriangle size={12} />
            Pending
          </span>
        );
      case 'in_grace_period':
        return (
          <span className="flex items-center gap-1 px-2 py-1 bg-orange-100 text-orange-800 rounded-full text-xs font-medium">
            <AlertTriangle size={12} />
            Grace Period
          </span>
        );
      default:
        return <span className="px-2 py-1 bg-gray-100 text-gray-800 rounded-full text-xs">{status}</span>;
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-[#4A3B32] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-[#2C2420] mb-1">Prime Memberships</h2>
          <p className="text-[#786A60]">Manage Prime subscriptions for this business</p>
        </div>
        <div className="flex items-center gap-3">
          {selectedBusiness && selectedBusiness !== 'all' && (
            <button
              onClick={() => setShowGrantModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-[#4A3B32] text-white rounded-lg hover:bg-[#332822] transition-colors"
            >
              <Crown size={16} />
              Grant Membership
            </button>
          )}
          {selectedBusiness && selectedBusiness !== 'all' && (
            <button
              onClick={() => window.location.href = `/admin/prime-analytics/${selectedBusiness}`}
              className="flex items-center gap-2 px-4 py-2 border border-[#E8E0D5] rounded-lg text-[#2C2420] hover:bg-[#F3EFEA] transition-colors"
            >
              <BarChart3 size={16} />
              Analytics
            </button>
          )}
          <button
            onClick={fetchMemberships}
            className="flex items-center gap-2 px-4 py-2 border border-[#E8E0D5] rounded-lg text-[#2C2420] hover:bg-[#F3EFEA] transition-colors"
          >
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-800">
          {error}
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="flex-1 relative">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#786A60]" />
          <input
            type="text"
            placeholder="Search by user ID or plan..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-[#E8E0D5] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4A3B32]/20"
          />
        </div>
        {isSuperAdmin && (
          <div className="flex items-center gap-2">
            <Building2 size={18} className="text-[#786A60]" />
            <select
              value={selectedBusiness}
              onChange={(e) => setSelectedBusiness(e.target.value)}
              className="px-4 py-2 border border-[#E8E0D5] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4A3B32]/20"
            >
              <option value="all">All Businesses</option>
              {businesses.map(biz => (
                <option key={biz.business_id} value={biz.business_id}>
                  {biz.name || biz.business_id}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="flex items-center gap-2">
          <Filter size={18} className="text-[#786A60]" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2 border border-[#E8E0D5] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4A3B32]/20"
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="expired">Expired</option>
            <option value="cancelled">Cancelled</option>
            <option value="pending_payment">Pending</option>
            <option value="in_grace_period">Grace Period</option>
          </select>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white border border-[#E8E0D5] rounded-lg p-4">
          <div className="text-2xl font-bold text-[#2C2420]">{memberships.length}</div>
          <div className="text-sm text-[#786A60]">Total Memberships</div>
        </div>
        <div className="bg-white border border-[#E8E0D5] rounded-lg p-4">
          <div className="text-2xl font-bold text-green-600">
            {memberships.filter(m => m.status === 'active').length}
          </div>
          <div className="text-sm text-[#786A60]">Active</div>
        </div>
        <div className="bg-white border border-[#E8E0D5] rounded-lg p-4">
          <div className="text-2xl font-bold text-red-600">
            {memberships.filter(m => m.status === 'expired').length}
          </div>
          <div className="text-sm text-[#786A60]">Expired</div>
        </div>
        <div className="bg-white border border-[#E8E0D5] rounded-lg p-4">
          <div className="text-2xl font-bold text-orange-600">
            {memberships.filter(m => m.status === 'in_grace_period').length}
          </div>
          <div className="text-sm text-[#786A60]">Grace Period</div>
        </div>
      </div>

      {/* Memberships Table */}
      <div className="bg-white border border-[#E8E0D5] rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-[#F3EFEA]">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-semibold text-[#2C2420] uppercase tracking-wider">
                  User ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-[#2C2420] uppercase tracking-wider">
                  Plan
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-[#2C2420] uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-[#2C2420] uppercase tracking-wider">
                  Started
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-[#2C2420] uppercase tracking-wider">
                  Expires
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-[#2C2420] uppercase tracking-wider">
                  Auto-renew
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-[#2C2420] uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E8E0D5]">
              {filteredMemberships.length === 0 ? (
                <tr>
                  <td colSpan="7" className="px-6 py-12 text-center text-[#786A60]">
                    No memberships found
                  </td>
                </tr>
              ) : (
                filteredMemberships.map((membership) => (
                  <tr key={membership.membership_id} className="hover:bg-[#F3EFEA]/50">
                    <td className="px-6 py-4 text-sm text-[#2C2420]">
                      {membership.user_id}
                    </td>
                    <td className="px-6 py-4 text-sm text-[#2C2420]">
                      {membership.plan_name}
                    </td>
                    <td className="px-6 py-4">
                      {getStatusBadge(membership.status)}
                    </td>
                    <td className="px-6 py-4 text-sm text-[#786A60]">
                      {formatDate(membership.started_at)}
                    </td>
                    <td className="px-6 py-4 text-sm text-[#786A60]">
                      {formatDate(membership.expires_at)}
                    </td>
                    <td className="px-6 py-4 text-sm text-[#786A60]">
                      {membership.auto_renew ? 'Yes' : 'No'}
                    </td>
                    <td className="px-6 py-4">
                      <div className="relative">
                        <button
                          onClick={() => setShowActionMenu(showActionMenu === membership.membership_id ? null : membership.membership_id)}
                          className="p-2 hover:bg-[#F3EFEA] rounded-lg"
                        >
                          <MoreVertical size={16} className="text-[#786A60]" />
                        </button>
                        {showActionMenu === membership.membership_id && (
                          <div className="absolute right-0 top-10 bg-white border border-[#E8E0D5] rounded-lg shadow-lg z-10 w-48">
                            <button
                              onClick={() => handleRevokeMembership(membership.user_id, membership.business_id)}
                              className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-[#F3EFEA] rounded-t-lg"
                            >
                              Revoke Membership
                            </button>
                            <button
                              onClick={() => setShowActionMenu(null)}
                              className="w-full px-4 py-2 text-left text-sm text-[#2C2420] hover:bg-[#F3EFEA] rounded-b-lg"
                            >
                              Cancel
                            </button>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Grant Membership Modal */}
      {showGrantModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h3 className="text-xl font-bold text-[#2C2420] mb-4">Grant Prime Membership</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-[#2C2420] mb-1">User ID</label>
                <input
                  type="text"
                  value={grantUserId}
                  onChange={(e) => setGrantUserId(e.target.value)}
                  placeholder="Enter user ID"
                  className="w-full px-4 py-2 border border-[#E8E0D5] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4A3B32]/20"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-[#2C2420] mb-1">Plan</label>
                <select
                  value={grantPlanId}
                  onChange={(e) => setGrantPlanId(e.target.value)}
                  className="w-full px-4 py-2 border border-[#E8E0D5] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4A3B32]/20"
                >
                  <option value="">Select a plan</option>
                  {plans.map(plan => (
                    <option key={plan.plan_id} value={plan.plan_id}>
                      {plan.name} - {plan.currency} {plan.price}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => {
                  setShowGrantModal(false);
                  setGrantUserId('');
                  setGrantPlanId('');
                }}
                className="flex-1 px-4 py-2 border border-[#E8E0D5] rounded-lg text-[#2C2420] hover:bg-[#F3EFEA] transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  if (!grantUserId || !grantPlanId) {
                    setError('Please fill in all fields');
                    return;
                  }
                  await handleGrantMembership(grantUserId, grantPlanId);
                  setShowGrantModal(false);
                  setGrantUserId('');
                  setGrantPlanId('');
                }}
                className="flex-1 px-4 py-2 bg-[#4A3B32] text-white rounded-lg hover:bg-[#332822] transition-colors"
              >
                Grant
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PrimeMembershipManager;
