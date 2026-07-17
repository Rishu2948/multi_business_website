import { createContext, useContext, useState, useEffect } from 'react';
import apiClient from '../utils/api';
import { toast } from 'sonner';

const CartContext = createContext(null);

export const CartProvider = ({ children }) => {
  const [cart, setCart] = useState({ items: [], total_amount: 0 });
  const [loading, setLoading] = useState(false);
  const [cartCount, setCartCount] = useState(0);

  // Fetch cart on mount
  useEffect(() => {
    fetchCart();
  }, []);

  const fetchCart = async () => {
    try {
      const response = await apiClient.get('/ecommerce/cart');
      setCart(response.data);
      setCartCount(response.data.items?.reduce((sum, item) => sum + item.quantity, 0) || 0);
    } catch (error) {
      console.error('Error fetching cart:', error);
    }
  };

  const addToCart = async (productId, variantId = null, quantity = 1, selectedAddons = []) => {
    setLoading(true);
    // Optimistic count update
    setCartCount(prev => prev + quantity);
    try {
      await apiClient.post('/ecommerce/cart/add', {
        product_id: productId,
        variant_id: variantId,
        quantity: quantity,
        selected_addons: selectedAddons || [],
      });
      await fetchCart();
      toast.success('Item added to cart');
      return true;
    } catch (error) {
      console.error('Error adding to cart:', error);
      // Revert optimistic update
      setCartCount(prev => Math.max(0, prev - quantity));
      toast.error('Failed to add item to cart');
      return false;
    } finally {
      setLoading(false);
    }
  };

  const updateQuantity = async (productId, variantId, quantity) => {
    setLoading(true);
    try {
      const params = variantId ? `?variant_id=${variantId}` : '';
      await apiClient.put(`/ecommerce/cart/${productId}${params}`, { quantity });
      await fetchCart();
      toast.success('Cart updated');
    } catch (error) {
      console.error('Error updating cart:', error);
      toast.error('Failed to update cart');
    } finally {
      setLoading(false);
    }
  };

  const removeFromCart = async (productId, variantId = null) => {
    setLoading(true);
    try {
      const params = variantId ? `?variant_id=${variantId}` : '';
      await apiClient.delete(`/ecommerce/cart/${productId}${params}`);
      await fetchCart();
      toast.success('Item removed from cart');
    } catch (error) {
      console.error('Error removing from cart:', error);
      toast.error('Failed to remove item');
    } finally {
      setLoading(false);
    }
  };

  const clearCart = async () => {
    setLoading(true);
    try {
      await apiClient.delete('/ecommerce/cart');
      await fetchCart();
      toast.success('Cart cleared');
    } catch (error) {
      console.error('Error clearing cart:', error);
      toast.error('Failed to clear cart');
    } finally {
      setLoading(false);
    }
  };

  return (
    <CartContext.Provider
      value={{
        cart,
        cartCount,
        loading,
        addToCart,
        updateQuantity,
        removeFromCart,
        clearCart,
        refreshCart: fetchCart
      }}
    >
      {children}
    </CartContext.Provider>
  );
};

export const useCart = () => {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error('useCart must be used within CartProvider');
  }
  return context;
};