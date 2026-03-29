import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useBusiness } from '../context/BusinessContext';
import Navbar from '../components/common/Navbar';
import apiClient from '../utils/api';
import { Package, AlertTriangle, Edit } from 'lucide-react';

const StaffDashboard = () => {
  const { user } = useAuth();
  const { selectedBusiness, setSelectedBusiness } = useBusiness();
  const [inventory, setInventory] = useState([]);
  const [businesses, setBusinesses] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchBusinesses = async () => {
      try {
        const response = await apiClient.get('/businesses');
        setBusinesses(response.data.businesses);
        
        // Auto-select first business
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

    const fetchInventory = async () => {
      try {
        const response = await apiClient.get(`/inventory?business_id=${selectedBusiness.business_id}`);
        setInventory(response.data.inventory);
      } catch (error) {
        console.error('Error fetching inventory:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchInventory();
  }, [selectedBusiness]);

  const handleInventoryUpdate = async (inventoryId, quantityChange) => {
    try {
      await apiClient.put(`/inventory/${inventoryId}`, {
        quantity_change: quantityChange,
        movement_type: quantityChange > 0 ? 'purchase' : 'sale',
        reason: 'Staff adjustment'
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
            <p className="mt-4 text-muted">Loading...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-surface">
      <Navbar />

      <main className="flex-1 py-8" data-testid="staff-dashboard">
        <div className="max-w-7xl mx-auto px-8">
          {/* Header */}
          <div className="mb-8 flex items-start justify-between">
            <div>
              <h1 className="text-4xl font-black tracking-tight text-primary uppercase mb-2">
                STAFF PORTAL
              </h1>
              <p className="text-sm text-muted">Welcome, {user?.name}</p>
            </div>
            
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

          {/* Quick Stats */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div className="bg-white border border-border p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 bg-primary flex items-center justify-center">
                  <Package size={24} className="text-white" strokeWidth={1.5} />
                </div>
                <p className="text-3xl font-black text-primary">{inventory.length}</p>
              </div>
              <p className="text-sm font-bold tracking-wide uppercase text-muted">TOTAL ITEMS</p>
            </div>

            <div className="bg-white border border-border p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 bg-destructive flex items-center justify-center">
                  <AlertTriangle size={24} className="text-white" strokeWidth={1.5} />
                </div>
                <p className="text-3xl font-black text-destructive">
                  {inventory.filter(item => item.quantity.available <= item.reorder.reorder_level).length}
                </p>
              </div>
              <p className="text-sm font-bold tracking-wide uppercase text-muted">LOW STOCK</p>
            </div>

            <div className="bg-white border border-border p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 bg-destructive flex items-center justify-center">
                  <Package size={24} className="text-white" strokeWidth={1.5} />
                </div>
                <p className="text-3xl font-black text-destructive">
                  {inventory.filter(item => item.quantity.available === 0).length}
                </p>
              </div>
              <p className="text-sm font-bold tracking-wide uppercase text-muted">OUT OF STOCK</p>
            </div>
          </div>

          {/* Inventory Management */}
          <div className="bg-white border border-border">
            <div className="p-6 border-b border-border">
              <h2 className="text-xl font-bold text-primary">INVENTORY UPDATES</h2>
              <p className="text-sm text-muted mt-1">Manage stock levels for {selectedBusiness.business_name}</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full" data-testid="staff-inventory-table">
                <thead>
                  <tr className="border-b border-border bg-surface">
                    <th className="text-left p-4 text-xs font-bold tracking-wide uppercase text-muted">Product</th>
                    <th className="text-left p-4 text-xs font-bold tracking-wide uppercase text-muted">SKU</th>
                    <th className="text-center p-4 text-xs font-bold tracking-wide uppercase text-muted">Available</th>
                    <th className="text-center p-4 text-xs font-bold tracking-wide uppercase text-muted">Status</th>
                    <th className="text-right p-4 text-xs font-bold tracking-wide uppercase text-muted">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {inventory.map((item) => {
                    const isLowStock = item.quantity.available <= item.reorder.reorder_level;
                    const isOutOfStock = item.quantity.available === 0;
                    return (
                      <tr
                        key={item.inventory_id}
                        className="border-b border-border hover:bg-surface transition-colors"
                        data-testid={`staff-inventory-row-${item.inventory_id}`}
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
                            isOutOfStock ? 'text-destructive' : isLowStock ? 'text-destructive' : 'text-primary'
                          }`}>
                            {item.quantity.available}
                          </span>
                        </td>
                        <td className="p-4 text-center">
                          {isOutOfStock ? (
                            <span className="text-xs px-2 py-1 bg-red-100 text-red-800 font-bold">OUT OF STOCK</span>
                          ) : isLowStock ? (
                            <span className="text-xs px-2 py-1 bg-yellow-100 text-yellow-800 font-bold">LOW STOCK</span>
                          ) : (
                            <span className="text-xs px-2 py-1 bg-green-100 text-green-800 font-bold">IN STOCK</span>
                          )}
                        </td>
                        <td className="p-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => handleInventoryUpdate(item.inventory_id, -1)}
                              className="px-3 py-1 bg-surface text-primary border border-border hover:bg-primary hover:text-white transition-all font-bold text-sm"
                              disabled={item.quantity.available === 0}
                              data-testid={`staff-decrease-stock-${item.inventory_id}`}
                            >
                              -
                            </button>
                            <button
                              onClick={() => handleInventoryUpdate(item.inventory_id, 1)}
                              className="px-3 py-1 bg-surface text-primary border border-border hover:bg-primary hover:text-white transition-all font-bold text-sm"
                              data-testid={`staff-increase-stock-${item.inventory_id}`}
                            >
                              +
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
    </div>
  );
};

export default StaffDashboard;