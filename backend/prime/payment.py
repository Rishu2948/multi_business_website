"""
Payment Gateway Integration for Prime Subscriptions

Supports Razorpay for subscription-based Prime memberships.
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta

try:
    import razorpay
except ImportError:
    razorpay = None

logger = logging.getLogger(__name__)


class RazorpayClient:
    """Razorpay client for Prime subscription management."""
    
    def __init__(self):
        self.client = None
        self.key_id = os.environ.get("RAZORPAY_KEY_ID")
        self.key_secret = os.environ.get("RAZORPAY_KEY_SECRET")
        
        if razorpay and self.key_id and self.key_secret:
            self.client = razorpay.Client(auth=(self.key_id, self.key_secret))
            logger.info("Razorpay client initialized")
        else:
            logger.warning("Razorpay client not initialized - missing credentials or package")
    
    def is_configured(self) -> bool:
        """Check if Razorpay is properly configured."""
        return self.client is not None
    
    def create_plan(self, plan_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a subscription plan in Razorpay."""
        if not self.is_configured():
            logger.error("Razorpay not configured")
            return None
        
        try:
            plan = {
                "period": plan_data["billing_cycle"],  # monthly or annual
                "interval": 1,
                "item": {
                    "name": plan_data["name"],
                    "description": f"Prime subscription - {plan_data['name']}",
                    "amount": int(plan_data["price"] * 100),  # Razorpay uses paise
                    "currency": plan_data.get("currency", "INR"),
                },
                "notes": {
                    "business_id": plan_data.get("business_id"),
                    "plan_id": plan_data["plan_id"],
                }
            }
            
            result = self.client.plan.create(data=plan)
            logger.info(f"Created Razorpay plan: {result['id']}")
            return result
        except Exception as e:
            logger.error(f"Failed to create Razorpay plan: {e}")
            return None
    
    def get_plan(self, razorpay_plan_id: str) -> Optional[Dict[str, Any]]:
        """Get plan details from Razorpay."""
        if not self.is_configured():
            return None
        
        try:
            return self.client.plan.fetch(razorpay_plan_id)
        except Exception as e:
            logger.error(f"Failed to fetch Razorpay plan: {e}")
            return None
    
    def create_subscription(
        self,
        plan_id: str,
        customer_id: str,
        business_id: str,
        user_id: str,
        start_at: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a subscription in Razorpay."""
        if not self.is_configured():
            return None
        
        try:
            subscription_data = {
                "plan_id": plan_id,
                "customer_id": customer_id,
                "total_count": 12,  # Auto-renew for 12 cycles
                "notes": {
                    "business_id": business_id,
                    "user_id": user_id,
                }
            }
            
            if start_at:
                subscription_data["start_at"] = start_at
            
            result = self.client.subscription.create(data=subscription_data)
            logger.info(f"Created Razorpay subscription: {result['id']}")
            return result
        except Exception as e:
            logger.error(f"Failed to create Razorpay subscription: {e}")
            return None
    
    def cancel_subscription(self, subscription_id: str, cancel_at_cycle_end: bool = True) -> Optional[Dict[str, Any]]:
        """Cancel a subscription in Razorpay."""
        if not self.is_configured():
            return None
        
        try:
            result = self.client.subscription.cancel(
                subscription_id,
                cancel_at_cycle_end=cancel_at_cycle_end
            )
            logger.info(f"Cancelled Razorpay subscription: {subscription_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to cancel Razorpay subscription: {e}")
            return None
    
    def create_customer(
        self,
        name: str,
        email: str,
        phone: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a customer in Razorpay."""
        if not self.is_configured():
            return None
        
        try:
            customer_data = {
                "name": name,
                "email": email,
            }
            
            if phone:
                customer_data["contact"] = phone
            
            result = self.client.customer.create(data=customer_data)
            logger.info(f"Created Razorpay customer: {result['id']}")
            return result
        except Exception as e:
            logger.error(f"Failed to create Razorpay customer: {e}")
            return None
    
    def create_checkout_session(
        self,
        plan_id: str,
        customer_id: str,
        amount: float,
        currency: str = "INR",
        notes: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a checkout session for one-time payment (for manual activation)."""
        if not self.is_configured():
            return None
        
        try:
            order_data = {
                "amount": int(amount * 100),
                "currency": currency,
                "receipt": f"prime_{datetime.now().timestamp()}",
                "notes": notes or {},
            }
            
            order = self.client.order.create(data=order_data)
            logger.info(f"Created Razorpay order: {order['id']}")
            return order
        except Exception as e:
            logger.error(f"Failed to create Razorpay order: {e}")
            return None
    
    def verify_payment_signature(
        self,
        order_id: str,
        payment_id: str,
        signature: str
    ) -> bool:
        """Verify Razorpay payment signature."""
        if not self.is_configured():
            return False
        
        try:
            params = {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature
            }
            self.client.utility.verify_payment_signature(params)
            return True
        except Exception as e:
            logger.error(f"Payment signature verification failed: {e}")
            return False


# Global Razorpay client instance
razorpay_client = RazorpayClient()
