/**
 * PrimeUpgradePage — Customer-facing subscription page
 * Display available Prime plans and handle subscription flow.
 */

import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import BakeryNavbar from '../components/common/BakeryNavbar';
import { useBusiness } from '../context/BusinessContext';
import { useAuth } from '../context/AuthContext';
import apiClient from '../utils/api';
import { Crown, Check, Loader2, AlertCircle } from 'lucide-react';

const PrimeUpgradePage = () => {
  const [searchParams] = useSearchParams();
  const { selectedBusiness } = useBusiness();
  const { user } = useAuth();
  
  const businessId = searchParams.get('business_id') || selectedBusiness?.business_id || 'whisked_words';
  
  const [config, setConfig] = useState(null);
  const [membership, setMembership] = useState(null);
  const [loading, setLoading] = useState(true);
  const [subscribing, setSubscribing] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchUpgradeInfo();
  }, [businessId, user]);

  const fetchUpgradeInfo = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await apiClient.get(`/prime/upgrade-info/${businessId}`);
      setConfig(response.data);
      setMembership(response.data.membership || null);
    } catch (err) {
      if (err.response?.status === 404) {
        setError('Prime is not available for this business yet.');
      } else {
        setError('Failed to load Prime information.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSubscribe = async (planId) => {
    if (!user) {
      // Redirect to login with return URL
      window.location.href = `/login?redirect=/prime?business_id=${businessId}`;
      return;
    }

    setSubscribing(true);
    setError('');
    try {
      // For MVP: Activate membership immediately (no real payment)
      const response = await apiClient.post('/prime/subscribe', {
        business_id: businessId,
        plan_id: planId,
      });

      // For MVP, activate the membership directly
      // In production, this would redirect to payment gateway
      await fetchUpgradeInfo();
    } catch (err) {
      if (err.response?.status === 409) {
        setError('You already have an active Prime membership.');
      } else {
        setError(err.response?.data?.detail || 'Failed to start subscription.');
      }
    } finally {
      setSubscribing(false);
    }
  };

  const handleCancel = async () => {
    if (!confirm('Are you sure you want to cancel auto-renew? You will retain access until your membership expires.')) {
      return;
    }

    try {
      await apiClient.post('/prime/cancel', null, { params: { business_id: businessId } });
      await fetchUpgradeInfo();
    } catch (err) {
      setError('Failed to cancel membership.');
    }
  };

  const handleReactivate = async () => {
    try {
      await apiClient.post('/prime/reactivate', null, { params: { business_id: businessId } });
      await fetchUpgradeInfo();
    } catch (err) {
      setError('Failed to reactivate membership.');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col">
        <BakeryNavbar businessId={businessId} />
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-[#4A3B32]" />
        </div>
      </div>
    );
  }

  if (error && !config) {
    return (
      <div className="min-h-screen flex flex-col">
        <BakeryNavbar businessId={businessId} />
        <main className="flex-1 flex items-center justify-center px-4">
          <div className="max-w-md w-full text-center">
            <AlertCircle className="w-16 h-16 text-[#786A60] mx-auto mb-4" />
            <h1 className="text-2xl font-bold text-[#2C2420] mb-2">Prime Not Available</h1>
            <p className="text-[#786A60]">{error}</p>
          </div>
        </main>
      </div>
    );
  }

  if (!config?.enabled) {
    return (
      <div className="min-h-screen flex flex-col">
        <BakeryNavbar businessId={businessId} />
        <main className="flex-1 flex items-center justify-center px-4">
          <div className="max-w-md w-full text-center">
            <Crown className="w-16 h-16 text-[#786A60] mx-auto mb-4" />
            <h1 className="text-2xl font-bold text-[#2C2420] mb-2">Prime Coming Soon</h1>
            <p className="text-[#786A60]">Prime membership is not yet available for this business.</p>
          </div>
        </main>
      </div>
    );
  }

  // Show membership status if user has any membership
  if (membership) {
    const expiryDate = new Date(membership.expires_at).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });

    const isActive = membership.status === 'active';
    const isExpired = membership.status === 'expired';
    const isCancelled = membership.status === 'cancelled';

    let statusBadge, statusMessage, statusColor;

    if (isActive) {
      statusBadge = 'Active';
      statusMessage = `Your membership is active until ${expiryDate}`;
      statusColor = 'green';
    } else if (isExpired) {
      statusBadge = 'Expired';
      statusMessage = `Your membership expired on ${expiryDate}`;
      statusColor = 'red';
    } else if (isCancelled) {
      statusBadge = 'Cancelled';
      statusMessage = `Your membership was cancelled on ${expiryDate}`;
      statusColor = 'gray';
    } else {
      statusBadge = membership.status;
      statusMessage = `Membership status: ${membership.status}`;
      statusColor = 'yellow';
    }

    return (
      <div className="min-h-screen flex flex-col bg-[#FAF8F5]">
        <BakeryNavbar businessId={businessId} />
        <main className="flex-1 py-8">
          <div className="max-w-2xl mx-auto px-4">
            <div className="bg-white border border-[#E8E0D5] rounded-lg p-8">
              <div className="text-center mb-6">
                <Crown className="w-16 h-16 text-[#4A3B32] mx-auto mb-4" />
                <h1 className="text-3xl font-bold text-[#2C2420] mb-2">{config.display_name}</h1>
                <p className="text-[#786A60]">{config.tagline}</p>
              </div>

              <div className={`bg-${statusColor}-50 border border-${statusColor}-200 rounded-lg p-6 mb-6`}>
                <h2 className={`text-lg font-semibold text-${statusColor}-800 mb-2`}>
                  {statusBadge} Membership
                </h2>
                <p className={`text-${statusColor}-700 mb-4`}>
                  {statusMessage}
                </p>
                <div className="flex items-center gap-2 text-sm text-[#786A60] mb-2">
                  <span className="font-medium">Plan:</span>
                  <span>{membership.plan_name}</span>
                </div>
                {isActive && (
                  <div className="flex items-center gap-2 text-sm text-[#786A60]">
                    <Check size={16} />
                    {membership.auto_renew ? 'Auto-renew enabled' : 'Auto-renew disabled'}
                  </div>
                )}
              </div>

              <div className="space-y-3">
                {isActive && (
                  <>
                    {membership.auto_renew ? (
                      <button
                        onClick={handleCancel}
                        className="w-full py-3 px-4 border border-[#E8E0D5] rounded text-[#2C2420] hover:bg-[#F3EFEA] transition-colors"
                      >
                        Cancel Auto-renew
                      </button>
                    ) : (
                      <button
                        onClick={handleReactivate}
                        className="w-full py-3 px-4 bg-[#4A3B32] text-white rounded hover:bg-[#332822] transition-colors"
                      >
                        Enable Auto-renew
                      </button>
                    )}
                  </>
                )}

                {(isExpired || isCancelled) && (
                  <button
                    onClick={() => window.location.reload()}
                    className="w-full py-3 px-4 bg-[#4A3B32] text-white rounded hover:bg-[#332822] transition-colors"
                  >
                    Subscribe Again
                  </button>
                )}
              </div>

              {error && (
                <div className="mt-4 bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded">
                  {error}
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
    );
  }

  // Show plans for subscription
  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5]">
      <BakeryNavbar businessId={businessId} />
      <main className="flex-1 py-8">
        <div className="max-w-4xl mx-auto px-4">
          <div className="text-center mb-8">
            <Crown className="w-16 h-16 text-[#4A3B32] mx-auto mb-4" />
            <h1 className="text-3xl font-bold text-[#2C2420] mb-2">{config.display_name}</h1>
            <p className="text-[#786A60]">{config.tagline}</p>
          </div>

          {config.enabled_features.length > 0 && (
            <div className="mb-8">
              <h2 className="text-lg font-semibold text-[#2C2420] mb-4">Included Features</h2>
              <div className="flex flex-wrap gap-2">
                {config.enabled_features.map(feature => (
                  <span
                    key={feature}
                    className="bg-[#4A3B32] text-white px-3 py-1 rounded-full text-sm"
                  >
                    {feature.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="grid md:grid-cols-2 gap-6">
            {config.plans.map(plan => (
              <div
                key={plan.plan_id}
                className="bg-white border border-[#E8E0D5] rounded-lg p-6 hover:border-[#4A3B32] transition-colors"
              >
                <h3 className="text-xl font-bold text-[#2C2420] mb-2">{plan.name}</h3>
                <div className="mb-4">
                  <span className="text-3xl font-bold text-[#4A3B32]">
                    ₹{plan.price}
                  </span>
                  <span className="text-[#786A60]">/{plan.billing_cycle === 'monthly' ? 'month' : 'year'}</span>
                </div>

                {plan.marketing_features.length > 0 && (
                  <ul className="space-y-2 mb-6">
                    {plan.marketing_features.map((feature, index) => (
                      <li key={index} className="flex items-start gap-2 text-sm text-[#2C2420]">
                        <Check size={16} className="text-green-600 mt-0.5 flex-shrink-0" />
                        {feature}
                      </li>
                    ))}
                  </ul>
                )}

                <button
                  onClick={() => handleSubscribe(plan.plan_id)}
                  disabled={subscribing}
                  className="w-full py-3 px-4 bg-[#4A3B32] text-white rounded hover:bg-[#332822] disabled:opacity-60 transition-colors"
                >
                  {subscribing ? (
                    <span className="flex items-center justify-center gap-2">
                      <Loader2 size={16} className="animate-spin" />
                      Processing...
                    </span>
                  ) : (
                    'Subscribe Now'
                  )}
                </button>
              </div>
            ))}
          </div>

          {error && (
            <div className="mt-6 bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded">
              {error}
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default PrimeUpgradePage;
