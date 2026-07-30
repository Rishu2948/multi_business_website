"""
Coupon Management for Prime Subscriptions

Handles creation, validation, and application of discount coupons.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from .models import CouponType, CouponStatus, PrimeCoupon

logger = logging.getLogger(__name__)


async def create_coupon(
    db,
    business_id: str,
    code: str,
    coupon_type: CouponType,
    discount_value: float,
    created_by: str,
    currency: str = "INR",
    trial_days: Optional[int] = None,
    max_uses: Optional[int] = None,
    valid_from: Optional[datetime] = None,
    valid_until: Optional[datetime] = None,
    applicable_plans: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create a new discount coupon."""
    coupon_id = f"coupon_{uuid.uuid4().hex[:12]}"
    
    if valid_from is None:
        valid_from = datetime.now(timezone.utc)
    
    coupon = {
        "coupon_id": coupon_id,
        "code": code.upper(),
        "business_id": business_id,
        "coupon_type": coupon_type,
        "discount_value": discount_value,
        "currency": currency,
        "trial_days": trial_days,
        "max_uses": max_uses,
        "used_count": 0,
        "valid_from": valid_from,
        "valid_until": valid_until,
        "applicable_plans": applicable_plans or [],
        "status": CouponStatus.ACTIVE,
        "created_at": datetime.now(timezone.utc),
        "created_by": created_by,
    }
    
    await db.prime_coupons.insert_one(coupon)
    logger.info(f"Created coupon {coupon_id} for business {business_id}")
    
    return coupon


async def validate_coupon(
    db,
    business_id: str,
    code: str,
    plan_id: str,
) -> Dict[str, Any]:
    """Validate a coupon and return discount details."""
    coupon = await db.prime_coupons.find_one({
        "business_id": business_id,
        "code": code.upper(),
    })
    
    if not coupon:
        raise ValueError("Invalid coupon code")
    
    # Check status
    if coupon["status"] != CouponStatus.ACTIVE:
        raise ValueError("Coupon is not active")
    
    # Check validity dates
    now = datetime.now(timezone.utc)
    if now < coupon["valid_from"]:
        raise ValueError("Coupon is not yet valid")
    
    if coupon["valid_until"] and now > coupon["valid_until"]:
        raise ValueError("Coupon has expired")
    
    # Check usage limit
    if coupon["max_uses"] and coupon["used_count"] >= coupon["max_uses"]:
        raise ValueError("Coupon usage limit exceeded")
    
    # Check if applicable to the plan
    if coupon["applicable_plans"] and plan_id not in coupon["applicable_plans"]:
        raise ValueError("Coupon is not applicable to this plan")
    
    return {
        "valid": True,
        "coupon_id": coupon["coupon_id"],
        "coupon_type": coupon["coupon_type"],
        "discount_value": coupon["discount_value"],
        "currency": coupon["currency"],
        "trial_days": coupon.get("trial_days"),
    }


async def apply_coupon(
    db,
    coupon_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Apply a coupon (increment usage count)."""
    coupon = await db.prime_coupons.find_one({"coupon_id": coupon_id})
    
    if not coupon:
        raise ValueError("Coupon not found")
    
    # Check if user has already used this coupon
    existing_usage = await db.prime_coupon_usage.find_one({
        "coupon_id": coupon_id,
        "user_id": user_id,
    })
    
    if existing_usage:
        raise ValueError("You have already used this coupon")
    
    # Record coupon usage
    await db.prime_coupon_usage.insert_one({
        "coupon_id": coupon_id,
        "user_id": user_id,
        "used_at": datetime.now(timezone.utc),
    })
    
    # Increment usage count
    await db.prime_coupons.update_one(
        {"coupon_id": coupon_id},
        {
            "$inc": {"used_count": 1},
            "$set": {"updated_at": datetime.now(timezone.utc)}
        }
    )
    
    # Check if max uses reached
    updated_coupon = await db.prime_coupons.find_one({"coupon_id": coupon_id})
    if updated_coupon["max_uses"] and updated_coupon["used_count"] >= updated_coupon["max_uses"]:
        await db.prime_coupons.update_one(
            {"coupon_id": coupon_id},
            {"$set": {"status": CouponStatus.USED}}
        )
    
    logger.info(f"Applied coupon {coupon_id} for user {user_id}")
    return {"success": True, "message": "Coupon applied successfully"}


async def get_coupons(db, business_id: str, include_expired: bool = False) -> List[Dict[str, Any]]:
    """Get all coupons for a business."""
    query = {"business_id": business_id}
    
    if not include_expired:
        query["status"] = CouponStatus.ACTIVE
    
    cursor = db.prime_coupons.find(query)
    return await cursor.to_list(length=None)


async def disable_coupon(db, coupon_id: str) -> Dict[str, Any]:
    """Disable a coupon."""
    result = await db.prime_coupons.update_one(
        {"coupon_id": coupon_id},
        {
            "$set": {
                "status": CouponStatus.DISABLED,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    if result.modified_count == 0:
        raise ValueError("Coupon not found")
    
    logger.info(f"Disabled coupon {coupon_id}")
    return {"success": True, "message": "Coupon disabled"}


async def calculate_discounted_price(
    original_price: float,
    coupon_type: CouponType,
    discount_value: float,
) -> float:
    """Calculate the discounted price based on coupon type."""
    if coupon_type == CouponType.PERCENTAGE:
        discount_amount = original_price * (discount_value / 100)
        return max(0, original_price - discount_amount)
    elif coupon_type == CouponType.FIXED_AMOUNT:
        return max(0, original_price - discount_value)
    else:
        return original_price  # Free trial doesn't affect price
