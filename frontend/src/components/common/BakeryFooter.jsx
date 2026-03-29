import { Link } from 'react-router-dom';

const BakeryFooter = () => {
  return (
    <footer className="bg-[#2C2420] text-[#FAF8F5] py-20 mt-auto" data-testid="bakery-footer">
      <div className="max-w-7xl mx-auto px-6 md:px-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-12">
          {/* Brand */}
          <div className="md:col-span-1">
            <h3 className="font-serif text-2xl font-bold italic mb-4">Whisked Words</h3>
            <p className="text-sm text-[#FAF8F5]/60 leading-relaxed">
              Artisan bakery crafting fresh pastries, custom cakes, and heartfelt confections since 2020.
            </p>
          </div>

          {/* Shop */}
          <div>
            <h4 className="text-xs tracking-[0.2em] uppercase font-semibold text-[#D4A373] mb-6">Shop</h4>
            <ul className="space-y-3">
              <li><Link to="/business/whisked_words/catalog" className="text-sm text-[#FAF8F5]/60 hover:text-[#D4A373] transition-colors">All Products</Link></li>
              <li><Link to="/business/whisked_words/custom-order" className="text-sm text-[#FAF8F5]/60 hover:text-[#D4A373] transition-colors">Custom Cakes</Link></li>
              <li><Link to="/subscriptions" className="text-sm text-[#FAF8F5]/60 hover:text-[#D4A373] transition-colors">Subscriptions</Link></li>
            </ul>
          </div>

          {/* Account */}
          <div>
            <h4 className="text-xs tracking-[0.2em] uppercase font-semibold text-[#D4A373] mb-6">Account</h4>
            <ul className="space-y-3">
              <li><Link to="/my-orders" className="text-sm text-[#FAF8F5]/60 hover:text-[#D4A373] transition-colors">My Orders</Link></li>
              <li><Link to="/loyalty" className="text-sm text-[#FAF8F5]/60 hover:text-[#D4A373] transition-colors">Rewards</Link></li>
              <li><Link to="/cart" className="text-sm text-[#FAF8F5]/60 hover:text-[#D4A373] transition-colors">Cart</Link></li>
            </ul>
          </div>

          {/* Jain Industries */}
          <div>
            <h4 className="text-xs tracking-[0.2em] uppercase font-semibold text-[#D4A373] mb-6">Jain Industries</h4>
            <ul className="space-y-3">
              <li><Link to="/businesses" className="text-sm text-[#FAF8F5]/60 hover:text-[#D4A373] transition-colors">All Businesses</Link></li>
              <li><Link to="/" className="text-sm text-[#FAF8F5]/60 hover:text-[#D4A373] transition-colors">Home</Link></li>
            </ul>
          </div>
        </div>

        <div className="mt-16 pt-8 border-t border-[#FAF8F5]/10 text-center">
          <p className="text-xs text-[#FAF8F5]/40 tracking-wide">
            &copy; {new Date().getFullYear()} Whisked Words &mdash; A Jain Industries Brand. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  );
};

export default BakeryFooter;
