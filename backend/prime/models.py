"""
Pydantic models for Prime subscription system.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field


class MembershipStatus(str, Enum):
    """Status of a Prime membership."""
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PENDING_PAYMENT = "pending_payment"
    IN_GRACE_PERIOD = "in_grace_period"


class PrimeFeatureConfig(BaseModel):
    """Configuration for a single Prime feature."""
    enabled: bool
    label: str


class PrimePlanConfig(BaseModel):
    """Configuration for a subscription plan."""
    plan_id: str
    name: str
    billing_cycle: str = Field(..., pattern="^(monthly|annual)$")
    price: float
    currency: str = "INR"
    is_active: bool = True
    marketing_features: List[str] = Field(default_factory=list)
    gateway_product_id: Optional[str] = None
    trial_days: Optional[int] = None  # Trial period in days


class CouponType(str, Enum):
    """Types of discounts."""
    PERCENTAGE = "percentage"
    FIXED_AMOUNT = "fixed_amount"
    FREE_TRIAL = "free_trial"


class CouponStatus(str, Enum):
    """Status of a coupon."""
    ACTIVE = "active"
    EXPIRED = "expired"
    DISABLED = "disabled"
    USED = "used"


class PrimeCoupon(BaseModel):
    """Discount coupon for Prime subscriptions."""
    coupon_id: str
    code: str  # User-facing coupon code
    business_id: str
    coupon_type: CouponType
    discount_value: float  # Percentage or fixed amount
    currency: str = "INR"
    trial_days: Optional[int] = None  # For free_trial type
    max_uses: Optional[int] = None  # Maximum number of uses
    used_count: int = 0
    valid_from: datetime
    valid_until: Optional[datetime] = None
    applicable_plans: List[str] = Field(default_factory=list)  # Plan IDs this applies to
    status: CouponStatus = CouponStatus.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str  # User ID who created the coupon


class PrimeConfig(BaseModel):
    """Prime configuration subsection in business_config."""
    enabled: bool
    display_name: str
    tagline: str
    plans: List[PrimePlanConfig] = Field(default_factory=list)
    features: dict = Field(default_factory=dict)  # {feature_key: PrimeFeatureConfig}


class PrimeMembership(BaseModel):
    """Prime membership record."""
    membership_id: str
    user_id: str
    business_id: str
    plan_id: str
    status: MembershipStatus
    started_at: datetime
    expires_at: datetime
    cancelled_at: Optional[datetime] = None
    auto_renew: bool = True
    granted_by_admin: bool = False
    payment_history: List[dict] = Field(default_factory=list)
    notifications_sent: List[dict] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SubscribeRequest(BaseModel):
    """Request to subscribe to Prime."""
    business_id: str
    plan_id: str
    payment_method: str = Field(..., pattern="^(razorpay|stripe)$")


class MembershipResponse(BaseModel):
    """Response with membership details."""
    membership_id: str
    business_id: str
    plan_id: str
    status: MembershipStatus
    started_at: datetime
    expires_at: datetime
    auto_renew: bool
    plan_name: str
    price: float
    billing_cycle: str
    enabled_features: List[str] = Field(default_factory=list)
    grace_period_ends_at: Optional[datetime] = None


class PlansResponse(BaseModel):
    """Response with available plans."""
    enabled: bool
    display_name: str
    tagline: str
    plans: List[PrimePlanConfig]
    enabled_features: List[str] = Field(default_factory=list)


class BusinessConfigUpdate(BaseModel):
    """Request to update business config."""
    prime: Optional[PrimeConfig] = None
