/**
 * Prime Analytics Dashboard
 * Displays Prime membership metrics and analytics for business admins.
 */

import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import apiClient from '../../utils/api';
import { TrendingUp, Users, DollarSign, BarChart3, Calendar, RefreshCw, Building2 } from 'lucide-react';

const PrimeAnalytics = () => {
  const { businessId } = useParams();
  const { user } = useAuth();
  const isSuperAdmin = user?.role === 'super_admin';

  const [analytics, setAnalytics] = useState(null);
  const [allBusinessAnalytics, setAllBusinessAnalytics] = useState(null);
  const [churnRate, setChurnRate] = useState(null);
  const [revenueForecast, setRevenueForecast] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [days, setDays] = useState(30);
  const [viewMode, setViewMode] = useState('single'); // 'single' or 'all'

  const fetchAnalytics = async () => {
    setLoading(true);
    setError('');
    try {
      if (viewMode === 'all' && isSuperAdmin) {
        const [allRes, churnRes, forecastRes] = await Promise.all([
          apiClient.get(`/prime/admin/analytics/all?days=${days}`),
          apiClient.get(`/prime/admin/churn-rate/${businessId}?days=${days}`),
          apiClient.get(`/prime/admin/revenue-forecast/${businessId}?months=6`),
        ]);
        setAllBusinessAnalytics(allRes.data);
        setChurnRate(churnRes.data);
        setRevenueForecast(forecastRes.data);
      } else {
        const [analyticsRes, churnRes, forecastRes] = await Promise.all([
          apiClient.get(`/prime/admin/analytics/${businessId}?days=${days}`),
          apiClient.get(`/prime/admin/churn-rate/${businessId}?days=${days}`),
          apiClient.get(`/prime/admin/revenue-forecast/${businessId}?months=6`),
        ]);
        setAnalytics(analyticsRes.data);
        setChurnRate(churnRes.data);
        setRevenueForecast(forecastRes.data);
      }
    } catch (err) {
      setError('Failed to load analytics data');
      console.error('Error fetching analytics:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (businessId) {
      fetchAnalytics();
    }
  }, [businessId, days, viewMode]);

  const StatCard = ({ icon: Icon, label, value, subtext }) => (
    <div className="bg-white border border-[#E8E0D5] rounded-lg p-6">
      <div className="flex items-center justify-between mb-2">
        <Icon size={20} className="text-[#4A3B32]" />
        <span className="text-xs text-[#786A60] uppercase tracking-wide">{label}</span>
      </div>
      <div className="text-2xl font-bold text-[#2C2420] mb-1">{value}</div>
      {subtext && <div className="text-xs text-[#786A60]">{subtext}</div>}
    </div>
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="animate-spin text-[#4A3B32]" size={32} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
        {error}
      </div>
    );
  }

  const data = viewMode === 'all' ? allBusinessAnalytics : analytics;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-[#2C2420] mb-1">Prime Analytics</h2>
          <p className="text-[#786A60]">Membership metrics and performance insights</p>
        </div>
        <div className="flex items-center gap-3">
          {isSuperAdmin && (
            <button
              onClick={() => setViewMode(viewMode === 'single' ? 'all' : 'single')}
              className="flex items-center gap-2 px-4 py-2 border border-[#E8E0D5] rounded-lg text-[#2C2420] hover:bg-[#F3EFEA] transition-colors"
            >
              <Building2 size={16} />
              {viewMode === 'single' ? 'View All Businesses' : 'View Single Business'}
            </button>
          )}
          <select
            value={days}
            onChange={(e) => setDays(parseInt(e.target.value))}
            className="px-4 py-2 border border-[#E8E0D5] rounded-lg text-[#2C2420] bg-white"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <button
            onClick={fetchAnalytics}
            className="flex items-center gap-2 px-4 py-2 border border-[#E8E0D5] rounded-lg text-[#2C2420] hover:bg-[#F3EFEA] transition-colors"
          >
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>
      </div>

      {viewMode === 'all' && data && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <StatCard
            icon={Building2}
            label="Total Businesses"
            value={data.total_businesses}
          />
          <StatCard
            icon={Users}
            label="Total Memberships"
            value={data.total_memberships}
            subtext={`${data.active_memberships} active`}
          />
          <StatCard
            icon={DollarSign}
            label="Total Revenue"
            value={`₹${data.total_revenue.toLocaleString()}`}
          />
          <StatCard
            icon={Calendar}
            label="Period"
            value={`${data.period_days} days`}
          />
        </div>
      )}

      {viewMode === 'single' && data && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <StatCard
              icon={Users}
              label="Total Memberships"
              value={data.total_memberships}
              subtext={`${data.active_memberships} active`}
            />
            <StatCard
              icon={TrendingUp}
              label="Active Members"
              value={data.active_memberships}
              subtext={`${data.expired_memberships} expired`}
            />
            <StatCard
              icon={DollarSign}
              label="Revenue"
              value={`₹${data.revenue.toLocaleString()}`}
              subtext={`${data.conversion_rate}% conversion`}
            />
            <StatCard
              icon={BarChart3}
              label="Cancelled"
              value={data.cancelled_memberships}
              subtext={`${data.trial_memberships} trials`}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white border border-[#E8E0D5] rounded-lg p-6">
              <h3 className="text-lg font-semibold text-[#2C2420] mb-4">Plan Distribution</h3>
              <div className="space-y-3">
                {Object.entries(data.plan_distribution || {}).map(([plan, count]) => (
                  <div key={plan} className="flex items-center justify-between">
                    <span className="text-sm text-[#2C2420]">{plan}</span>
                    <span className="text-sm font-semibold text-[#4A3B32]">{count}</span>
                  </div>
                ))}
                {Object.keys(data.plan_distribution || {}).length === 0 && (
                  <div className="text-sm text-[#786A60]">No plan data available</div>
                )}
              </div>
            </div>

            <div className="bg-white border border-[#E8E0D5] rounded-lg p-6">
              <h3 className="text-lg font-semibold text-[#2C2420] mb-4">Daily Signups</h3>
              <div className="space-y-3 max-h-48 overflow-y-auto">
                {Object.entries(data.daily_signups || {}).map(([date, count]) => (
                  <div key={date} className="flex items-center justify-between">
                    <span className="text-sm text-[#2C2420]">{date}</span>
                    <span className="text-sm font-semibold text-[#4A3B32]">{count}</span>
                  </div>
                ))}
                {Object.keys(data.daily_signups || {}).length === 0 && (
                  <div className="text-sm text-[#786A60]">No signup data available</div>
                )}
              </div>
            </div>
          </div>
        </>
      )}

      {churnRate && (
        <div className="bg-white border border-[#E8E0D5] rounded-lg p-6">
          <h3 className="text-lg font-semibold text-[#2C2420] mb-4">Churn Rate</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatCard
              icon={Users}
              label="Active at Start"
              value={churnRate.active_at_start}
            />
            <StatCard
              icon={TrendingUp}
              label="Cancelled"
              value={churnRate.cancelled_during_period}
            />
            <StatCard
              icon={BarChart3}
              label="Churn Rate"
              value={`${churnRate.churn_rate}%`}
              subtext={`Last ${churnRate.period_days} days`}
            />
          </div>
        </div>
      )}

      {revenueForecast && (
        <div className="bg-white border border-[#E8E0D5] rounded-lg p-6">
          <h3 className="text-lg font-semibold text-[#2C2420] mb-4">Revenue Forecast</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatCard
              icon={DollarSign}
              label="Current MRR"
              value={`₹${revenueForecast.current_mrr.toLocaleString()}`}
              subtext="Monthly Recurring Revenue"
            />
            <StatCard
              icon={Calendar}
              label="Forecast Period"
              value={`${revenueForecast.forecast_months} months`}
            />
            <StatCard
              icon={TrendingUp}
              label="Projected Revenue"
              value={`₹${revenueForecast.projected_revenue.toLocaleString()}`}
              subtext={`${revenueForecast.active_auto_renew_memberships} auto-renewing`}
            />
          </div>
        </div>
      )}

      {viewMode === 'all' && data && data.business_analytics && data.business_analytics.length > 0 && (
        <div className="bg-white border border-[#E8E0D5] rounded-lg p-6">
          <h3 className="text-lg font-semibold text-[#2C2420] mb-4">Business Breakdown</h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[#E8E0D5]">
                  <th className="text-left py-2 px-4 text-xs font-semibold text-[#2C2420] uppercase">Business ID</th>
                  <th className="text-left py-2 px-4 text-xs font-semibold text-[#2C2420] uppercase">Total</th>
                  <th className="text-left py-2 px-4 text-xs font-semibold text-[#2C2420] uppercase">Active</th>
                  <th className="text-left py-2 px-4 text-xs font-semibold text-[#2C2420] uppercase">Revenue</th>
                </tr>
              </thead>
              <tbody>
                {data.business_analytics.map((business) => (
                  <tr key={business.business_id} className="border-b border-[#E8E0D5]">
                    <td className="py-2 px-4 text-sm text-[#2C2420]">{business.business_id}</td>
                    <td className="py-2 px-4 text-sm text-[#2C2420]">{business.total_memberships}</td>
                    <td className="py-2 px-4 text-sm text-[#2C2420]">{business.active_memberships}</td>
                    <td className="py-2 px-4 text-sm text-[#2C2420]">₹{business.revenue.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default PrimeAnalytics;
