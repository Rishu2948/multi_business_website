import { Link } from 'react-router-dom';
import Navbar from '../components/common/Navbar';
import Footer from '../components/common/Footer';
import { ArrowRight, Package, TrendingUp, Users, Shield } from 'lucide-react';

const Landing = () => {
  const businesses = [
    {
      id: 'rishabh_garments',
      name: 'Rishabh Garments',
      description: 'Premium kids wear collection',
      image: 'https://images.pexels.com/photos/5560013/pexels-photo-5560013.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940',
      category: 'Kids Wear'
    },
    {
      id: 'jain_jewellers',
      name: 'Jain Jewellers',
      description: 'Exquisite gold and diamond jewellery',
      image: 'https://images.pexels.com/photos/3641056/pexels-photo-3641056.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940',
      category: 'Jewellery'
    },
    {
      id: 'jain_sarees',
      name: 'Jain Sarees',
      description: 'Traditional and designer sarees',
      image: 'https://images.pexels.com/photos/36194190/pexels-photo-36194190.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940',
      category: 'Sarees'
    },
    {
      id: 'whisked_words',
      name: 'Whisked Words',
      description: 'Artisan bakery with fresh pastries',
      image: 'https://images.pexels.com/photos/192933/pexels-photo-192933.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940',
      category: 'Bakery'
    }
  ];

  const features = [
    {
      icon: Package,
      title: 'Inventory Management',
      description: 'Real-time stock tracking across all businesses'
    },
    {
      icon: TrendingUp,
      title: 'Business Analytics',
      description: 'Comprehensive insights and performance metrics'
    },
    {
      icon: Users,
      title: 'Multi-User Access',
      description: 'Role-based permissions for team collaboration'
    },
    {
      icon: Shield,
      title: 'Secure & Reliable',
      description: 'Enterprise-grade security for your data'
    }
  ];

  return (
    <div className="min-h-screen flex flex-col bg-white">
      <Navbar />

      {/* Hero Section */}
      <section className="py-20 md:py-32 bg-white" data-testid="hero-section">
        <div className="max-w-7xl mx-auto px-8">
          <div className="max-w-4xl">
            <p className="text-xs tracking-[0.2em] uppercase font-bold text-muted mb-6">UNIFIED MANAGEMENT PLATFORM</p>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl tracking-tighter font-black uppercase text-primary mb-8 leading-none">
              ONE PLATFORM,<br />
              FOUR AMAZING<br />
              BUSINESSES
            </h1>
            <p className="text-base leading-relaxed text-muted max-w-2xl mb-12">
              Streamline operations across multiple businesses with our comprehensive management platform.
              From inventory tracking to analytics, everything you need in one place.
            </p>
            <div className="flex flex-wrap gap-4">
              <Link
                to="/businesses"
                className="bg-primary text-white hover:bg-[#333333] transition-all border border-primary px-8 py-4 font-bold tracking-wide flex items-center gap-2"
                data-testid="explore-businesses-button"
              >
                EXPLORE BUSINESSES
                <ArrowRight size={20} />
              </Link>
              <Link
                to="/login"
                className="bg-transparent text-primary hover:bg-secondary transition-all border border-border px-8 py-4 font-bold tracking-wide"
                data-testid="admin-login-button"
              >
                ADMIN LOGIN
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Businesses Grid - Bento Style */}
      <section className="py-20 bg-surface" data-testid="businesses-section">
        <div className="max-w-7xl mx-auto px-8">
          <div className="mb-12">
            <p className="text-xs tracking-[0.2em] uppercase font-bold text-muted mb-4">OUR BUSINESSES</p>
            <h2 className="text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold text-primary">Diverse Portfolio, Unified Management</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            {businesses.map((business, index) => (
              <Link
                key={business.id}
                to={`/catalog/${business.id}`}
                className="bg-white border border-border p-0 hover:-translate-y-1 hover:shadow-xl transition-transform duration-300 group"
                data-testid={`business-card-${business.id}`}
              >
                <div className="aspect-square overflow-hidden">
                  <img
                    src={business.image}
                    alt={business.name}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                  />
                </div>
                <div className="p-6">
                  <p className="text-xs tracking-[0.2em] uppercase font-bold text-muted mb-2">{business.category}</p>
                  <h3 className="text-xl font-bold text-primary mb-2">{business.name}</h3>
                  <p className="text-sm text-muted mb-4">{business.description}</p>
                  <div className="flex items-center gap-2 text-accent font-bold text-sm">
                    VISIT STORE
                    <ArrowRight size={16} />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 bg-white" data-testid="features-section">
        <div className="max-w-7xl mx-auto px-8">
          <div className="mb-12 text-center">
            <p className="text-xs tracking-[0.2em] uppercase font-bold text-muted mb-4">PLATFORM FEATURES</p>
            <h2 className="text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold text-primary">Everything You Need To Succeed</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map((feature, index) => {
              const Icon = feature.icon;
              return (
                <div
                  key={index}
                  className="bg-white border border-border p-6"
                  data-testid={`feature-${index}`}
                >
                  <div className="w-12 h-12 bg-primary flex items-center justify-center mb-4">
                    <Icon size={24} className="text-white" strokeWidth={1.5} />
                  </div>
                  <h3 className="text-lg font-semibold text-primary mb-2">{feature.title}</h3>
                  <p className="text-sm text-muted">{feature.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-primary text-white" data-testid="cta-section">
        <div className="max-w-4xl mx-auto px-8 text-center">
          <h2 className="text-2xl sm:text-3xl lg:text-4xl tracking-tight font-bold mb-6">
            READY TO STREAMLINE YOUR OPERATIONS?
          </h2>
          <p className="text-base leading-relaxed text-white/70 mb-8 max-w-2xl mx-auto">
            Join us today and experience the power of unified business management.
          </p>
          <Link
            to="/login"
            className="inline-flex items-center gap-2 bg-white text-primary hover:bg-surface transition-all border border-white px-8 py-4 font-bold tracking-wide"
            data-testid="cta-login-button"
          >
            GET STARTED
            <ArrowRight size={20} />
          </Link>
        </div>
      </section>

      <Footer />
    </div>
  );
};

export default Landing;