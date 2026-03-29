import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import BakeryNavbar from '../components/common/BakeryNavbar';
import BakeryFooter from '../components/common/BakeryFooter';
import apiClient from '../utils/api';
import { Award, ArrowUp, ArrowDown, Star, Gift, TrendingUp } from 'lucide-react';

const tierConfig = {
  bronze: { bg: 'bg-[#A67C52]', text: 'text-[#A67C52]', label: 'Bronze', next: 'silver', pointsNeeded: 2000 },
  silver: { bg: 'bg-[#9CA3AF]', text: 'text-[#9CA3AF]', label: 'Silver', next: 'gold', pointsNeeded: 5000 },
  gold: { bg: 'bg-[#D4AF37]', text: 'text-[#D4AF37]', label: 'Gold', next: 'platinum', pointsNeeded: 10000 },
  platinum: { bg: 'bg-[#78716C]', text: 'text-[#78716C]', label: 'Platinum', next: null, pointsNeeded: null }
};

const LoyaltyPage = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [loyalty, setLoyalty] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) { navigate('/login'); return; }
    const fetchData = async () => {
      try {
        const [loyaltyRes, txnRes] = await Promise.all([apiClient.get('/loyalty/points'), apiClient.get('/loyalty/transactions')]);
        setLoyalty(loyaltyRes.data); setTransactions(txnRes.data.transactions);
      } catch (error) { console.error('Error:', error); }
      finally { setLoading(false); }
    };
    fetchData();
  }, [isAuthenticated, navigate]);

  if (loading) {
    return (<div className="min-h-screen flex flex-col bg-[#FAF8F5]"><BakeryNavbar /><div className="flex-1 flex items-center justify-center"><div className="w-12 h-12 border-4 border-[#4A3B32] border-t-transparent rounded-full animate-spin" /></div></div>);
  }

  const tier = tierConfig[loyalty?.tier || 'bronze'];
  const progressToNext = tier.pointsNeeded ? Math.min(((loyalty?.total_earned || 0) / tier.pointsNeeded) * 100, 100) : 100;

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5]" data-testid="loyalty-page">
      <BakeryNavbar />

      <main className="flex-1 py-16 md:py-24">
        <div className="max-w-4xl mx-auto px-6 md:px-12">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <p className="text-xs tracking-[0.2em] uppercase text-[#D4A373] font-semibold mb-2">Your Rewards</p>
            <h1 className="font-serif text-4xl md:text-5xl text-[#2C2420] mb-12">Loyalty Program</h1>
          </motion.div>

          {/* Points Overview */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="bg-white border border-[#E8E0D5] p-8" data-testid="current-points-card">
              <div className="flex items-center gap-3 mb-4"><div className="w-10 h-10 bg-[#4A3B32] flex items-center justify-center"><Award size={20} className="text-white" strokeWidth={1.5} /></div></div>
              <p className="font-serif text-4xl text-[#2C2420] mb-1">{loyalty?.points || 0}</p>
              <p className="text-xs tracking-[0.15em] uppercase text-[#786A60] font-semibold">Available Points</p>
            </motion.div>
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }} className="bg-white border border-[#E8E0D5] p-8" data-testid="total-earned-card">
              <div className="flex items-center gap-3 mb-4"><div className="w-10 h-10 bg-[#D4A373] flex items-center justify-center"><TrendingUp size={20} className="text-white" strokeWidth={1.5} /></div></div>
              <p className="font-serif text-4xl text-[#2C2420] mb-1">{loyalty?.total_earned || 0}</p>
              <p className="text-xs tracking-[0.15em] uppercase text-[#786A60] font-semibold">Total Earned</p>
            </motion.div>
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="bg-white border border-[#E8E0D5] p-8" data-testid="current-tier-card">
              <div className="flex items-center gap-3 mb-4"><div className={`w-10 h-10 ${tier.bg} flex items-center justify-center`}><Star size={20} className="text-white" strokeWidth={1.5} /></div></div>
              <p className={`font-serif text-3xl ${tier.text} mb-1`}>{tier.label}</p>
              <p className="text-xs tracking-[0.15em] uppercase text-[#786A60] font-semibold">Current Tier</p>
            </motion.div>
          </div>

          {/* Progress Bar */}
          {tier.next && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.25 }} className="bg-white border border-[#E8E0D5] p-8 mb-12" data-testid="tier-progress">
              <h2 className="font-serif text-xl text-[#2C2420] mb-4">Progress to {tierConfig[tier.next].label}</h2>
              <div className="w-full bg-[#F3EFEA] h-2 mb-3">
                <div className="bg-[#D4A373] h-2 transition-all duration-700" style={{ width: `${progressToNext}%` }} data-testid="tier-progress-bar" />
              </div>
              <p className="text-sm text-[#786A60]">{loyalty?.total_earned || 0} / {tier.pointsNeeded} points <span className="ml-1 text-[#D4A373]">({Math.max(0, tier.pointsNeeded - (loyalty?.total_earned || 0))} to go)</span></p>
            </motion.div>
          )}

          {/* How to Earn */}
          <div className="bg-white border border-[#E8E0D5] p-8 mb-12" data-testid="how-to-earn">
            <h2 className="font-serif text-xl text-[#2C2420] mb-6">How to Earn Points</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {[
                { icon: Gift, title: 'Shop & Earn', desc: '10% of order value as points on every purchase' },
                { icon: Star, title: 'Write Reviews', desc: '50 points for every product review you write' },
                { icon: Award, title: 'Tier Benefits', desc: 'Higher tiers unlock exclusive discounts and perks' }
              ].map(({ icon: Icon, title, desc }) => (
                <div key={title} className="p-5 bg-[#FAF8F5]">
                  <Icon size={22} className="text-[#D4A373] mb-3" strokeWidth={1.5} />
                  <p className="font-semibold text-[#2C2420] text-sm mb-1">{title}</p>
                  <p className="text-xs text-[#786A60] leading-relaxed">{desc}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Tier Benefits Table */}
          <div className="bg-white border border-[#E8E0D5] p-8 mb-12" data-testid="tier-benefits">
            <h2 className="font-serif text-xl text-[#2C2420] mb-6">Tier Benefits</h2>
            <div className="grid grid-cols-4 gap-4">
              {Object.entries(tierConfig).map(([key, config]) => (
                <div key={key} className={`p-5 ${loyalty?.tier === key ? 'bg-[#FAF8F5]' : ''} border-t-4 ${config.bg.replace('bg-', 'border-')}`}>
                  <p className={`font-serif text-lg ${config.text} mb-3`}>{config.label}{loyalty?.tier === key && <span className="text-xs ml-1">(You)</span>}</p>
                  <div className="space-y-2 text-xs text-[#786A60]">
                    <p>{config.pointsNeeded ? `${config.pointsNeeded.toLocaleString()}+ pts` : '10,000+ pts'}</p>
                    <p className="font-semibold text-[#2C2420]">{key === 'bronze' ? '0%' : key === 'silver' ? '5%' : key === 'gold' ? '10%' : '15%'} off</p>
                    <p>{key === 'gold' || key === 'platinum' ? 'Free delivery' : 'Standard delivery'}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Transaction History */}
          <div className="bg-white border border-[#E8E0D5]" data-testid="transactions-section">
            <div className="p-8 border-b border-[#E8E0D5]">
              <h2 className="font-serif text-xl text-[#2C2420]">Points History</h2>
            </div>
            {transactions.length === 0 ? (
              <div className="p-16 text-center">
                <Award size={48} className="mx-auto text-[#786A60] mb-4" strokeWidth={1} />
                <p className="text-[#786A60] font-serif">Start shopping to earn points!</p>
              </div>
            ) : (
              <div>
                {transactions.map((txn) => (
                  <div key={txn.transaction_id} className="px-8 py-5 border-b border-[#E8E0D5] last:border-0 flex items-center justify-between hover:bg-[#FAF8F5] transition-colors" data-testid={`transaction-${txn.transaction_id}`}>
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 flex items-center justify-center ${txn.type === 'earned' ? 'bg-[#A3B18A]/20' : 'bg-red-50'}`}>
                        {txn.type === 'earned' ? <ArrowUp size={14} className="text-[#A3B18A]" /> : <ArrowDown size={14} className="text-red-500" />}
                      </div>
                      <div>
                        <p className="text-sm font-medium text-[#2C2420]">{txn.reason}</p>
                        <p className="text-xs text-[#786A60]">{new Date(txn.created_at).toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' })}</p>
                      </div>
                    </div>
                    <span className={`font-semibold text-sm ${txn.type === 'earned' ? 'text-[#A3B18A]' : 'text-red-500'}`}>{txn.type === 'earned' ? '+' : '-'}{txn.points} pts</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </main>

      <BakeryFooter />
    </div>
  );
};

export default LoyaltyPage;
