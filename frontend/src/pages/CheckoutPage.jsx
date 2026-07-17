import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import BakeryNavbar from '../components/common/BakeryNavbar';
import BakeryFooter from '../components/common/BakeryFooter';
import AnnouncementBar from '../components/common/AnnouncementBar';
import { useCart } from '../context/CartContext';
import { useAuth } from '../context/AuthContext';
import apiClient from '../utils/api';
import { toast } from 'sonner';
import {
  CreditCard, Truck, Wallet, MapPin, Home, Briefcase,
  Plus, Navigation, Check, Trash2, Star, Tag, X, ChevronDown, ChevronUp,
} from 'lucide-react';

const LABELS = [
  { value: 'Home', icon: Home },
  { value: 'Work', icon: Briefcase },
  { value: 'Other', icon: MapPin },
];

const CheckoutPage = () => {
  const navigate = useNavigate();
  const { cart, clearCart } = useCart();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState('cod');
  const [delivery, setDelivery] = useState({ name: '', phone: '', email: '', address: '', city: '', state: '', pincode: '', lat: null, lng: null });
  const [savedAddresses, setSavedAddresses] = useState([]);
  const [selectedAddressId, setSelectedAddressId] = useState(null);
  const [showNewAddress, setShowNewAddress] = useState(false);
  const [savingAddress, setSavingAddress] = useState(false);
  const [newLabel, setNewLabel] = useState('Home');
  const [saveAsDefault, setSaveAsDefault] = useState(false);
  // Offer code state
  const [promoCode, setPromoCode] = useState('');
  const [promoInput, setPromoInput] = useState('');
  const [promoLoading, setPromoLoading] = useState(false);
  const [appliedOffer, setAppliedOffer] = useState(null);
  const [discountAmount, setDiscountAmount] = useState(0);
  const [locating, setLocating] = useState(false);
  const [loadingAddresses, setLoadingAddresses] = useState(true);
  // Accordion state for mobile sections
  const [openSection, setOpenSection] = useState('delivery'); // 'delivery' | 'payment' | 'review'
  const toggleSection = (s) => setOpenSection(prev => prev === s ? '' : s);

  const items = cart?.items || [];
  const subtotal = cart?.total_amount || 0;
  const tax = Math.round(subtotal * 0.05 * 100) / 100;
  const deliveryCharge = subtotal >= 500 ? 0 : 50;
  const total = Math.max(0, subtotal + tax + deliveryCharge - discountAmount);

  const handleApplyPromo = async () => {
    if (!promoInput.trim()) return;
    setPromoLoading(true);
    try {
      const r = await apiClient.post('/offers/validate', {
        business_id: 'whisked_words',
        promo_code: promoInput.trim().toUpperCase(),
        cart_total: subtotal,
        cart_items: items.map(i => ({
          product_id: i.product_id,
          category_id: i.category_id || '',
          quantity: i.quantity,
          price: i.price,
        })),
        user_id: null,
      });
      if (r.data.is_valid) {
        setAppliedOffer(r.data.offer);
        setDiscountAmount(r.data.discount_amount);
        setPromoCode(promoInput.trim().toUpperCase());
        toast.success(r.data.message);
      } else {
        toast.error(r.data.message);
      }
    } catch {
      toast.error('Failed to validate promo code');
    } finally {
      setPromoLoading(false);
    }
  };

  const handleRemovePromo = () => {
    setAppliedOffer(null);
    setDiscountAmount(0);
    setPromoCode('');
    setPromoInput('');
  };

  const inputClass = "w-full border border-[#E8E0D5] px-4 py-3 focus:ring-1 focus:ring-[#4A3B32] focus:border-[#4A3B32] transition-all outline-none bg-white text-[#2C2420] text-sm";

  const fetchAddresses = useCallback(async () => {
    try {
      const res = await apiClient.get('/locations/addresses');
      setSavedAddresses(res.data.addresses);
      // Auto-select default
      const def = res.data.addresses.find(a => a.is_default);
      if (def) {
        selectAddress(def);
      } else if (res.data.addresses.length === 0) {
        setShowNewAddress(true);
      }
    } catch {}
    finally { setLoadingAddresses(false); }
  }, []);

  useEffect(() => {
    if (isAuthenticated && !authLoading) fetchAddresses();
    else if (!authLoading) setLoadingAddresses(false);
  }, [isAuthenticated, authLoading, fetchAddresses]);

  const selectAddress = (addr) => {
    setSelectedAddressId(addr.address_id);
    setDelivery({
      name: addr.name, phone: addr.phone, email: addr.email || '',
      address: addr.address, city: addr.city, state: addr.state,
      pincode: addr.pincode, lat: addr.lat, lng: addr.lng
    });
    setShowNewAddress(false);
  };

  const useCurrentLocation = () => {
    if (!navigator.geolocation) { toast.error('Geolocation not supported by your browser'); return; }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude, longitude } = pos.coords;
        setDelivery(d => ({ ...d, lat: latitude, lng: longitude }));
        // Reverse geocode using Nominatim (free)
        try {
          const resp = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}&addressdetails=1`);
          const data = await resp.json();
          if (data.address) {
            const a = data.address;
            setDelivery(d => ({
              ...d,
              address: data.display_name?.split(',').slice(0, 3).join(', ') || d.address,
              city: a.city || a.town || a.village || a.county || d.city,
              state: a.state || d.state,
              pincode: a.postcode || d.pincode
            }));
          }
          toast.success('Location detected');
        } catch { toast.success('GPS coordinates captured'); }
        setLocating(false);
      },
      () => { toast.error('Unable to get location. Please allow location access.'); setLocating(false); },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  const saveNewAddress = async () => {
    if (!delivery.address || !delivery.city || !delivery.pincode) { toast.error('Fill required address fields'); return; }
    setSavingAddress(true);
    try {
      await apiClient.post('/locations/addresses', {
        ...delivery, label: newLabel, is_default: saveAsDefault
      });
      toast.success('Address saved');
      fetchAddresses();
    } catch (e) { toast.error('Failed to save address'); }
    finally { setSavingAddress(false); }
  };

  const deleteAddress = async (addressId) => {
    try {
      await apiClient.delete(`/locations/addresses/${addressId}`);
      toast.success('Address deleted');
      if (selectedAddressId === addressId) {
        setSelectedAddressId(null);
        setDelivery({ name: '', phone: '', email: '', address: '', city: '', state: '', pincode: '', lat: null, lng: null });
      }
      fetchAddresses();
    } catch { toast.error('Failed to delete'); }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!isAuthenticated) { toast.error('Please login to place an order'); navigate('/login'); return; }
    if (items.length === 0) { toast.error('Cart is empty'); return; }
    if (!delivery.name || !delivery.phone || !delivery.address || !delivery.city || !delivery.state || !delivery.pincode) { toast.error('Please fill delivery details'); return; }

    setSubmitting(true);
    try {
      const orderPayload = {
        items: items.map(item => ({ product_id: item.product_id, variant_id: null, product_name: item.product_name, quantity: item.quantity, price: item.price, subtotal: item.price * item.quantity, addons_price: item.addons_price || 0, selected_addons: item.selected_addons || [] })),
        delivery_info: delivery, payment_method: paymentMethod, subtotal, tax, delivery_charge: deliveryCharge,
        discount_amount: discountAmount,
        promo_code: promoCode || null,
        offer_id: appliedOffer?.offer_id || null,
        total,
      };

      if (paymentMethod === 'stripe') {
        const paymentRes = await apiClient.post('/payments/stripe/create-session', { items: orderPayload.items, delivery_info: delivery, subtotal, tax, delivery_charge: deliveryCharge, total });
        if (paymentRes.data.checkout_url) { window.location.href = paymentRes.data.checkout_url; return; }
      }

      const orderRes = await apiClient.post('/orders/create', orderPayload);
      await clearCart();
      toast.success('Order placed successfully!');
      navigate(`/order-success?orderId=${orderRes.data.order_id}&method=${paymentMethod}`);
    } catch (error) { toast.error(error.response?.data?.detail || 'Failed to place order'); }
    finally { setSubmitting(false); }
  };

  if (items.length === 0) {
    return (
      <div className="min-h-screen flex flex-col bg-[#FAF8F5]"><BakeryNavbar />
        <div className="flex-1 flex items-center justify-center flex-col gap-4 py-24">
          <p className="font-serif text-2xl text-[#2C2420]">Your cart is empty</p>
          <button onClick={() => navigate('/business/whisked_words/catalog')} className="bg-[#4A3B32] text-white px-8 py-4 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#332822] transition-colors" data-testid="browse-products-btn">Browse Products</button>
        </div>
      <BakeryFooter /></div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF8F5]" data-testid="checkout-page">
      <AnnouncementBar businessId="whisked_words" />
      <BakeryNavbar />

      <main className="flex-1 py-16 md:py-24">
        <div className="max-w-6xl mx-auto px-6 md:px-12">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <p className="text-xs tracking-[0.2em] uppercase text-[#D4A373] font-semibold mb-2">Final Step</p>
            <h1 className="font-serif text-4xl md:text-5xl text-[#2C2420] mb-12">Checkout</h1>
          </motion.div>

          <form onSubmit={handleSubmit}>
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">
              {/* Left: Forms */}
              <div className="lg:col-span-7 space-y-10">
                {/* Saved Addresses */}
                {isAuthenticated && (
                  <div className="bg-white border border-[#E8E0D5]" data-testid="saved-addresses-section">
                    {/* Accordion header */}
                    <button
                      type="button"
                      onClick={() => toggleSection('delivery')}
                      className="w-full flex items-center justify-between p-5 sm:p-8 text-left"
                      aria-expanded={openSection === 'delivery'}
                      data-testid="delivery-accordion-toggle"
                    >
                      <div className="flex items-center gap-3">
                        {selectedAddressId && <Check size={16} className="text-green-600 flex-shrink-0" />}
                        <h2 className="font-serif text-lg sm:text-xl text-[#2C2420]">
                          {openSection !== 'delivery' && selectedAddressId
                            ? `Delivering to: ${delivery.city}`
                            : 'Delivery Address'}
                        </h2>
                      </div>
                      <div className="flex items-center gap-3">
                        {openSection === 'delivery'
                          ? <button type="button" onClick={(e) => { e.stopPropagation(); setShowNewAddress(true); setSelectedAddressId(null); setDelivery({ name: '', phone: '', email: '', address: '', city: '', state: '', pincode: '', lat: null, lng: null }); }}
                              className="text-xs text-[#D4A373] font-semibold flex items-center gap-1" data-testid="add-new-address-btn">
                              <Plus size={12} /> New
                            </button>
                          : null
                        }
                        {openSection === 'delivery' ? <ChevronUp size={18} className="text-[#786A60]" /> : <ChevronDown size={18} className="text-[#786A60]" />}
                      </div>
                    </button>

                    {/* Collapsible content */}
                    <AnimatePresence initial={false}>
                      {openSection === 'delivery' && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.25 }}
                          className="overflow-hidden px-5 sm:px-8 pb-6"
                        >

                    {/* Saved Address Cards */}
                    {!loadingAddresses && savedAddresses.length > 0 && (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6" data-testid="saved-addresses-grid">
                        {savedAddresses.map(addr => {
                          const LabelIcon = LABELS.find(l => l.value === addr.label)?.icon || MapPin;
                          const isSelected = selectedAddressId === addr.address_id;
                          return (
                            <button type="button" key={addr.address_id} onClick={() => selectAddress(addr)}
                              className={`relative p-4 border text-left transition-all ${isSelected ? 'border-[#D4A373] bg-[#D4A373]/5 ring-1 ring-[#D4A373]' : 'border-[#E8E0D5] hover:border-[#D4A373]/50'}`}
                              data-testid={`saved-address-${addr.address_id}`}>
                              {isSelected && <Check size={16} className="absolute top-3 right-3 text-[#D4A373]" />}
                              {addr.is_default && <Star size={12} className="absolute top-3 right-8 text-[#D4A373] fill-[#D4A373]" />}
                              <div className="flex items-center gap-2 mb-2">
                                <LabelIcon size={14} className="text-[#D4A373]" />
                                <span className="text-xs tracking-[0.1em] uppercase font-semibold text-[#4A3B32]">{addr.label}</span>
                              </div>
                              <p className="text-sm text-[#2C2420] font-medium">{addr.name}</p>
                              <p className="text-xs text-[#786A60] mt-0.5 line-clamp-2">{addr.address}, {addr.city} - {addr.pincode}</p>
                              {addr.lat && <p className="text-[10px] text-[#D4A373] mt-1 flex items-center gap-1"><MapPin size={10} />GPS saved</p>}
                              <button type="button" onClick={(e) => { e.stopPropagation(); deleteAddress(addr.address_id); }} className="absolute bottom-3 right-3 text-[#786A60] hover:text-red-500 transition-colors" data-testid={`delete-address-${addr.address_id}`}>
                                <Trash2 size={13} />
                              </button>
                            </button>
                          );
                        })}
                      </div>
                    )}

                    {/* New Address Form / Edit Form */}
                    <AnimatePresence>
                      {(showNewAddress || savedAddresses.length === 0) && (
                        <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
                          {/* Use Current Location Button */}
                          <button type="button" onClick={useCurrentLocation} disabled={locating}
                            className="w-full mb-4 p-3 border border-dashed border-[#D4A373] text-[#D4A373] hover:bg-[#D4A373]/5 transition-colors flex items-center justify-center gap-2 text-xs tracking-[0.1em] uppercase font-semibold disabled:opacity-50"
                            data-testid="use-current-location-btn">
                            <Navigation size={14} className={locating ? 'animate-spin' : ''} />
                            {locating ? 'Detecting Location...' : 'Use My Current Location'}
                          </button>

                          {delivery.lat && (
                            <p className="text-[10px] text-[#A3B18A] mb-3 flex items-center gap-1" data-testid="gps-indicator"><MapPin size={10} /> GPS: {delivery.lat.toFixed(4)}, {delivery.lng.toFixed(4)}</p>
                          )}

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Full Name *</label><input type="text" value={delivery.name} onChange={(e) => setDelivery(d => ({ ...d, name: e.target.value }))} className={inputClass} data-testid="checkout-input-name" /></div>
                            <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Phone *</label><input type="tel" value={delivery.phone} onChange={(e) => setDelivery(d => ({ ...d, phone: e.target.value }))} className={inputClass} data-testid="checkout-input-phone" /></div>
                            <div className="md:col-span-2"><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Email</label><input type="email" value={delivery.email} onChange={(e) => setDelivery(d => ({ ...d, email: e.target.value }))} className={inputClass} data-testid="checkout-input-email" /></div>
                            <div className="md:col-span-2"><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Address *</label><textarea value={delivery.address} onChange={(e) => setDelivery(d => ({ ...d, address: e.target.value }))} rows="2" className={`${inputClass} resize-none`} data-testid="checkout-input-address" /></div>
                            <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">City *</label><input type="text" value={delivery.city} onChange={(e) => setDelivery(d => ({ ...d, city: e.target.value }))} className={inputClass} data-testid="checkout-input-city" /></div>
                            <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">State *</label><input type="text" value={delivery.state} onChange={(e) => setDelivery(d => ({ ...d, state: e.target.value }))} className={inputClass} data-testid="checkout-input-state" /></div>
                            <div><label className="block text-xs tracking-[0.1em] uppercase text-[#786A60] font-semibold mb-2">Pincode *</label><input type="text" value={delivery.pincode} onChange={(e) => setDelivery(d => ({ ...d, pincode: e.target.value }))} className={inputClass} data-testid="checkout-input-pincode" /></div>
                          </div>

                          {/* Save Address Options */}
                          {isAuthenticated && (
                            <div className="mt-4 pt-4 border-t border-[#E8E0D5] flex flex-wrap items-center gap-4">
                              <div className="flex gap-2">
                                {LABELS.map(({ value, icon: Icon }) => (
                                  <button type="button" key={value} onClick={() => setNewLabel(value)}
                                    className={`px-3 py-1.5 text-xs tracking-[0.05em] uppercase font-semibold border flex items-center gap-1.5 transition-colors ${newLabel === value ? 'bg-[#4A3B32] text-white border-[#4A3B32]' : 'bg-white text-[#4A3B32] border-[#E8E0D5] hover:bg-[#FAF8F5]'}`}
                                    data-testid={`label-${value.toLowerCase()}`}>
                                    <Icon size={12} /> {value}
                                  </button>
                                ))}
                              </div>
                              <label className="flex items-center gap-2 text-xs text-[#786A60] cursor-pointer" data-testid="save-as-default-label">
                                <input type="checkbox" checked={saveAsDefault} onChange={(e) => setSaveAsDefault(e.target.checked)} className="accent-[#D4A373]" />
                                Set as default
                              </label>
                              <button type="button" onClick={saveNewAddress} disabled={savingAddress}
                                className="px-4 py-2 text-xs tracking-[0.1em] uppercase font-semibold bg-[#D4A373] text-white hover:bg-[#c49363] transition-colors disabled:opacity-50"
                                data-testid="save-address-btn">
                                {savingAddress ? 'Saving...' : 'Save Address'}
                              </button>
                            </div>
                          )}
                        </motion.div>
                      )}
                    </AnimatePresence>
                    </motion.div>
                  )}
                  </AnimatePresence>
                  </div>
                )}

                <div className="bg-white border border-[#E8E0D5]" data-testid="payment-method-section">
                  <button
                    type="button"
                    onClick={() => toggleSection('payment')}
                    className="w-full flex items-center justify-between p-5 sm:p-8 text-left"
                    aria-expanded={openSection === 'payment'}
                    data-testid="payment-accordion-toggle"
                  >
                    <div className="flex items-center gap-3">
                      {openSection !== 'payment' && (
                        <Check size={16} className="text-green-600 flex-shrink-0" />
                      )}
                      <h2 className="font-serif text-lg sm:text-xl text-[#2C2420]">
                        {openSection !== 'payment'
                          ? `Payment: ${paymentMethod === 'cod' ? 'Cash on Delivery' : paymentMethod === 'stripe' ? 'Card / UPI' : 'Razorpay'}`
                          : 'Payment Method'}
                      </h2>
                    </div>
                    {openSection === 'payment'
                      ? <ChevronUp size={18} className="text-[#786A60]" />
                      : <ChevronDown size={18} className="text-[#786A60]" />}
                  </button>

                  <AnimatePresence initial={false}>
                    {openSection === 'payment' && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.25 }}
                        className="overflow-hidden px-5 sm:px-8 pb-6"
                      >
                  <div className="space-y-3">
                    {[
                      { value: 'cod', label: 'Cash on Delivery', icon: Truck, desc: 'Pay when your order arrives' },
                      { value: 'stripe', label: 'Card / UPI (Stripe)', icon: CreditCard, desc: 'Secure online payment' },
                      { value: 'razorpay', label: 'Razorpay', icon: Wallet, desc: 'UPI, Cards, Netbanking' }
                    ].map(({ value, label, icon: Icon, desc }) => (
                      <button key={value} type="button"
                        onClick={() => { setPaymentMethod(value); toggleSection('review'); }}
                        className={`w-full p-4 sm:p-5 border text-left flex items-center gap-4 transition-all
                          ${paymentMethod === value ? 'border-[#D4A373] bg-[#D4A373]/5' : 'border-[#E8E0D5] hover:bg-[#FAF8F5]'}`}
                        data-testid={`payment-${value}`}>
                        <div className={`w-9 h-9 flex items-center justify-center flex-shrink-0
                          ${paymentMethod === value ? 'bg-[#4A3B32]' : 'bg-[#F3EFEA]'}`}>
                          <Icon size={16} className={paymentMethod === value ? 'text-white' : 'text-[#786A60]'} />
                        </div>
                        <div>
                          <p className="font-semibold text-[#2C2420] text-sm">{label}</p>
                          <p className="text-xs text-[#786A60]">{desc}</p>
                        </div>
                        {paymentMethod === value && <Check size={14} className="text-[#D4A373] ml-auto" />}
                      </button>
                    ))}
                  </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </div>

              {/* Right: Order Summary */}
              <div className="lg:col-span-5">
                <div className="sticky top-28 bg-white border border-[#E8E0D5] p-8" data-testid="order-summary">
                  <h2 className="font-serif text-xl text-[#2C2420] mb-6">Order Summary</h2>

                  <div className="space-y-4 mb-6 pb-6 border-b border-[#E8E0D5]">
                    {items.map((item) => (
                      <div key={item.product_id} className="flex items-center justify-between" data-testid={`summary-item-${item.product_id}`}>
                        <div className="flex items-center gap-3">
                          <div className="w-12 h-12 bg-[#F3EFEA] overflow-hidden flex-shrink-0">{item.image_url && <img src={item.image_url} alt={item.product_name} className="w-full h-full object-cover" />}</div>
                          <div><p className="text-sm font-medium text-[#2C2420]">{item.product_name}</p><p className="text-xs text-[#786A60]">Qty: {item.quantity}</p></div>
                        </div>
                        <p className="text-sm font-medium text-[#2C2420]">₹{(item.price * item.quantity).toLocaleString()}</p>
                      </div>
                    ))}
                  </div>

                  <div className="space-y-2 mb-6 pb-6 border-b border-[#E8E0D5] text-sm">
                    <div className="flex justify-between"><span className="text-[#786A60]">Subtotal</span><span className="text-[#2C2420]">₹{subtotal.toLocaleString()}</span></div>
                    <div className="flex justify-between"><span className="text-[#786A60]">Tax (5%)</span><span className="text-[#2C2420]">₹{tax.toLocaleString()}</span></div>
                    <div className="flex justify-between"><span className="text-[#786A60]">Delivery</span><span className={deliveryCharge === 0 ? 'text-[#A3B18A]' : 'text-[#2C2420]'}>{deliveryCharge === 0 ? 'Free' : `₹${deliveryCharge}`}</span></div>
                    {discountAmount > 0 && (
                      <div className="flex justify-between text-green-700 font-medium">
                        <span className="flex items-center gap-1"><Tag size={12} />{promoCode}</span>
                        <span>-₹{discountAmount.toLocaleString()}</span>
                      </div>
                    )}
                  </div>

                  {/* Promo code input */}
                  <div className="mb-6">
                    {appliedOffer ? (
                      <div className="flex items-center justify-between bg-green-50 border border-green-200 px-3 py-2 text-sm">
                        <span className="flex items-center gap-1.5 text-green-700">
                          <Tag size={13} />
                          <strong>{promoCode}</strong> applied — ₹{discountAmount.toLocaleString()} off
                        </span>
                        <button onClick={handleRemovePromo} className="text-green-600 hover:text-red-500" data-testid="remove-promo">
                          <X size={14} />
                        </button>
                      </div>
                    ) : (
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={promoInput}
                          onChange={e => setPromoInput(e.target.value.toUpperCase())}
                          placeholder="Promo code"
                          className="flex-1 border border-[#E8E0D5] px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#4A3B32]"
                          data-testid="promo-code-input"
                          onKeyDown={e => e.key === 'Enter' && handleApplyPromo()}
                        />
                        <button
                          type="button"
                          onClick={handleApplyPromo}
                          disabled={promoLoading || !promoInput.trim()}
                          className="bg-[#D4A373] text-white px-4 py-2 text-xs font-semibold hover:bg-[#c49363] disabled:opacity-50"
                          data-testid="apply-promo-btn"
                        >
                          {promoLoading ? '...' : 'Apply'}
                        </button>
                      </div>
                    )}
                  </div>

                  <div className="flex justify-between mb-8">
                    <span className="font-serif text-lg text-[#2C2420]">Total</span>
                    <span className="font-serif text-xl text-[#2C2420]" data-testid="checkout-total">₹{total.toLocaleString()}</span>
                  </div>

                  <button type="submit" disabled={submitting} className="w-full bg-[#4A3B32] text-white py-4 text-xs tracking-[0.15em] uppercase font-semibold hover:bg-[#332822] transition-colors duration-300 disabled:opacity-50" data-testid="place-order-button">
                    {submitting ? 'Processing...' : 'Place Order'}
                  </button>

                  {subtotal < 500 && <p className="text-xs text-[#D4A373] text-center mt-3">Add ₹{(500 - subtotal).toLocaleString()} more for free delivery</p>}
                </div>
              </div>
            </div>
          </form>
        </div>
      </main>

      <BakeryFooter />
    </div>
  );
};

export default CheckoutPage;
