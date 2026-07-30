/**
 * BusinessConfigSelector — Business selection page for super admins
 * Allows super admins to select which business's config to manage.
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../../components/common/Navbar';
import { useAuth } from '../../context/AuthContext';
import apiClient from '../../utils/api';
import { Building2, ArrowRight } from 'lucide-react';

const BusinessConfigSelector = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [businesses, setBusinesses] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchBusinesses();
  }, []);

  const fetchBusinesses = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get('/businesses');
      setBusinesses(response.data.businesses || []);
    } catch (error) {
      console.error('Failed to fetch businesses:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectBusiness = (businessId) => {
    navigate(`/admin/business-config/${businessId}`);
  };

  if (user?.role !== 'super_admin') {
    return (
      <div className="min-h-screen flex flex-col">
        <Navbar />
        <main className="flex-1 flex items-center justify-center px-4">
          <div className="text-center">
            <p className="text-[#786A60]">Access denied. Super admin only.</p>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5]">
      <Navbar />
      <main className="flex-1 py-8">
        <div className="max-w-4xl mx-auto px-4">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-[#2C2420] mb-2">Select Business</h1>
            <p className="text-[#786A60]">Choose which business configuration to manage</p>
          </div>

          {loading ? (
            <div className="text-center py-12">
              <div className="inline-block w-8 h-8 border-4 border-[#4A3B32] border-t-transparent rounded-full animate-spin" />
            </div>
          ) : businesses.length === 0 ? (
            <div className="text-center py-12">
              <Building2 size={48} className="mx-auto text-[#786A60] mb-4" />
              <p className="text-[#786A60]">No businesses found</p>
            </div>
          ) : (
            <div className="grid gap-4">
              {businesses.map((business) => (
                <button
                  key={business.business_id}
                  onClick={() => handleSelectBusiness(business.business_id)}
                  className="flex items-center justify-between p-6 bg-white border border-[#E8E0D5] rounded-lg hover:border-[#4A3B32] hover:shadow-md transition-all"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-[#F3EFEA] rounded-full flex items-center justify-center">
                      <Building2 size={24} className="text-[#4A3B32]" />
                    </div>
                    <div className="text-left">
                      <h3 className="text-lg font-semibold text-[#2C2420]">{business.business_name}</h3>
                      <p className="text-sm text-[#786A60]">{business.business_id}</p>
                    </div>
                  </div>
                  <ArrowRight size={20} className="text-[#786A60]" />
                </button>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default BusinessConfigSelector;
