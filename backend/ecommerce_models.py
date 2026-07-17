from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


# ── Add-on Models (new) ────────────────────────────────────────────────────

class ProductAddonItem(BaseModel):
    addon_item_id: str
    name: str
    price: float = 0.0          # 0 = included, >0 = extra charge
    is_veg: Optional[bool] = None
    image_url: Optional[str] = None
    is_available: bool = True


class ProductAddonGroup(BaseModel):
    group_id: str
    group_name: str             # "COLD BEVERAGES"
    type: str = "optional"      # "optional" | "required"
    min_select: int = 0
    max_select: int = 1
    display_label: Optional[str] = None  # "You can choose up to 3 options"
    items: List[ProductAddonItem] = []


# ── Selected add-ons (used in cart / order) ────────────────────────────────

class SelectedAddonItem(BaseModel):
    addon_item_id: str
    name: str
    price: float


class SelectedAddonGroup(BaseModel):
    group_id: str
    group_name: str
    selected_items: List[SelectedAddonItem]


# ── Cart Models ────────────────────────────────────────────────────────────

class CartItem(BaseModel):
    product_id: str
    variant_id: Optional[str] = None
    product_name: str
    quantity: int
    price: float                        # base price only
    addons_price: float = 0.0           # total price of selected add-ons
    total_item_price: float = 0.0       # (price + addons_price) * quantity
    image_url: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = {}
    selected_addons: List[SelectedAddonGroup] = []  # add-on selections


class CartCreate(BaseModel):
    product_id: str
    variant_id: Optional[str] = None
    quantity: int = 1
    selected_addons: List[SelectedAddonGroup] = []  # carry add-on selections


class CartUpdate(BaseModel):
    quantity: int


class Cart(BaseModel):
    cart_id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    items: List[CartItem] = []
    total_amount: float = 0.0
    created_at: datetime
    updated_at: datetime


# ── Order Models ───────────────────────────────────────────────────────────

class OrderType(str, Enum):
    delivery = "delivery"
    takeaway = "takeaway"
    dine_in = "dine_in"


class DeliveryInfo(BaseModel):
    name: str
    phone: str
    email: str
    address: str
    city: str
    state: str
    pincode: str
    lat: Optional[float] = None
    lng: Optional[float] = None
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
    addons_price: float = 0.0
    image_url: Optional[str] = None
    selected_addons: List[SelectedAddonGroup] = []


class OrderCreate(BaseModel):
    items: List[OrderItem]
    delivery_info: DeliveryInfo
    payment_method: str                     # "stripe" | "razorpay" | "cod"
    subtotal: float
    tax: float
    delivery_charge: float
    discount_amount: float = 0.0            # from applied offers
    promo_code: Optional[str] = None
    offer_id: Optional[str] = None
    total: float
    order_type: OrderType = OrderType.delivery
    notes: Optional[str] = None


class Order(BaseModel):
    order_id: str
    user_id: Optional[str] = None
    business_id: str = "whisked_words"
    items: List[OrderItem]
    delivery_info: DeliveryInfo
    payment_method: str
    payment_status: str     # pending, paid, failed
    payment_id: Optional[str] = None
    order_status: str       # pending, confirmed, preparing, out_for_delivery, delivered, cancelled
    subtotal: float
    tax: float
    delivery_charge: float
    discount_amount: float = 0.0
    promo_code: Optional[str] = None
    offer_id: Optional[str] = None
    total: float
    order_type: OrderType = OrderType.delivery
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ── Payment Models ─────────────────────────────────────────────────────────

class PaymentTransaction(BaseModel):
    transaction_id: str
    order_id: str
    user_id: Optional[str] = None
    payment_method: str
    amount: float
    currency: str = "INR"
    payment_status: str     # initiated, pending, paid, failed
    session_id: Optional[str] = None
    payment_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


# ── Custom Order Models ────────────────────────────────────────────────────

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
    status: str     # pending_quote, quoted, confirmed, rejected
    admin_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ── Review Models ──────────────────────────────────────────────────────────

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


# ── Loyalty Models ─────────────────────────────────────────────────────────

class LoyaltyPoints(BaseModel):
    user_id: str
    points: int = 0
    total_earned: int = 0
    total_redeemed: int = 0
    tier: str = "bronze"    # bronze, silver, gold, platinum


class PointsTransaction(BaseModel):
    transaction_id: str
    user_id: str
    points: int
    type: str               # earned, redeemed
    reason: str
    order_id: Optional[str] = None
    created_at: datetime


# ── Subscription Models ────────────────────────────────────────────────────

class SubscriptionCreate(BaseModel):
    product_ids: List[str]
    frequency: str          # daily, weekly, monthly
    delivery_days: List[str]
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
    status: str             # active, paused, cancelled
    created_at: datetime
    updated_at: datetime
