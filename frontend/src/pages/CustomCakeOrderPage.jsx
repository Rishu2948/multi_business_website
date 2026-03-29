import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import apiClient from '../utils/api';
import { toast } from 'sonner';
import { ChevronRight, ChevronLeft, Cake, Calendar, MapPin } from 'lucide-react';

const CustomCakeOrderPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);

  const [formData, setFormData] = useState({
    // Step 1: Cake Details
    cake_type: 'regular',
    weight: '500g',
    flavor: 'chocolate',
    shape: 'round',
    message_on_cake: '',
    special_instructions: '',
    image_reference_url: '',
    
    // Step 2: Delivery
    delivery_date: '',
    delivery_time: '',
    
    // Step 3: Contact
    name: user?.name || '',
    phone: '',
    email: user?.email || '',
    address: '',
    city: '',
    state: '',
    pincode: ''
  });

  const cakeTypes = ['Regular Cake', 'Photo Cake', 'Designer Cake', 'Wedding Cake', 'Birthday Cake'];
  const weights = ['500g', '1kg', '1.5kg', '2kg', '3kg', '5kg'];
  const flavors = ['Chocolate', 'Vanilla', 'Strawberry', 'Butterscotch', 'Red Velvet', 'Black Forest', 'Pineapple', 'Mango'];
  const shapes = ['Round', 'Square', 'Rectangle', 'Heart', 'Custom'];

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleNext = () => {
    if (step === 1) {
      if (!formData.cake_type || !formData.weight || !formData.flavor || !formData.shape) {
        toast.error('Please fill all cake details');
        return;
      }
    } else if (step === 2) {
      if (!formData.delivery_date || !formData.delivery_time) {
        toast.error('Please select delivery date and time');
        return;
      }
    }
    setStep(step + 1);
  };

  const handleBack = () => {
    setStep(step - 1);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.name || !formData.phone || !formData.email || !formData.address || !formData.city || !formData.state || !formData.pincode) {
      toast.error('Please fill all delivery information');
      return;
    }

    setLoading(true);
    try {
      // Get a cake product (using first product from whisked_words as base)
      const productsRes = await apiClient.get('/products?business_id=whisked_words&limit=1');
      const productId = productsRes.data.products[0]?.product_id;

      if (!productId) {
        toast.error('Unable to create custom order. Please try again.');
        setLoading(false);
        return;
      }

      const customOrderData = {
        product_id: productId,
        cake_type: formData.cake_type,
        weight: formData.weight,
        flavor: formData.flavor,
        shape: formData.shape,
        message_on_cake: formData.message_on_cake,
        special_instructions: formData.special_instructions,
        image_reference_url: formData.image_reference_url,
        delivery_date: formData.delivery_date,
        delivery_time: formData.delivery_time,
        delivery_info: {
          name: formData.name,
          phone: formData.phone,
          email: formData.email,
          address: formData.address,
          city: formData.city,
          state: formData.state,
          pincode: formData.pincode
        }
      };

      const response = await apiClient.post('/custom-orders/create', customOrderData);
      
      toast.success('Custom cake order request submitted! We will contact you with a quote.');
      setTimeout(() => {
        navigate('/my-orders');
      }, 2000);
    } catch (error) {
      console.error('Error creating custom order:', error);
      toast.error(error.response?.data?.detail || 'Failed to create custom order');
    } finally {
      setLoading(false);
    }
  };

  const renderStep1 = () => (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-primary mb-2">CAKE DETAILS</h2>
        <p className="text-sm text-muted">Customize your perfect cake</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label className="block text-sm font-medium text-primary mb-2">Cake Type *</label>
          <select
            name="cake_type"
            value={formData.cake_type}
            onChange={handleChange}
            className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
            data-testid="cake-type"
          >
            {cakeTypes.map(type => (
              <option key={type} value={type.toLowerCase().replace(' ', '_')}>{type}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-primary mb-2">Weight *</label>
          <select
            name="weight"
            value={formData.weight}
            onChange={handleChange}
            className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
            data-testid="cake-weight"
          >
            {weights.map(weight => (
              <option key={weight} value={weight}>{weight}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-primary mb-2">Flavor *</label>
          <select
            name="flavor"
            value={formData.flavor}
            onChange={handleChange}
            className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
            data-testid="cake-flavor"
          >
            {flavors.map(flavor => (
              <option key={flavor} value={flavor.toLowerCase()}>{flavor}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-primary mb-2">Shape *</label>
          <select
            name="shape"
            value={formData.shape}
            onChange={handleChange}
            className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
            data-testid="cake-shape"
          >
            {shapes.map(shape => (
              <option key={shape} value={shape.toLowerCase()}>{shape}</option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-primary mb-2">Message on Cake (Optional)</label>
        <input
          type="text"
          name="message_on_cake"
          value={formData.message_on_cake}
          onChange={handleChange}
          placeholder="e.g., Happy Birthday!"
          maxLength="50"
          className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
          data-testid="cake-message"
        />
        <p className="text-xs text-muted mt-1">Max 50 characters</p>
      </div>

      <div>
        <label className="block text-sm font-medium text-primary mb-2">Reference Image URL (Optional)</label>
        <input
          type="url"
          name="image_reference_url"
          value={formData.image_reference_url}
          onChange={handleChange}
          placeholder="https://example.com/cake-design.jpg"
          className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
          data-testid="cake-image-url"
        />
        <p className="text-xs text-muted mt-1">Provide a URL to your desired cake design</p>
      </div>

      <div>
        <label className="block text-sm font-medium text-primary mb-2">Special Instructions (Optional)</label>
        <textarea
          name="special_instructions"
          value={formData.special_instructions}
          onChange={handleChange}
          rows="4"
          placeholder="Any specific requirements or allergies..."
          className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none resize-none"
          data-testid="cake-instructions"
        />
      </div>
    </div>
  );

  const renderStep2 = () => (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-primary mb-2">DELIVERY SCHEDULE</h2>
        <p className="text-sm text-muted">When do you need your cake?</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label className="block text-sm font-medium text-primary mb-2">Delivery Date *</label>
          <input
            type="date"
            name="delivery_date"
            value={formData.delivery_date}
            onChange={handleChange}
            min={new Date(Date.now() + 24*60*60*1000).toISOString().split('T')[0]}
            className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
            data-testid="delivery-date"
          />
          <p className="text-xs text-muted mt-1">Minimum 24 hours advance notice required</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-primary mb-2">Delivery Time *</label>
          <select
            name="delivery_time"
            value={formData.delivery_time}
            onChange={handleChange}
            className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
            data-testid="delivery-time"
          >
            <option value="">Select Time</option>
            <option value="morning">Morning (9 AM - 12 PM)</option>
            <option value="afternoon">Afternoon (12 PM - 4 PM)</option>
            <option value="evening">Evening (4 PM - 8 PM)</option>
          </select>
        </div>
      </div>
    </div>
  );

  const renderStep3 = () => (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-primary mb-2">DELIVERY INFORMATION</h2>
        <p className="text-sm text-muted">Where should we deliver your cake?</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label className="block text-sm font-medium text-primary mb-2">Full Name *</label>
          <input
            type="text"
            name="name"
            value={formData.name}
            onChange={handleChange}
            className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
            data-testid="contact-name"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-primary mb-2">Phone *</label>
          <input
            type="tel"
            name="phone"
            value={formData.phone}
            onChange={handleChange}
            placeholder="+91-XXXXXXXXXX"
            className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
            data-testid="contact-phone"
          />
        </div>

        <div className="md:col-span-2">
          <label className="block text-sm font-medium text-primary mb-2">Email *</label>
          <input
            type="email"
            name="email"
            value={formData.email}
            onChange={handleChange}
            className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
            data-testid="contact-email"
          />
        </div>

        <div className="md:col-span-2">
          <label className="block text-sm font-medium text-primary mb-2">Address *</label>
          <textarea
            name="address"
            value={formData.address}
            onChange={handleChange}
            rows="3"
            className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none resize-none"
            data-testid="contact-address"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-primary mb-2">City *</label>
          <input
            type="text"
            name="city"
            value={formData.city}
            onChange={handleChange}
            className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
            data-testid="contact-city"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-primary mb-2">State *</label>
          <input
            type="text"
            name="state"
            value={formData.state}
            onChange={handleChange}
            className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
            data-testid="contact-state"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-primary mb-2">Pincode *</label>
          <input
            type="text"
            name="pincode"
            value={formData.pincode}
            onChange={handleChange}
            pattern="[0-9]{6}"
            className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
            data-testid="contact-pincode"
          />
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-surface py-12" data-testid="custom-cake-order-page">
      <div className="max-w-4xl mx-auto px-8">
        {/* Header */}
        <div className="text-center mb-12">
          <Cake size={48} className="mx-auto text-primary mb-4" strokeWidth={1.5} />
          <h1 className="text-4xl font-black text-primary uppercase mb-2">CUSTOM CAKE ORDER</h1>
          <p className="text-base text-muted">Design your perfect cake in 3 easy steps</p>
        </div>

        {/* Progress Steps */}
        <div className="flex items-center justify-between mb-12">
          {[1, 2, 3].map((num) => (
            <div key={num} className="flex items-center flex-1">
              <div className="flex flex-col items-center flex-1">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${
                  step >= num ? 'bg-accent text-white' : 'bg-surface text-muted'
                }`}>
                  {num}
                </div>
                <p className={`text-xs mt-2 font-medium ${
                  step >= num ? 'text-primary' : 'text-muted'
                }`}>
                  {num === 1 ? 'CAKE DETAILS' : num === 2 ? 'DELIVERY' : 'CONTACT'}
                </p>
              </div>
              {num < 3 && (
                <div className={`h-1 flex-1 mx-2 ${
                  step > num ? 'bg-accent' : 'bg-surface'
                }`} />
              )}
            </div>
          ))}
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          <div className="bg-white border border-border p-8 mb-8">
            {step === 1 && renderStep1()}
            {step === 2 && renderStep2()}
            {step === 3 && renderStep3()}
          </div>

          {/* Navigation Buttons */}
          <div className="flex items-center justify-between">
            {step > 1 && (
              <button
                type="button"
                onClick={handleBack}
                className="bg-transparent text-primary hover:bg-secondary transition-all border border-border px-8 py-3 font-bold tracking-wide flex items-center gap-2"
                data-testid="back-button"
              >
                <ChevronLeft size={20} />
                BACK
              </button>
            )}
            
            <div className="flex-1" />

            {step < 3 ? (
              <button
                type="button"
                onClick={handleNext}
                className="bg-accent text-white hover:bg-[#002280] transition-all border border-accent px-8 py-3 font-bold tracking-wide flex items-center gap-2"
                data-testid="next-button"
              >
                NEXT
                <ChevronRight size={20} />
              </button>
            ) : (
              <button
                type="submit"
                disabled={loading}
                className="bg-primary text-white hover:bg-[#333333] transition-all border border-primary px-8 py-3 font-bold tracking-wide disabled:opacity-50"
                data-testid="submit-order-button"
              >
                {loading ? 'SUBMITTING...' : 'SUBMIT ORDER REQUEST'}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
};

export default CustomCakeOrderPage;