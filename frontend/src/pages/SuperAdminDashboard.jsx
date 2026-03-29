import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Navbar from '../components/common/Navbar';
import apiClient from '../utils/api';
import { Package, TrendingUp, Users, AlertTriangle, Store } from 'lucide-react';

const SuperAdminDashboard = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [businesses, setBusinesses] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, businessesRes] = await Promise.all([
          apiClient.get('/analytics/dashboard'),
          apiClient.get('/businesses')
        ]);
        setStats(statsRes.data.system_stats);
        setBusinesses(businessesRes.data.businesses);
      } catch (error) {
        console.error('Error fetching dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col">
        <Navbar />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto"></div>
            <p className="mt-4 text-muted">Loading dashboard...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-surface">
      <Navbar />

      <main className="flex-1 py-8" data-testid="super-admin-dashboard">
        <div className="max-w-7xl mx-auto px-8">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-4xl font-black tracking-tight text-primary uppercase mb-2">
              SUPER ADMIN DASHBOARD
            </h1>
            <p className="text-sm text-muted">Welcome back, {user?.name}</p>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div className="bg-white border border-border p-6" data-testid="stat-businesses">
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 bg-primary flex items-center justify-center">
                  <Store size={24} className="text-white" strokeWidth={1.5} />
                </div>
                <p className="text-3xl font-black text-primary">{stats?.total_businesses || 0}</p>
              </div>
              <p className="text-sm font-bold tracking-wide uppercase text-muted">TOTAL BUSINESSES</p>
            </div>

            <div className="bg-white border border-border p-6" data-testid="stat-products">
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 bg-primary flex items-center justify-center">
                  <Package size={24} className="text-white" strokeWidth={1.5} />
                </div>
                <p className="text-3xl font-black text-primary">{stats?.total_products || 0}</p>
              </div>
              <p className="text-sm font-bold tracking-wide uppercase text-muted">TOTAL PRODUCTS</p>
            </div>

            <div className="bg-white border border-border p-6" data-testid="stat-users">
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 bg-primary flex items-center justify-center">
                  <Users size={24} className="text-white" strokeWidth={1.5} />
                </div>
                <p className="text-3xl font-black text-primary">{stats?.total_users || 0}</p>
              </div>
              <p className="text-sm font-bold tracking-wide uppercase text-muted">TOTAL USERS</p>
            </div>

            <div className="bg-white border border-border p-6" data-testid="stat-low-stock">
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 bg-destructive flex items-center justify-center">
                  <AlertTriangle size={24} className="text-white" strokeWidth={1.5} />
                </div>
                <p className="text-3xl font-black text-destructive">{stats?.low_stock_items || 0}</p>
              </div>
              <p className="text-sm font-bold tracking-wide uppercase text-muted">LOW STOCK ALERTS</p>
            </div>
          </div>

          {/* Businesses Table */}
          <div className="bg-white border border-border">
            <div className="p-6 border-b border-border">
              <h2 className="text-xl font-bold text-primary">ALL BUSINESSES</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full" data-testid="businesses-table">
                <thead>
                  <tr className="border-b border-border bg-surface">
                    <th className="text-left p-4 text-xs font-bold tracking-wide uppercase text-muted">Business</th>
                    <th className="text-left p-4 text-xs font-bold tracking-wide uppercase text-muted">Type</th>
                    <th className="text-left p-4 text-xs font-bold tracking-wide uppercase text-muted">Location</th>
                    <th className="text-left p-4 text-xs font-bold tracking-wide uppercase text-muted">Status</th>
                    <th className="text-right p-4 text-xs font-bold tracking-wide uppercase text-muted">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {businesses.map((business) => (
                    <tr
                      key={business.business_id}
                      className="border-b border-border hover:bg-surface transition-colors"
                      data-testid={`business-row-${business.business_id}`}
                    >
                      <td className="p-4">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 bg-surface flex items-center justify-center overflow-hidden">
                            <img src={business.logo_url} alt={business.business_name} className="w-full h-full object-cover" />
                          </div>
                          <div>
                            <p className="font-semibold text-primary">{business.business_name}</p>
                            <p className="text-xs text-muted">{business.business_id}</p>
                          </div>
                        </div>
                      </td>
                      <td className="p-4">
                        <span className="text-sm text-muted">{business.business_type.replace('_', ' ')}</span>
                      </td>
                      <td className="p-4">
                        <span className="text-sm text-muted">
                          {business.contact.city}, {business.contact.state}
                        </span>
                      </td>
                      <td className="p-4">
                        <span className={`text-xs px-2 py-1 font-bold ${
                          business.status === 'active' 
                            ? 'bg-green-100 text-green-800' 
                            : 'bg-red-100 text-red-800'
                        }`}>
                          {business.status.toUpperCase()}
                        </span>
                      </td>
                      <td className="p-4 text-right">
                        <Link
                          to={`/catalog/${business.business_id}`}
                          className="text-sm font-bold text-accent hover:text-[#002280] transition-colors"
                          data-testid={`view-business-${business.business_id}`}
                        >
                          VIEW CATALOG
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
            <Link
              to="/admin"
              className="bg-white border border-border p-6 hover:-translate-y-1 hover:shadow-lg transition-all"
              data-testid="manage-inventory-link"
            >
              <Package size={32} className="text-primary mb-4" strokeWidth={1.5} />
              <h3 className="text-lg font-bold text-primary mb-2">MANAGE INVENTORY</h3>
              <p className="text-sm text-muted">View and update stock levels across all businesses</p>
            </Link>

            <Link
              to="/admin"
              className="bg-white border border-border p-6 hover:-translate-y-1 hover:shadow-lg transition-all"
              data-testid="user-management-link"
            >
              <Users size={32} className="text-primary mb-4" strokeWidth={1.5} />
              <h3 className="text-lg font-bold text-primary mb-2">USER MANAGEMENT</h3>
              <p className="text-sm text-muted">Manage users and assign roles</p>
            </Link>

            <Link
              to="/admin"
              className="bg-white border border-border p-6 hover:-translate-y-1 hover:shadow-lg transition-all"
              data-testid="analytics-link"
            >
              <TrendingUp size={32} className="text-primary mb-4" strokeWidth={1.5} />
              <h3 className="text-lg font-bold text-primary mb-2">ANALYTICS</h3>
              <p className="text-sm text-muted">View detailed reports and insights</p>
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
};

export default SuperAdminDashboard;
