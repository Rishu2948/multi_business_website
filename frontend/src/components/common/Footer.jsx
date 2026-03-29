import { Link } from 'react-router-dom';

const Footer = () => {
  return (
    <footer className="bg-primary text-white mt-auto">
      <div className="max-w-7xl mx-auto px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Brand */}
          <div>
            <h3 className="text-lg font-black tracking-tight mb-4 uppercase">Jain Industries</h3>
            <p className="text-sm text-white/70">
              A diversified business conglomerate managing four successful brands across fashion, jewellery, textiles, and food industries.
            </p>
          </div>

          {/* Businesses */}
          <div>
            <h4 className="text-sm font-bold tracking-wide uppercase mb-4">Our Businesses</h4>
            <ul className="space-y-2">
              <li>
                <Link to="/catalog/rishabh_garments" className="text-sm text-white/70 hover:text-white transition-colors">
                  Rishabh Garments
                </Link>
              </li>
              <li>
                <Link to="/catalog/jain_jewellers" className="text-sm text-white/70 hover:text-white transition-colors">
                  Jain Jewellers
                </Link>
              </li>
              <li>
                <Link to="/catalog/jain_sarees" className="text-sm text-white/70 hover:text-white transition-colors">
                  Jain Sarees
                </Link>
              </li>
              <li>
                <Link to="/catalog/whisked_words" className="text-sm text-white/70 hover:text-white transition-colors">
                  Whisked Words
                </Link>
              </li>
            </ul>
          </div>

          {/* Quick Links */}
          <div>
            <h4 className="text-sm font-bold tracking-wide uppercase mb-4">Quick Links</h4>
            <ul className="space-y-2">
              <li>
                <Link to="/" className="text-sm text-white/70 hover:text-white transition-colors">
                  Home
                </Link>
              </li>
              <li>
                <Link to="/businesses" className="text-sm text-white/70 hover:text-white transition-colors">
                  All Businesses
                </Link>
              </li>
              <li>
                <Link to="/login" className="text-sm text-white/70 hover:text-white transition-colors">
                  Admin Login
                </Link>
              </li>
            </ul>
          </div>

          {/* Legal */}
          <div>
            <h4 className="text-sm font-bold tracking-wide uppercase mb-4">Legal</h4>
            <ul className="space-y-2">
              <li>
                <span className="text-sm text-white/70">Privacy Policy</span>
              </li>
              <li>
                <span className="text-sm text-white/70">Terms of Service</span>
              </li>
              <li>
                <span className="text-sm text-white/70">Contact Us</span>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-12 pt-8 border-t border-white/20">
          <p className="text-sm text-white/70 text-center">
            © {new Date().getFullYear()} Multi-Business Platform. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;