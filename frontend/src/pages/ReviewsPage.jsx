import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Navbar from '../components/common/Navbar';
import apiClient from '../utils/api';
import { toast } from 'sonner';
import { Star, MessageSquare, Award, ArrowLeft } from 'lucide-react';

const StarRating = ({ rating, onRate, interactive = false, size = 20 }) => {
  const [hover, setHover] = useState(0);

  return (
    <div className="flex items-center gap-1" data-testid="star-rating">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          disabled={!interactive}
          onClick={() => interactive && onRate(star)}
          onMouseEnter={() => interactive && setHover(star)}
          onMouseLeave={() => interactive && setHover(0)}
          className={`${interactive ? 'cursor-pointer' : 'cursor-default'} transition-colors`}
          data-testid={`star-${star}`}
        >
          <Star
            size={size}
            className={`${
              star <= (hover || rating)
                ? 'fill-yellow-400 text-yellow-400'
                : 'text-border'
            }`}
          />
        </button>
      ))}
    </div>
  );
};

const ReviewsPage = () => {
  const { productId } = useParams();
  const { user, isAuthenticated } = useAuth();
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
        if (reviewsRes) {
          setReviews(reviewsRes.data.reviews);
          setAvgRating(reviewsRes.data.average_rating);
        }
      } catch (error) {
        console.error('Error fetching reviews:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [productId]);

  const handleSubmitReview = async (e) => {
    e.preventDefault();

    if (formData.rating === 0) {
      toast.error('Please select a rating');
      return;
    }

    setSubmitting(true);
    try {
      await apiClient.post('/reviews/create', {
        product_id: productId,
        rating: formData.rating,
        comment: formData.comment
      });

      toast.success('Review submitted! You earned 50 loyalty points.');
      setFormData({ rating: 0, comment: '' });
      setShowForm(false);

      // Refresh reviews
      const reviewsRes = await apiClient.get(`/reviews/product/${productId}`);
      setReviews(reviewsRes.data.reviews);
      setAvgRating(reviewsRes.data.average_rating);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to submit review');
    } finally {
      setSubmitting(false);
    }
  };

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

  return (
    <div className="min-h-screen flex flex-col bg-surface" data-testid="reviews-page">
      <Navbar />

      <main className="flex-1 py-12">
        <div className="max-w-4xl mx-auto px-8">
          {/* Back Link */}
          {productId && (
            <Link
              to={`/business/whisked_words/catalog`}
              className="inline-flex items-center gap-2 text-sm text-muted hover:text-primary transition-colors mb-8"
              data-testid="back-to-catalog"
            >
              <ArrowLeft size={16} />
              Back to Catalog
            </Link>
          )}

          {/* Product Header */}
          {product && (
            <div className="bg-white border border-border p-6 mb-8 flex gap-6" data-testid="review-product-header">
              <div className="w-24 h-24 bg-surface flex-shrink-0 overflow-hidden">
                {product.images?.[0]?.url ? (
                  <img src={product.images[0].url} alt={product.product_name} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-muted">
                    <MessageSquare size={32} />
                  </div>
                )}
              </div>
              <div>
                <h1 className="text-2xl font-black text-primary uppercase mb-2">{product.product_name}</h1>
                <div className="flex items-center gap-3">
                  <StarRating rating={Math.round(avgRating)} size={18} />
                  <span className="text-sm font-semibold text-primary">{avgRating.toFixed(1)}</span>
                  <span className="text-sm text-muted">({reviews.length} {reviews.length === 1 ? 'review' : 'reviews'})</span>
                </div>
              </div>
            </div>
          )}

          {/* Write Review Button / Form */}
          {isAuthenticated && productId && (
            <div className="mb-8">
              {!showForm ? (
                <button
                  onClick={() => setShowForm(true)}
                  className="bg-accent text-white hover:bg-[#002280] transition-all border border-accent px-6 py-3 font-bold tracking-wide flex items-center gap-2"
                  data-testid="write-review-button"
                >
                  <Star size={18} />
                  WRITE A REVIEW
                </button>
              ) : (
                <form onSubmit={handleSubmitReview} className="bg-white border border-border p-6" data-testid="review-form">
                  <h3 className="text-lg font-bold text-primary mb-4">YOUR REVIEW</h3>

                  <div className="mb-4">
                    <label className="block text-sm font-medium text-primary mb-2">Rating *</label>
                    <StarRating
                      rating={formData.rating}
                      onRate={(r) => setFormData(prev => ({ ...prev, rating: r }))}
                      interactive
                      size={28}
                    />
                  </div>

                  <div className="mb-4">
                    <label className="block text-sm font-medium text-primary mb-2">Comment</label>
                    <textarea
                      value={formData.comment}
                      onChange={(e) => setFormData(prev => ({ ...prev, comment: e.target.value }))}
                      rows="4"
                      placeholder="Share your experience with this product..."
                      className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none resize-none"
                      data-testid="review-comment-input"
                    />
                  </div>

                  <div className="flex items-center gap-2 text-xs text-muted mb-4">
                    <Award size={14} />
                    <span>Earn 50 loyalty points for your review</span>
                  </div>

                  <div className="flex gap-3">
                    <button
                      type="submit"
                      disabled={submitting}
                      className="bg-primary text-white hover:bg-[#333333] transition-all border border-primary px-6 py-3 font-bold tracking-wide disabled:opacity-50"
                      data-testid="submit-review-button"
                    >
                      {submitting ? 'SUBMITTING...' : 'SUBMIT REVIEW'}
                    </button>
                    <button
                      type="button"
                      onClick={() => { setShowForm(false); setFormData({ rating: 0, comment: '' }); }}
                      className="bg-transparent text-primary hover:bg-secondary transition-all border border-border px-6 py-3 font-bold tracking-wide"
                      data-testid="cancel-review-button"
                    >
                      CANCEL
                    </button>
                  </div>
                </form>
              )}
            </div>
          )}

          {/* Reviews List */}
          <div data-testid="reviews-list">
            <h2 className="text-xl font-bold text-primary mb-6">
              {reviews.length > 0 ? `REVIEWS (${reviews.length})` : 'NO REVIEWS YET'}
            </h2>

            {reviews.length === 0 ? (
              <div className="bg-white border border-border p-12 text-center">
                <MessageSquare size={48} className="mx-auto text-muted mb-4" strokeWidth={1.5} />
                <p className="text-muted">Be the first to review this product!</p>
              </div>
            ) : (
              <div className="space-y-4">
                {reviews.map((review) => (
                  <div
                    key={review.review_id}
                    className="bg-white border border-border p-6"
                    data-testid={`review-${review.review_id}`}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <p className="font-semibold text-primary">{review.user_name}</p>
                        <p className="text-xs text-muted">
                          {new Date(review.created_at).toLocaleDateString('en-IN', {
                            year: 'numeric', month: 'short', day: 'numeric'
                          })}
                        </p>
                      </div>
                      <StarRating rating={review.rating} size={16} />
                    </div>
                    {review.comment && (
                      <p className="text-sm text-primary leading-relaxed">{review.comment}</p>
                    )}
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

export default ReviewsPage;
