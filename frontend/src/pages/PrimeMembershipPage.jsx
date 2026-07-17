/**
 * Prime Membership Management Page
 * Allows customers to view and manage their Prime subscriptions.
 */

import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import Navbar from '../components/common/Navbar';
import { useAuth } from '../context/AuthContext';
import apiClient from '../utils/api';
import { Crown, Calendar, CreditCard, AlertTriangle, CheckCircle, XCircle, RefreshCw } from 'lucide-react';

const PrimeMembershipPage = () => {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const businessId = searchParams.get('business_id') || 'whisked_words';

  const [memberships, setMemberships] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    fetchMemberships();
  }, []);

  const fetchMemberships = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get('/prime/my-memberships');
      setMemberships(response.data);
    } catch (err) {
      setError('Failed to load memberships');
      console.error('Error fetching memberships:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async (businessId) => {
    if (!confirm('Are you sure you want to cancel auto-renew? Your membership will remain active until the expiry date.')) {
      return;
    }

    setActionLoading(true);
    try {
      await apiClient.post('/prime/cancel', { business_id });
      await fetchMemberships();
    } catch (err) {
      setError('Failed to cancel membership');
      console.error('Error cancelling membership:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleReactivate = async (businessId) => {
    setActionLoading(true);
    try {
      await apiClient.post('/prime/reactivate', { business_id });
      await fetchMemberships();
    } catch (err) {
      setError('Failed to reactivate membership');
      console.error('Error reactivating membership:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'active':
        return (
          <span className="flex items-center gap-1 px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium">
            <CheckCircle size={14} />
            Active
          </span>
        );
      case 'expired':
        return (
          <span className="flex items-center gap-1 px-3 py-1 bg-red-100 text-red-800 rounded-full text-sm font-medium">
            <XCircle size={14} />
            Expired
          </span>
        );
      case 'cancelled':
        return (
          <span className="flex items-center gap-1 px-3 py-1 bg-gray-100 text-gray-800 rounded-full text-sm font-medium">
            <XCircle size={14} />
            Cancelled
          </span>
        );
      case 'pending_payment':
        return (
          <span className="flex items-center gap-1 px-3 py-1 bg-yellow-100 text-yellow-800 rounded-full text-sm font-medium">
            <AlertTriangle size={14} />
            Pending Payment
          </span>
        );
      case 'in_grace_period':
        return (
          <span className="flex items-center gap-1 px-3 py-1 bg-orange-100 text-orange-800 rounded-full text-sm font-medium">
            <AlertTriangle size={14} />
            Grace Period
          </span>
        );
      default:
        return <span className="px-3 py-1 bg-gray-100 text-gray-800 rounded-full text-sm font-medium">{status}</span>;
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

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5]">
      <Navbar />
      <main className="flex-1 py-8">
        <div className="max-w-4xl mx-auto px-4">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-[#2C2420] mb-2">Prime Memberships</h1>
            <p className="text-[#786A60]">Manage your Prime subscriptions across businesses</p>
          </div>

          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800">
              {error}
            </div>
          )}

          {memberships.length === 0 ? (
            <div className="text-center py-12 bg-white border border-[#E8E0D5] rounded-lg">
              <Crown size={48} className="mx-auto text-[#786A60] mb-4" />
              <h3 className="text-lg font-semibold text-[#2C2420] mb-2">No Prime Memberships</h3>
              <p className="text-[#786A60] mb-4">You don't have any Prime subscriptions yet.</p>
              <button
                onClick={() => navigate(`/prime?business_id=${businessId}`)}
                className="bg-[#4A3B32] text-white px-6 py-2 rounded-lg font-medium hover:bg-[#3A2B22] transition-colors"
              >
                View Prime Plans
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {memberships.map((membership) => (
                <div
                  key={membership.membership_id}
                  className="bg-white border border-[#E8E0D5] rounded-lg p-6 hover:shadow-md transition-shadow"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h3 className="text-xl font-semibold text-[#2C2420] mb-1">
                        {membership.plan_name}
                      </h3>
                      <p className="text-sm text-[#786A60] capitalize">
                        {membership.business_id.replace('_', ' ')}
                      </p>
                    </div>
                    {getStatusBadge(membership.status)}
                  </div>

                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div className="flex items-center gap-2 text-sm">
                      <Calendar size={16} className="text-[#786A60]" />
                      <span className="text-[#786A60]">Started:</span>
                      <span className="text-[#2C2420] font-medium">{formatDate(membership.started_at)}</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      <Calendar size={16} className="text-[#786A60]" />
                      <span className="text-[#786A60]">Expires:</span>
                      <span className="text-[#2C2420] font-medium">{formatDate(membership.expires_at)}</span>
                    </div>
                  </div>

                  <div className="mb-4">
                    <div className="flex items-center gap-2 text-sm mb-2">
                      <Crown size={16} className="text-[#786A60]" />
                      <span className="text-[#786A60]">Enabled Features:</span>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {membership.enabled_features.map((feature) => (
                        <span
                          key={feature}
                          className="px-2 py-1 bg-[#F3EFEA] text-[#4A3B32] rounded text-xs font-medium"
                        >
                          {feature.replace('_', ' ')}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-4 border-t border-[#E8E0D5]">
                    <div className="flex items-center gap-2 text-sm">
                      <CreditCard size={16} className="text-[#786A60]" />
                      <span className="text-[#786A60]">
                        Auto-renew: {membership.auto_renew ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>

                    {membership.status === 'active' && membership.auto_renew && (
                      <button
                        onClick={() => handleCancel(membership.business_id)}
                        disabled={actionLoading}
                        className="text-sm text-[#786A60] hover:text-[#2C2420] font-medium disabled:opacity-50"
                      >
                        Cancel Auto-renew
                      </button>
                    )}

                    {membership.status === 'active' && !membership.auto_renew && (
                      <button
                        onClick={() => handleReactivate(membership.business_id)}
                        disabled={actionLoading}
                        className="text-sm text-[#4A3B32] hover:text-[#2C2420] font-medium disabled:opacity-50 flex items-center gap-1"
                      >
                        <RefreshCw size={14} />
                        Enable Auto-renew
                      </button>
                    )}

                    {membership.status === 'expired' && (
                      <button
                        onClick={() => navigate(`/prime?business_id=${membership.business_id}`)}
                        className="text-sm bg-[#4A3B32] text-white px-4 py-2 rounded font-medium hover:bg-[#3A2B22] transition-colors"
                      >
                        Subscribe Again
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default PrimeMembershipPage;
