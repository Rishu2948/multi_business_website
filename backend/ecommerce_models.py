from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

# Cart Models
class CartItem(BaseModel):
    product_id: str
    variant_id: Optional[str] = None
    product_name: str
    quantity: int
    price: float
    image_url: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None

class CartCreate(BaseModel):
    product_id: str
    variant_id: Optional[str] = None
    quantity: int = 1

class CartUpdate(BaseModel):
    quantity: int

class Cart(BaseModel):
    cart_id: str
    user_id: Optional[str] = None  # For logged-in users
    session_id: Optional[str] = None  # For guest users
    items: List[CartItem] = []
    total_amount: float = 0.0
    created_at: datetime
    updated_at: datetime

# Order Models
class DeliveryInfo(BaseModel):
    name: str
    phone: str
    email: str
    address: str
    city: str
    state: str
    pincode: str
    delivery_date: Optional[str] = None
    delivery_time: Optional[str] = None
    special_instructions: Optional[str] = None

class OrderItem(BaseModel):
    product_id: str
    variant_id: Optional[str] = None
    product_name: str
    quantity: int
    price: float
    subtotal: float
    image_url: Optional[str] = None

class OrderCreate(BaseModel):
    items: List[OrderItem]
    delivery_info: DeliveryInfo
    payment_method: str  # "stripe" or "razorpay"
    subtotal: float
    tax: float
    delivery_charge: float
    total: float

class Order(BaseModel):
    order_id: str
    user_id: Optional[str] = None
    business_id: str = "whisked_words"
    items: List[OrderItem]
    delivery_info: DeliveryInfo
    payment_method: str
    payment_status: str  # pending, paid, failed
    payment_id: Optional[str] = None
    order_status: str  # pending, confirmed, preparing, out_for_delivery, delivered, cancelled
    subtotal: float
    tax: float
    delivery_charge: float
    total: float
    created_at: datetime
    updated_at: datetime

# Payment Models
class PaymentTransaction(BaseModel):
    transaction_id: str
    order_id: str
    user_id: Optional[str] = None
    payment_method: str
    amount: float
    currency: str = "INR"
    payment_status: str  # initiated, pending, paid, failed
    session_id: Optional[str] = None
    payment_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

# Custom Order Models (for cake customization)
class CustomOrderCreate(BaseModel):
    product_id: str
    cake_type: str
    weight: str
    flavor: str
    shape: str
    message_on_cake: Optional[str] = None
    special_instructions: Optional[str] = None
    image_reference_url: Optional[str] = None
    delivery_date: str
    delivery_time: str
    delivery_info: DeliveryInfo

class CustomOrder(BaseModel):
    custom_order_id: str
    user_id: Optional[str] = None
    business_id: str = "whisked_words"
    product_id: str
    cake_type: str
    weight: str
    flavor: str
    shape: str
    message_on_cake: Optional[str] = None
    special_instructions: Optional[str] = None
    image_reference_url: Optional[str] = None
    delivery_date: str
    delivery_time: str
    delivery_info: DeliveryInfo
    price: float
    status: str  # pending_quote, quoted, confirmed, rejected
    admin_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

# Review Models
class ReviewCreate(BaseModel):
    product_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None

class Review(BaseModel):
    review_id: str
    product_id: str
    user_id: str
    user_name: str
    rating: int
    comment: Optional[str] = None
    created_at: datetime

# Loyalty Points Models
class LoyaltyPoints(BaseModel):
    user_id: str
    points: int = 0
    total_earned: int = 0
    total_redeemed: int = 0
    tier: str = "bronze"  # bronze, silver, gold, platinum

class PointsTransaction(BaseModel):
    transaction_id: str
    user_id: str
    points: int
    type: str  # earned, redeemed
    reason: str
    order_id: Optional[str] = None
    created_at: datetime

# Subscription Models
class SubscriptionCreate(BaseModel):
    product_ids: List[str]
    frequency: str  # daily, weekly, monthly
    delivery_days: List[str]  # ["monday", "wednesday", "friday"]
    delivery_time: str
    start_date: str
    delivery_info: DeliveryInfo

class Subscription(BaseModel):
    subscription_id: str
    user_id: str
    business_id: str = "whisked_words"
    product_ids: List[str]
    frequency: str
    delivery_days: List[str]
    delivery_time: str
    start_date: str
    next_delivery: str
    delivery_info: DeliveryInfo
    status: str  # active, paused, cancelled
    created_at: datetime
    updated_at: datetime
