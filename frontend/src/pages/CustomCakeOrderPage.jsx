import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import BakeryNavbar from '../components/common/BakeryNavbar';
import BakeryFooter from '../components/common/BakeryFooter';
import apiClient from '../utils/api';
import { toast } from 'sonner';
import { Cake, ArrowRight, ArrowLeft, Check } from 'lucide-react';

const steps = ['Cake Details', 'Delivery', 'Contact'];

const CustomCakeOrderPage = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [currentStep, setCurrentStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [formData, setFormData] = useState({
    flavor: '', size: '', tiers: '1', message: '', dietary: [], shape: 'round',
    date: '', time: 'morning', occasion: '',
    name: '', phone: '', email: '', address: '', city: '', state: '', pincode: '', notes: ''
  });

  const inputClass = "w-full border border-[#E8E0D5] px-4 py-3 focus:ring-1 focus:ring-[#4A3B32] focus:border-[#4A3B32] transition-all outline-none bg-white text-[#2C2420]";

  const flavors = ['Vanilla', 'Chocolate', 'Red Velvet', 'Butterscotch', 'Pineapple', 'Black Forest', 'Strawberry', 'Mango'];
  const sizes = ['500g (Small)', '1kg (Regular)', '1.5kg (Medium)', '2kg (Large)', '3kg (Extra Large)'];
  const shapes = ['round', 'square', 'heart', 'rectangle'];
  const dietaryOptions = ['Eggless', 'Sugar-Free', 'Gluten-Free', 'Vegan'];

  const handleSubmit = async () => {
    if (!isAuthenticated) { toast.error('Please login first'); navigate('/login'); return; }
    if (!formData.flavor || !formData.size || !formData.date || !formData.name || !formData.phone || !formData.address) { toast.error('Please fill all required fields'); return; }
    setSubmitting(true);
    try {
      await apiClient.post('/custom-orders/create', {
        specifications: {
          flavor: formData.flavor, size: formData.size, tiers: parseInt(formData.tiers),
          message: formData.message, dietary: formData.dietary, shape: formData.shape, occasion: formData.occasion
        },
        delivery_date: formData.date, delivery_time: formData.time,
        delivery_info: { name: formData.name, phone: formData.phone, email: formData.email, address: formData.address, city: formData.city, state: formData.state, pincode: formData.pincode },
        notes: formData.notes
      });
      toast.success('Custom cake order placed!');
      navigate('/my-orders');
    } catch (error) { toast.error(error.response?.data?.detail || 'Failed to place order'); }
    finally { setSubmitting(false); }
  };

  const toggleDietary = (opt) => setFormData(p => ({ ...p, dietary: p.dietary.includes(opt) ? p.dietary.filter(d => d !== opt) : [...p.dietary, opt] }));

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5]" data-testid="custom-cake-order-page">
      <BakeryNavbar />

      <main className="flex-1 py-16 md:py-24">
        <div className="max-w-6xl mx-auto px-6 md:px-12">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">
            {/* Left: Sticky Image */}
            <div className="hidden lg:block lg:col-span-5">
              <div className="sticky top-28">
                <div className="aspect-[3/4] overflow-hidden mb-6">
                  <img
                    src="https://images.unsplash.com/photo-1693059740560-21151639561f?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzOTB8MHwxfHNlYXJjaHwzfHxjdXN0b20lMjBiaXJ0aGRheSUyMGNha2UlMjBiYWtlcnl8ZW58MHx8fHwxNzc3NjE4NjE3fDA&ixlib=rb-4.1.0&q=85"
                    alt="Custom Cake Showcase"
                    className="w-full h-full object-cover"
                  />
                </div>
                <p className="font-serif text-lg text-[#2C2420] italic text-center">Every cake tells a story</p>
              </div>
            </div>

            {/* Right: Form */}
            <div className="lg:col-span-7">
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
                <p className="text-xs tracking-[0.2em] uppercase text-[#D4A373] font-semibold mb-2">Made to Order</p>
                <h1 className="font-serif text-4xl md:text-5xl text-[#2C2420] mb-8 italic">Custom Cake</h1>
              </motion.div>

              {/* Steps */}
              <div className="flex items-center gap-4 mb-10">
                {steps.map((step, i) => (
                  <div key={step} className="flex items-center gap-2">
                    <div className={`w-8 h-8 flex items-center justify-center text-sm font-semibold transition-colors ${i <= currentStep ? 'bg-[#4A3B32] text-white' : 'bg-[#F3EFEA] text-[#786A60]'}`}>
                      {i < currentStep ? <Check size={14} /> : i + 1}
                    </div>
                    <span className={`text-xs tracking-[0.1em] uppercase font-semibold ${i <= currentStep ? 'text-[#2C2420]' : 'text-[#786A60]'}`}>{step}</span>
                    {i < steps.length - 1 && <div className={`w-12 h-[1px] ${i < currentStep ? 'bg-[#4A3B32]' : 'bg-[#E8E0D5]'}`} />}
                  </div>
                ))}
              </div>

              {/* Step 1: Cake Details */}
              {currentStep === 0 && (
                <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} className="space-y-6">
                  <div>
                    <label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-3">Flavor *</label>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                      {flavors.map(f => (
                        <button key={f} type="button" onClick={() => setFormData(p => ({ ...p, flavor: f }))} className={`py-3 px-4 text-sm border transition-all ${formData.flavor === f ? 'bg-[#4A3B32] text-white border-[#4A3B32]' : 'border-[#E8E0D5] text-[#4A3B32] hover:bg-[#FAF8F5]'}`} data-testid={`flavor-${f.toLowerCase()}`}>{f}</button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-3">Size *</label>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {sizes.map(s => (
                        <button key={s} type="button" onClick={() => setFormData(p => ({ ...p, size: s }))} className={`py-3 px-4 text-sm border text-left transition-all ${formData.size === s ? 'bg-[#4A3B32] text-white border-[#4A3B32]' : 'border-[#E8E0D5] text-[#4A3B32] hover:bg-[#FAF8F5]'}`} data-testid={`size-${s.split(' ')[0]}`}>{s}</button>
                      ))}
                    </div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Tiers</label><select value={formData.tiers} onChange={(e) => setFormData(p => ({ ...p, tiers: e.target.value }))} className={inputClass} data-testid="cake-tiers">{[1,2,3,4].map(t => <option key={t} value={t}>{t} Tier{t > 1 ? 's' : ''}</option>)}</select></div>
                    <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Shape</label><div className="flex gap-2">{shapes.map(s => (<button key={s} type="button" onClick={() => setFormData(p => ({ ...p, shape: s }))} className={`flex-1 py-3 text-xs uppercase tracking-wide border transition-all ${formData.shape === s ? 'bg-[#4A3B32] text-white border-[#4A3B32]' : 'border-[#E8E0D5] text-[#4A3B32] hover:bg-[#FAF8F5]'}`} data-testid={`shape-${s}`}>{s}</button>))}</div></div>
                  </div>
                  <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-3">Dietary Requirements</label><div className="flex flex-wrap gap-2">{dietaryOptions.map(d => (<button key={d} type="button" onClick={() => toggleDietary(d)} className={`px-4 py-2 text-xs font-semibold border transition-all ${formData.dietary.includes(d) ? 'bg-[#A3B18A] text-white border-[#A3B18A]' : 'border-[#E8E0D5] text-[#4A3B32] hover:bg-[#FAF8F5]'}`} data-testid={`dietary-${d.toLowerCase()}`}>{d}</button>))}</div></div>
                  <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Cake Message</label><input type="text" value={formData.message} onChange={(e) => setFormData(p => ({ ...p, message: e.target.value }))} placeholder="Happy Birthday, Sarah!" className={inputClass} data-testid="cake-message" /></div>
                  <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Occasion</label><input type="text" value={formData.occasion} onChange={(e) => setFormData(p => ({ ...p, occasion: e.target.value }))} placeholder="Birthday, Wedding, Anniversary..." className={inputClass} data-testid="cake-occasion" /></div>
                </motion.div>
              )}

              {/* Step 2: Delivery */}
              {currentStep === 1 && (
                <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} className="space-y-6">
                  <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Delivery Date *</label><input type="date" value={formData.date} onChange={(e) => setFormData(p => ({ ...p, date: e.target.value }))} min={new Date(Date.now() + 2*86400000).toISOString().split('T')[0]} className={`${inputClass} max-w-xs`} data-testid="delivery-date" /></div>
                  <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Preferred Time</label><select value={formData.time} onChange={(e) => setFormData(p => ({ ...p, time: e.target.value }))} className={inputClass} data-testid="delivery-time"><option value="morning">Morning (9 AM – 12 PM)</option><option value="afternoon">Afternoon (12 – 4 PM)</option><option value="evening">Evening (4 – 8 PM)</option></select></div>
                  <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Special Instructions</label><textarea value={formData.notes} onChange={(e) => setFormData(p => ({ ...p, notes: e.target.value }))} rows="3" placeholder="Any special requirements..." className={`${inputClass} resize-none`} data-testid="special-notes" /></div>
                </motion.div>
              )}

              {/* Step 3: Contact */}
              {currentStep === 2 && (
                <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Name *</label><input type="text" value={formData.name} onChange={(e) => setFormData(p => ({ ...p, name: e.target.value }))} className={inputClass} data-testid="contact-name" /></div>
                    <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Phone *</label><input type="tel" value={formData.phone} onChange={(e) => setFormData(p => ({ ...p, phone: e.target.value }))} className={inputClass} data-testid="contact-phone" /></div>
                    <div className="md:col-span-2"><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Email</label><input type="email" value={formData.email} onChange={(e) => setFormData(p => ({ ...p, email: e.target.value }))} className={inputClass} data-testid="contact-email" /></div>
                    <div className="md:col-span-2"><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Address *</label><textarea value={formData.address} onChange={(e) => setFormData(p => ({ ...p, address: e.target.value }))} rows="2" className={`${inputClass} resize-none`} data-testid="contact-address" /></div>
                    <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">City *</label><input type="text" value={formData.city} onChange={(e) => setFormData(p => ({ ...p, city: e.target.value }))} className={inputClass} data-testid="contact-city" /></div>
                    <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">State</label><input type="text" value={formData.state} onChange={(e) => setFormData(p => ({ ...p, state: e.target.value }))} className={inputClass} data-testid="contact-state" /></div>
                    <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Pincode</label><input type="text" value={formData.pincode} onChange={(e) => setFormData(p => ({ ...p, pincode: e.target.value }))} className={inputClass} data-testid="contact-pincode" /></div>
                  </div>
                </motion.div>
              )}

              {/* Navigation Buttons */}
              <div className="flex items-center justify-between mt-10 pt-8 border-t border-[#E8E0D5]">
                {currentStep > 0 ? (
                  <button onClick={() => setCurrentStep(s => s - 1)} className="flex items-center gap-2 text-xs tracking-[0.15em] uppercase font-semibold text-[#4A3B32] hover:text-[#D4A373] transition-colors" data-testid="prev-step-button"><ArrowLeft size={14} /> Previous</button>
                ) : <div />}

                {currentStep < steps.length - 1 ? (
                  <button onClick={() => setCurrentStep(s => s + 1)} className="bg-[#4A3B32] text-white px-8 py-4 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#332822] transition-colors flex items-center gap-2" data-testid="next-step-button">Next <ArrowRight size={14} /></button>
                ) : (
                  <button onClick={handleSubmit} disabled={submitting} className="bg-[#4A3B32] text-white px-8 py-4 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#332822] transition-colors disabled:opacity-50 flex items-center gap-2" data-testid="submit-custom-order-button">{submitting ? 'Placing Order...' : 'Place Custom Order'} <Cake size={16} /></button>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>

      <BakeryFooter />
    </div>
  );
};

export default CustomCakeOrderPage;
