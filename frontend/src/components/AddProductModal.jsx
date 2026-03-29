import { useState } from 'react';
import apiClient from '../utils/api';
import { toast } from 'sonner';
import { X, Upload } from 'lucide-react';

const AddProductModal = ({ isOpen, onClose, businessId, onProductAdded }) => {
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    product_name: '',
    description: '',
    base_price: '',
    category_id: null,
    images: [{ url: '', alt: '', is_primary: true }],
    attributes: {},
    variants: [],
    inventory_count: ''
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleImageChange = (index, field, value) => {
    const newImages = [...formData.images];
    newImages[index][field] = value;
    setFormData(prev => ({ ...prev, images: newImages }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.product_name || !formData.base_price) {
      toast.error('Please fill required fields');
      return;
    }

    setLoading(true);
    try {
      const productData = {
        business_id: businessId,
        product_name: formData.product_name,
        description: formData.description,
        base_price: parseFloat(formData.base_price),
        currency: 'INR',
        images: formData.images.filter(img => img.url),
        attributes: formData.attributes,
        variants: formData.variants,
        inventory_count: parseInt(formData.inventory_count) || 0
      };

      await apiClient.post('/products', productData);
      toast.success('Product added successfully');
      onProductAdded();
      onClose();
      
      // Reset form
      setFormData({
        product_name: '',
        description: '',
        base_price: '',
        category_id: null,
        images: [{ url: '', alt: '', is_primary: true }],
        attributes: {},
        variants: [],
        inventory_count: ''
      });
    } catch (error) {
      console.error('Error adding product:', error);
      toast.error(error.response?.data?.detail || 'Failed to add product');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" data-testid="add-product-modal">
      <div className="bg-white border border-border max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="p-6 border-b border-border flex items-center justify-between sticky top-0 bg-white">
          <h2 className="text-2xl font-bold text-primary">ADD NEW PRODUCT</h2>
          <button
            onClick={onClose}
            className="text-muted hover:text-primary transition-colors"
            data-testid="close-modal"
          >
            <X size={24} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          <div>
            <label className="block text-sm font-medium text-primary mb-2">Product Name *</label>
            <input
              type="text"
              name="product_name"
              value={formData.product_name}
              onChange={handleChange}
              required
              className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
              data-testid="input-product-name"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-primary mb-2">Description</label>
            <textarea
              name="description"
              value={formData.description}
              onChange={handleChange}
              rows="3"
              className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none resize-none"
              data-testid="input-description"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-primary mb-2">Price (₹) *</label>
              <input
                type="number"
                name="base_price"
                value={formData.base_price}
                onChange={handleChange}
                required
                min="0"
                step="0.01"
                className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
                data-testid="input-price"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-primary mb-2">Initial Stock</label>
              <input
                type="number"
                name="inventory_count"
                value={formData.inventory_count}
                onChange={handleChange}
                min="0"
                className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
                data-testid="input-stock"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-primary mb-2">Image URL</label>
            <input
              type="url"
              value={formData.images[0].url}
              onChange={(e) => handleImageChange(0, 'url', e.target.value)}
              placeholder="https://example.com/image.jpg"
              className="w-full border border-border px-4 py-3 focus:ring-2 focus:ring-accent focus:border-accent transition-all outline-none"
              data-testid="input-image-url"
            />
            <p className="text-xs text-muted mt-1">Provide a URL to the product image</p>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-4 pt-4 border-t border-border">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 bg-transparent text-primary hover:bg-secondary transition-all border border-border px-6 py-3 font-bold tracking-wide"
              data-testid="cancel-button"
            >
              CANCEL
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 bg-accent text-white hover:bg-[#002280] transition-all border border-accent px-6 py-3 font-bold tracking-wide disabled:opacity-50"
              data-testid="submit-button"
            >
              {loading ? 'ADDING...' : 'ADD PRODUCT'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AddProductModal;