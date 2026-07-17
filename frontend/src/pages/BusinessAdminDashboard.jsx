import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useBusiness } from '../context/BusinessContext';
import Navbar from '../components/common/Navbar';
import AddProductModal from '../components/AddProductModal';
import apiClient from '../utils/api';
import {
  Package, AlertTriangle, TrendingUp, Plus, Edit, Trash2,
  Tag, Megaphone, Layers, Store, LayoutGrid
} from 'lucide-react';

const BusinessAdminDashboard = () => {
  const { user } = useAuth();
  const { selectedBusiness, setSelectedBusiness } = useBusiness();
  const [stats, setStats] = useState(null);
  const [inventory, setInventory] = useState([]);
  const [businesses, setBusinesses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddProduct, setShowAddProduct] = useState(false);

  useEffect(() => {
    const fetchBusinesses = async () => {
      try {
        const response = await apiClient.get('/businesses');
        setBusinesses(response.data.businesses);
        
        // Auto-select first business if not selected
        if (!selectedBusiness && response.data.businesses.length > 0) {
          setSelectedBusiness(response.data.businesses[0]);
        }
      } catch (error) {
        console.error('Error fetching businesses:', error);
      }
    };

    fetchBusinesses();
  }, [selectedBusiness, setSelectedBusiness]);

  useEffect(() => {
    if (!selectedBusiness) return;

    const fetchData = async () => {
      try {
        const [statsRes, inventoryRes] = await Promise.all([
          apiClient.get(`/analytics/dashboard?business_id=${selectedBusiness.business_id}`),
          apiClient.get(`/inventory?business_id=${selectedBusiness.business_id}`)
        ]);
        setStats(statsRes.data.business_stats);
        setInventory(inventoryRes.data.inventory);
      } catch (error) {
        console.error('Error fetching dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [selectedBusiness]);

  const handleInventoryUpdate = async (inventoryId, quantityChange) => {
    try {
      await apiClient.put(`/inventory/${inventoryId}`, {
        quantity_change: quantityChange,
        movement_type: quantityChange > 0 ? 'purchase' : 'sale',
        reason: 'Manual adjustment'
      });
      
      // Refresh inventory
      const response = await apiClient.get(`/inventory?business_id=${selectedBusiness.business_id}`);
      setInventory(response.data.inventory);
    } catch (error) {
      console.error('Error updating inventory:', error);
      alert('Failed to update inventory');
    }
  };

  if (loading || !selectedBusiness) {
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

      <main className="flex-1 py-8" data-testid="business-admin-dashboard">
        <div className="max-w-7xl mx-auto px-8">
          {/* Header with Business Selector */}
          <div className="mb-8 flex items-start justify-between">
            <div>
              <h1 className="text-4xl font-black tracking-tight text-primary uppercase mb-2">
                BUSINESS DASHBOARD
              </h1>
              <p className="text-sm text-muted">Managing {selectedBusiness.business_name}</p>
            </div>
            
            <div className="flex items-center gap-4">
              <Link
                to="/admin/orders"
                className="bg-primary text-white px-4 py-3 font-bold text-sm tracking-wide border border-primary hover:bg-[#333333] transition-all flex items-center gap-2"
                data-testid="manage-orders-button"
              >
                <Package size={16} />
                MANAGE ORDERS
              </Link>
              {businesses.length > 1 && (
                <select
                  value={selectedBusiness.business_id}
                  onChange={(e) => {
                    const business = businesses.find(b => b.business_id === e.target.value);
                    setSelectedBusiness(business);
                  }}
                  className="border border-border bg-white px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none text-base text-primary"
                  data-testid="business-selector"
                >
                  {businesses.map((business) => (
                    <option key={business.business_id} value={business.business_id}>
                      {business.business_name}
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div className="bg-white border border-border p-6" data-testid="stat-total-products">
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 bg-primary flex items-center justify-center">
                  <Package size={24} className="text-white" strokeWidth={1.5} />
                </div>
                <p className="text-3xl font-black text-primary">{stats?.total_products || 0}</p>
              </div>
              <p className="text-sm font-bold tracking-wide uppercase text-muted">TOTAL PRODUCTS</p>
            </div>

            <div className="bg-white border border-border p-6" data-testid="stat-inventory-value">
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 bg-primary flex items-center justify-center">
                  <TrendingUp size={24} className="text-white" strokeWidth={1.5} />
                </div>
                <p className="text-3xl font-black text-primary">
                  ₹{((stats?.total_inventory_value || 0) / 1000).toFixed(0)}K
                </p>
              </div>
              <p className="text-sm font-bold tracking-wide uppercase text-muted">INVENTORY VALUE</p>
            </div>

            <div className="bg-white border border-border p-6" data-testid="stat-low-stock">
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 bg-destructive flex items-center justify-center">
                  <AlertTriangle size={24} className="text-white" strokeWidth={1.5} />
                </div>
                <p className="text-3xl font-black text-destructive">{stats?.low_stock_items || 0}</p>
              </div>
              <p className="text-sm font-bold tracking-wide uppercase text-muted">LOW STOCK ITEMS</p>
            </div>

            <div className="bg-white border border-border p-6" data-testid="stat-out-of-stock">
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 bg-destructive flex items-center justify-center">
                  <Package size={24} className="text-white" strokeWidth={1.5} />
                </div>
                <p className="text-3xl font-black text-destructive">{stats?.out_of_stock_items || 0}</p>
              </div>
              <p className="text-sm font-bold tracking-wide uppercase text-muted">OUT OF STOCK</p>
            </div>
          </div>

          {/* Inventory Table */}
          <div className="bg-white border border-border mb-8">
            <div className="p-6 border-b border-border flex items-center justify-between">
              <h2 className="text-xl font-bold text-primary">INVENTORY MANAGEMENT</h2>
              <button
                onClick={() => setShowAddProduct(true)}
                className="bg-accent text-white px-4 py-2 font-bold text-sm tracking-wide border border-accent hover:bg-[#002280] transition-all flex items-center gap-2"
                data-testid="add-product-button"
              >
                <Plus size={16} />
                ADD PRODUCT
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full" data-testid="inventory-table">
                <thead>
                  <tr className="border-b border-border bg-surface">
                    <th className="text-left p-4 text-xs font-bold tracking-wide uppercase text-muted">Product</th>
                    <th className="text-left p-4 text-xs font-bold tracking-wide uppercase text-muted">SKU</th>
                    <th className="text-center p-4 text-xs font-bold tracking-wide uppercase text-muted">Available</th>
                    <th className="text-center p-4 text-xs font-bold tracking-wide uppercase text-muted">Reserved</th>
                    <th className="text-center p-4 text-xs font-bold tracking-wide uppercase text-muted">Total</th>
                    <th className="text-right p-4 text-xs font-bold tracking-wide uppercase text-muted">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {inventory.slice(0, 10).map((item) => {
                    const isLowStock = item.quantity.available <= item.reorder.reorder_level;
                    return (
                      <tr
                        key={item.inventory_id}
                        className="border-b border-border hover:bg-surface transition-colors"
                        data-testid={`inventory-row-${item.inventory_id}`}
                      >
                        <td className="p-4">
                          <div>
                            <p className="font-semibold text-primary">{item.product_name || 'Unknown Product'}</p>
                            <p className="text-xs text-muted">{item.product_id}</p>
                          </div>
                        </td>
                        <td className="p-4">
                          <span className="text-sm text-muted font-mono">{item.sku || 'N/A'}</span>
                        </td>
                        <td className="p-4 text-center">
                          <span className={`text-base font-bold ${
                            isLowStock ? 'text-destructive' : 'text-primary'
                          }`}>
                            {item.quantity.available}
                            {isLowStock && ' ⚠️'}
                          </span>
                        </td>
                        <td className="p-4 text-center">
                          <span className="text-base text-muted">{item.quantity.reserved}</span>
                        </td>
                        <td className="p-4 text-center">
                          <span className="text-base font-semibold text-primary">{item.quantity.total}</span>
                        </td>
                        <td className="p-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => handleInventoryUpdate(item.inventory_id, -1)}
                              className="px-3 py-1 bg-surface text-primary border border-border hover:bg-primary hover:text-white transition-all font-bold text-sm"
                              disabled={item.quantity.available === 0}
                              data-testid={`decrease-stock-${item.inventory_id}`}
                            >
                              -
                            </button>
                            <button
                              onClick={() => handleInventoryUpdate(item.inventory_id, 1)}
                              className="px-3 py-1 bg-surface text-primary border border-border hover:bg-primary hover:text-white transition-all font-bold text-sm"
                              data-testid={`increase-stock-${item.inventory_id}`}
                            >
                              +
                            </button>
                            <button
                              className="px-3 py-1 text-accent hover:text-[#002280] transition-colors"
                              data-testid={`edit-inventory-${item.inventory_id}`}
                            >
                              <Edit size={16} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {inventory.length === 0 && (
              <div className="text-center py-12">
                <Package size={48} className="mx-auto text-muted mb-4" strokeWidth={1.5} />
                <p className="text-muted">No inventory items found</p>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Add Product Modal */}
      {/* ── Config Management ─────────────────────────────────────────── */}
          <div className="mt-8 mb-8">
            <h2 className="text-xl font-bold text-primary uppercase mb-4 tracking-tight">
              STORE CONFIGURATION
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <Link
                to="/admin/categories"
                className="bg-white border border-border p-5 hover:-translate-y-0.5 hover:shadow-md transition-all group"
                data-testid="nav-categories"
              >
                <LayoutGrid size={28} className="text-primary mb-3" strokeWidth={1.5} />
                <h3 className="text-sm font-bold text-primary uppercase tracking-wide mb-1">
                  CATEGORY MANAGER
                </h3>
                <p className="text-xs text-muted">Add, rename, reorder menu categories. No redeploy needed.</p>
              </Link>

              <Link
                to="/admin/products"
                className="bg-white border border-border p-5 hover:-translate-y-0.5 hover:shadow-md transition-all"
                data-testid="nav-products"
              >
                <Package size={28} className="text-primary mb-3" strokeWidth={1.5} />
                <h3 className="text-sm font-bold text-primary uppercase tracking-wide mb-1">
                  PRODUCT MANAGER
                </h3>
                <p className="text-xs text-muted">Add products, manage addons, veg flags, collection tags.</p>
              </Link>

              <Link
                to="/admin/store-config"
                className="bg-white border border-border p-5 hover:-translate-y-0.5 hover:shadow-md transition-all"
                data-testid="nav-store-config"
              >
                <Store size={28} className="text-primary mb-3" strokeWidth={1.5} />
                <h3 className="text-sm font-bold text-primary uppercase tracking-wide mb-1">
                  STORE CONFIG
                </h3>
                <p className="text-xs text-muted">Business hours, order types, delivery settings, tax rate.</p>
              </Link>

              <Link
                to="/admin/offers"
                className="bg-white border border-border p-5 hover:-translate-y-0.5 hover:shadow-md transition-all"
                data-testid="nav-offers"
              >
                <Tag size={28} className="text-primary mb-3" strokeWidth={1.5} />
                <h3 className="text-sm font-bold text-primary uppercase tracking-wide mb-1">
                  OFFERS MANAGER
                </h3>
                <p className="text-xs text-muted">Create promo codes, discounts, and auto-applied offers.</p>
              </Link>

              <Link
                to="/admin/collections"
                className="bg-white border border-border p-5 hover:-translate-y-0.5 hover:shadow-md transition-all"
                data-testid="nav-collections"
              >
                <Layers size={28} className="text-primary mb-3" strokeWidth={1.5} />
                <h3 className="text-sm font-bold text-primary uppercase tracking-wide mb-1">
                  COLLECTIONS
                </h3>
                <p className="text-xs text-muted">Manage Gifting, Festive, Corporate groupings.</p>
              </Link>

              <Link
                to="/admin/announcements"
                className="bg-white border border-border p-5 hover:-translate-y-0.5 hover:shadow-md transition-all"
                data-testid="nav-announcements"
              >
                <Megaphone size={28} className="text-primary mb-3" strokeWidth={1.5} />
                <h3 className="text-sm font-bold text-primary uppercase tracking-wide mb-1">
                  ANNOUNCEMENTS
                </h3>
                <p className="text-xs text-muted">Edit the top banner bar message shown to customers.</p>
              </Link>
            </div>
          </div>

      <AddProductModal
        isOpen={showAddProduct}
        onClose={() => setShowAddProduct(false)}
        businessId={selectedBusiness?.business_id}
        onProductAdded={() => {
          // Refresh data
          const fetchData = async () => {
            try {
              const [statsRes, inventoryRes] = await Promise.all([
                apiClient.get(`/analytics/dashboard?business_id=${selectedBusiness.business_id}`),
                apiClient.get(`/inventory?business_id=${selectedBusiness.business_id}`)
              ]);
              setStats(statsRes.data.business_stats);
              setInventory(inventoryRes.data.inventory);
            } catch (error) {
              console.error('Error refreshing data:', error);
            }
          };
          fetchData();
        }}
      />
    </div>
  );
};

export default BusinessAdminDashboard;