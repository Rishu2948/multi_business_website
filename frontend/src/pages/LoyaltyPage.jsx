import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Navbar from '../components/common/Navbar';
import apiClient from '../utils/api';
import { Award, ArrowUp, ArrowDown, Star, Gift, TrendingUp } from 'lucide-react';

const tierConfig = {
  bronze: { color: 'bg-amber-700', textColor: 'text-amber-700', label: 'BRONZE', next: 'silver', pointsNeeded: 2000 },
  silver: { color: 'bg-gray-400', textColor: 'text-gray-500', label: 'SILVER', next: 'gold', pointsNeeded: 5000 },
  gold: { color: 'bg-yellow-500', textColor: 'text-yellow-600', label: 'GOLD', next: 'platinum', pointsNeeded: 10000 },
  platinum: { color: 'bg-violet-600', textColor: 'text-violet-600', label: 'PLATINUM', next: null, pointsNeeded: null }
};

const LoyaltyPage = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [loyalty, setLoyalty] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }

    const fetchData = async () => {
      try {
        const [loyaltyRes, transactionsRes] = await Promise.all([
          apiClient.get('/loyalty/points'),
          apiClient.get('/loyalty/transactions')
        ]);
        setLoyalty(loyaltyRes.data);
        setTransactions(transactionsRes.data.transactions);
      } catch (error) {
        console.error('Error fetching loyalty data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [isAuthenticated, navigate]);

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col">
        <Navbar />
        <div className="flex-1 flex items-center justify-center">
          <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
        </div>
      </div>
    );
  }

  const tier = tierConfig[loyalty?.tier || 'bronze'];
  const progressToNext = tier.pointsNeeded
    ? Math.min(((loyalty?.total_earned || 0) / tier.pointsNeeded) * 100, 100)
    : 100;

  return (
    <div className="min-h-screen flex flex-col bg-surface" data-testid="loyalty-page">
      <Navbar />

      <main className="flex-1 py-12">
        <div className="max-w-4xl mx-auto px-8">
          <h1 className="text-4xl font-black text-primary uppercase mb-8">LOYALTY REWARDS</h1>

          {/* Points Overview */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            {/* Current Points */}
            <div className="bg-white border border-border p-6" data-testid="current-points-card">
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 bg-primary flex items-center justify-center">
                  <Award size={24} className="text-white" strokeWidth={1.5} />
                </div>
                <p className="text-3xl font-black text-primary">{loyalty?.points || 0}</p>
              </div>
              <p className="text-sm font-bold tracking-wide uppercase text-muted">AVAILABLE POINTS</p>
            </div>

            {/* Total Earned */}
            <div className="bg-white border border-border p-6" data-testid="total-earned-card">
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 bg-accent flex items-center justify-center">
                  <TrendingUp size={24} className="text-white" strokeWidth={1.5} />
                </div>
                <p className="text-3xl font-black text-primary">{loyalty?.total_earned || 0}</p>
              </div>
              <p className="text-sm font-bold tracking-wide uppercase text-muted">TOTAL EARNED</p>
            </div>

            {/* Current Tier */}
            <div className="bg-white border border-border p-6" data-testid="current-tier-card">
              <div className="flex items-center justify-between mb-4">
                <div className={`w-12 h-12 ${tier.color} flex items-center justify-center`}>
                  <Star size={24} className="text-white" strokeWidth={1.5} />
                </div>
                <p className={`text-2xl font-black ${tier.textColor}`}>{tier.label}</p>
              </div>
              <p className="text-sm font-bold tracking-wide uppercase text-muted">CURRENT TIER</p>
            </div>
          </div>

          {/* Tier Progress */}
          {tier.next && (
            <div className="bg-white border border-border p-6 mb-8" data-testid="tier-progress">
              <h2 className="text-lg font-bold text-primary mb-4">PROGRESS TO {tierConfig[tier.next].label}</h2>
              <div className="w-full bg-surface h-3 mb-2">
                <div
                  className="bg-accent h-3 transition-all duration-500"
                  style={{ width: `${progressToNext}%` }}
                  data-testid="tier-progress-bar"
                />
              </div>
              <p className="text-sm text-muted">
                {loyalty?.total_earned || 0} / {tier.pointsNeeded} points
                <span className="ml-2">({Math.max(0, tier.pointsNeeded - (loyalty?.total_earned || 0))} more to go)</span>
              </p>
            </div>
          )}

          {/* How to Earn Points */}
          <div className="bg-white border border-border p-6 mb-8" data-testid="how-to-earn">
            <h2 className="text-lg font-bold text-primary mb-4">HOW TO EARN POINTS</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 bg-surface">
                <Gift size={24} className="text-accent mb-2" strokeWidth={1.5} />
                <p className="font-semibold text-primary text-sm mb-1">Shop & Earn</p>
                <p className="text-xs text-muted">Earn 10% of order value as points on every purchase</p>
              </div>
              <div className="p-4 bg-surface">
                <Star size={24} className="text-accent mb-2" strokeWidth={1.5} />
                <p className="font-semibold text-primary text-sm mb-1">Write Reviews</p>
                <p className="text-xs text-muted">Earn 50 points for every product review</p>
              </div>
              <div className="p-4 bg-surface">
                <Award size={24} className="text-accent mb-2" strokeWidth={1.5} />
                <p className="font-semibold text-primary text-sm mb-1">Tier Benefits</p>
                <p className="text-xs text-muted">Higher tiers unlock exclusive discounts and perks</p>
              </div>
            </div>
          </div>

          {/* Tier Benefits */}
          <div className="bg-white border border-border p-6 mb-8" data-testid="tier-benefits">
            <h2 className="text-lg font-bold text-primary mb-4">TIER BENEFITS</h2>
            <div className="overflow-x-auto">
              <table className="w-full" data-testid="tier-table">
                <thead>
                  <tr className="border-b border-border bg-surface">
                    <th className="text-left p-3 text-xs font-bold tracking-wide uppercase text-muted">Tier</th>
                    <th className="text-center p-3 text-xs font-bold tracking-wide uppercase text-muted">Points Needed</th>
                    <th className="text-center p-3 text-xs font-bold tracking-wide uppercase text-muted">Discount</th>
                    <th className="text-center p-3 text-xs font-bold tracking-wide uppercase text-muted">Free Delivery</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(tierConfig).map(([key, config]) => (
                    <tr
                      key={key}
                      className={`border-b border-border ${loyalty?.tier === key ? 'bg-surface' : ''}`}
                    >
                      <td className="p-3">
                        <div className="flex items-center gap-2">
                          <div className={`w-3 h-3 ${config.color}`} />
                          <span className={`font-bold text-sm ${loyalty?.tier === key ? config.textColor : 'text-primary'}`}>
                            {config.label}
                            {loyalty?.tier === key && ' (You)'}
                          </span>
                        </div>
                      </td>
                      <td className="p-3 text-center text-sm text-muted">
                        {config.pointsNeeded ? `${config.pointsNeeded.toLocaleString()}+` : '10,000+'}
                      </td>
                      <td className="p-3 text-center text-sm font-semibold text-primary">
                        {key === 'bronze' ? '0%' : key === 'silver' ? '5%' : key === 'gold' ? '10%' : '15%'}
                      </td>
                      <td className="p-3 text-center text-sm text-muted">
                        {key === 'gold' || key === 'platinum' ? 'Yes' : 'No'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Transaction History */}
          <div className="bg-white border border-border" data-testid="transactions-section">
            <div className="p-6 border-b border-border">
              <h2 className="text-lg font-bold text-primary">POINTS HISTORY</h2>
            </div>

            {transactions.length === 0 ? (
              <div className="p-12 text-center">
                <Award size={48} className="mx-auto text-muted mb-4" strokeWidth={1.5} />
                <p className="text-muted">No points transactions yet. Start shopping to earn points!</p>
              </div>
            ) : (
              <div>
                {transactions.map((txn) => (
                  <div
                    key={txn.transaction_id}
                    className="p-4 border-b border-border last:border-0 flex items-center justify-between hover:bg-surface transition-colors"
                    data-testid={`transaction-${txn.transaction_id}`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 flex items-center justify-center ${
                        txn.type === 'earned' ? 'bg-green-100' : 'bg-red-100'
                      }`}>
                        {txn.type === 'earned' ? (
                          <ArrowUp size={16} className="text-green-600" />
                        ) : (
                          <ArrowDown size={16} className="text-red-600" />
                        )}
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-primary">{txn.reason}</p>
                        <p className="text-xs text-muted">
                          {new Date(txn.created_at).toLocaleDateString('en-IN', {
                            year: 'numeric', month: 'short', day: 'numeric'
                          })}
                        </p>
                      </div>
                    </div>
                    <span className={`font-bold ${
                      txn.type === 'earned' ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {txn.type === 'earned' ? '+' : '-'}{txn.points} pts
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};

export default LoyaltyPage;
