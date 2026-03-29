import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import BakeryNavbar from '../components/common/BakeryNavbar';
import BakeryFooter from '../components/common/BakeryFooter';
import apiClient from '../utils/api';
import { toast } from 'sonner';
import { Star, MessageSquare, Award, ArrowLeft } from 'lucide-react';

const StarRating = ({ rating, onRate, interactive = false, size = 20 }) => {
  const [hover, setHover] = useState(0);
  return (
    <div className="flex items-center gap-1" data-testid="star-rating">
      {[1, 2, 3, 4, 5].map((star) => (
        <button key={star} type="button" disabled={!interactive} onClick={() => interactive && onRate(star)} onMouseEnter={() => interactive && setHover(star)} onMouseLeave={() => interactive && setHover(0)} className={`${interactive ? 'cursor-pointer' : 'cursor-default'} transition-colors`} data-testid={`star-${star}`}>
          <Star size={size} className={star <= (hover || rating) ? 'fill-[#D4A373] text-[#D4A373]' : 'text-[#E8E0D5]'} />
        </button>
      ))}
    </div>
  );
};

const ReviewsPage = () => {
  const { productId } = useParams();
  const { isAuthenticated } = useAuth();
  const [product, setProduct] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [avgRating, setAvgRating] = useState(0);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({ rating: 0, comment: '' });

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [productRes, reviewsRes] = await Promise.all([
          productId ? apiClient.get(`/products/${productId}`) : Promise.resolve(null),
          productId ? apiClient.get(`/reviews/product/${productId}`) : Promise.resolve(null)
        ]);
        if (productRes) setProduct(productRes.data);
        if (reviewsRes) { setReviews(reviewsRes.data.reviews); setAvgRating(reviewsRes.data.average_rating); }
      } catch (error) { console.error('Error fetching reviews:', error); }
      finally { setLoading(false); }
    };
    fetchData();
  }, [productId]);

  const handleSubmitReview = async (e) => {
    e.preventDefault();
    if (formData.rating === 0) { toast.error('Please select a rating'); return; }
    setSubmitting(true);
    try {
      await apiClient.post('/reviews/create', { product_id: productId, rating: formData.rating, comment: formData.comment });
      toast.success('Review submitted! You earned 50 loyalty points.');
      setFormData({ rating: 0, comment: '' }); setShowForm(false);
      const reviewsRes = await apiClient.get(`/reviews/product/${productId}`);
      setReviews(reviewsRes.data.reviews); setAvgRating(reviewsRes.data.average_rating);
    } catch (error) { toast.error(error.response?.data?.detail || 'Failed to submit review'); }
    finally { setSubmitting(false); }
  };

  if (loading) {
    return (<div className="min-h-screen flex flex-col bg-[#FAF8F5]"><BakeryNavbar /><div className="flex-1 flex items-center justify-center"><div className="w-12 h-12 border-4 border-[#4A3B32] border-t-transparent rounded-full animate-spin" /></div></div>);
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5]" data-testid="reviews-page">
      <BakeryNavbar />

      <main className="flex-1 py-16 md:py-24">
        <div className="max-w-4xl mx-auto px-6 md:px-12">
          <Link to="/business/whisked_words/catalog" className="inline-flex items-center gap-2 text-xs tracking-[0.1em] uppercase text-[#D4A373] hover:text-[#4A3B32] font-semibold transition-colors mb-10" data-testid="back-to-catalog">
            <ArrowLeft size={14} /> Back to Shop
          </Link>

          {product && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex gap-8 items-start mb-12" data-testid="review-product-header">
              <div className="w-28 h-28 bg-[#F3EFEA] overflow-hidden flex-shrink-0">
                {product.images?.[0]?.url ? <img src={product.images[0].url} alt={product.product_name} className="w-full h-full object-cover" /> : <div className="w-full h-full flex items-center justify-center text-[#786A60]"><MessageSquare size={32} /></div>}
              </div>
              <div>
                <h1 className="font-serif text-3xl md:text-4xl text-[#2C2420] mb-2">{product.product_name}</h1>
                <div className="flex items-center gap-3">
                  <StarRating rating={Math.round(avgRating)} size={18} />
                  <span className="text-sm font-semibold text-[#2C2420]">{avgRating.toFixed(1)}</span>
                  <span className="text-sm text-[#786A60]">({reviews.length} {reviews.length === 1 ? 'review' : 'reviews'})</span>
                </div>
              </div>
            </motion.div>
          )}

          {/* Write Review */}
          {isAuthenticated && productId && (
            <div className="mb-12">
              {!showForm ? (
                <button onClick={() => setShowForm(true)} className="bg-[#4A3B32] text-white px-8 py-4 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#332822] transition-colors duration-300 flex items-center gap-2" data-testid="write-review-button">
                  <Star size={16} /> Write a Review
                </button>
              ) : (
                <motion.form initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} onSubmit={handleSubmitReview} className="bg-white border border-[#E8E0D5] p-8" data-testid="review-form">
                  <h3 className="font-serif text-xl text-[#2C2420] mb-6">Your Review</h3>
                  <div className="mb-5">
                    <label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Rating *</label>
                    <StarRating rating={formData.rating} onRate={(r) => setFormData(prev => ({ ...prev, rating: r }))} interactive size={28} />
                  </div>
                  <div className="mb-5">
                    <label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Comment</label>
                    <textarea value={formData.comment} onChange={(e) => setFormData(prev => ({ ...prev, comment: e.target.value }))} rows="4" placeholder="Share your experience..." className="w-full border border-[#E8E0D5] px-4 py-3 focus:ring-1 focus:ring-[#4A3B32] focus:border-[#4A3B32] transition-all outline-none resize-none bg-white text-[#2C2420]" data-testid="review-comment-input" />
                  </div>
                  <div className="flex items-center gap-2 text-xs text-[#A3B18A] mb-6"><Award size={14} /><span>Earn 50 loyalty points for your review</span></div>
                  <div className="flex gap-3">
                    <button type="submit" disabled={submitting} className="bg-[#4A3B32] text-white px-8 py-4 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#332822] transition-colors duration-300 disabled:opacity-50" data-testid="submit-review-button">{submitting ? 'Submitting...' : 'Submit Review'}</button>
                    <button type="button" onClick={() => { setShowForm(false); setFormData({ rating: 0, comment: '' }); }} className="bg-transparent border border-[#E8E0D5] text-[#4A3B32] px-8 py-4 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#F3EFEA] transition-colors duration-300" data-testid="cancel-review-button">Cancel</button>
                  </div>
                </motion.form>
              )}
            </div>
          )}

          {/* Reviews List */}
          <div data-testid="reviews-list">
            <h2 className="font-serif text-2xl text-[#2C2420] mb-8">{reviews.length > 0 ? `Reviews (${reviews.length})` : 'No Reviews Yet'}</h2>
            {reviews.length === 0 ? (
              <div className="bg-white border border-[#E8E0D5] p-16 text-center">
                <MessageSquare size={48} className="mx-auto text-[#786A60] mb-4" strokeWidth={1} />
                <p className="text-[#786A60] font-serif text-lg">Be the first to review this product</p>
              </div>
            ) : (
              <div className="space-y-6">
                {reviews.map((review, i) => (
                  <motion.div key={review.review_id} initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }} className="bg-white border border-[#E8E0D5] p-6" data-testid={`review-${review.review_id}`}>
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-[#F3EFEA] flex items-center justify-center font-serif text-[#4A3B32] font-bold">{review.user_name?.charAt(0)?.toUpperCase() || 'A'}</div>
                        <div>
                          <p className="font-semibold text-[#2C2420] text-sm">{review.user_name}</p>
                          <p className="text-xs text-[#786A60]">{new Date(review.created_at).toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' })}</p>
                        </div>
                      </div>
                      <StarRating rating={review.rating} size={14} />
                    </div>
                    {review.comment && <p className="text-sm text-[#786A60] leading-relaxed">{review.comment}</p>}
                  </motion.div>
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

export default ReviewsPage;
