import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Navbar from '../components/common/Navbar';
import Footer from '../components/common/Footer';
import apiClient from '../utils/api';
import { ArrowRight, Loader2 } from 'lucide-react';

const Businesses = () => {
  const [businesses, setBusinesses] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchBusinesses = async () => {
      try {
        const response = await apiClient.get('/businesses/public');
        setBusinesses(response.data.businesses);
      } catch (error) {
        console.error('Error fetching businesses:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchBusinesses();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col">
        <Navbar />
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-white">
      <Navbar />

      <main className="flex-1 py-20" data-testid="businesses-page">
        <div className="max-w-7xl mx-auto px-8">
          {/* Header */}
          <div className="mb-16">
            <p className="text-xs tracking-[0.2em] uppercase font-bold text-muted mb-4">ALL BUSINESSES</p>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl tracking-tighter font-black uppercase text-primary mb-6 leading-none">
              EXPLORE OUR<br />
              PORTFOLIO
            </h1>
            <p className="text-base leading-relaxed text-muted max-w-2xl">
              Browse products from our diverse collection of businesses.
              From fashion to jewellery, sarees to baked goods - we have it all.
            </p>
          </div>

          {/* Businesses Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
            {businesses.map((business) => (
              <Link
                key={business.business_id}
                to={`/catalog/${business.business_id}`}
                className="group"
                data-testid={`business-item-${business.business_id}`}
              >
                <div className="bg-white border border-border overflow-hidden hover:-translate-y-2 transition-all duration-300">
                  {/* Image */}
                  <div className="aspect-[16/9] overflow-hidden">
                    <img
                      src={business.logo_url}
                      alt={business.business_name}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                    />
                  </div>

                  {/* Content */}
                  <div className="p-8">
                    <p className="text-xs tracking-[0.2em] uppercase font-bold text-muted mb-3">
                      {business.business_type.replace('_', ' ')}
                    </p>
                    <h2 className="text-2xl font-bold text-primary mb-4">{business.business_name}</h2>
                    <p className="text-base text-muted mb-6">{business.description}</p>

                    {/* Action */}
                    <div className="flex items-center justify-between pt-4 border-t border-border">
                      <div className="text-sm text-muted">
                        <p>{business.contact.city}, {business.contact.state}</p>
                      </div>
                      <div className="flex items-center gap-2 text-accent font-bold text-sm group-hover:gap-4 transition-all">
                        BROWSE CATALOG
                        <ArrowRight size={16} />
                      </div>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
};

export default Businesses;