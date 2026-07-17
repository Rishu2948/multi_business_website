"""
backend/offers_routes.py

Config-driven offers system. Admins create/edit offers via the dashboard.
Supports percentage, flat, free_delivery, buy_x_get_y types.
Scope: all_products, specific_categories, specific_products, specific_collections.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

db = None

def set_db(database):
    global db
    db = database


# ── Models ─────────────────────────────────────────────────────────────────

class OfferCreate(BaseModel):
    business_id: str
    title: str
    description: Optional[str] = None
    promo_code: Optional[str] = None        # None = auto-applied
    offer_type: str                          # percentage | flat_amount | free_delivery | buy_x_get_y
    discount_value: float
    max_discount_cap: Optional[float] = None
    min_order_amount: float = 0.0
    scope: str = "all_products"             # all_products | specific_categories | specific_products | specific_collections
    scope_ids: List[str] = []
    valid_from: datetime
    valid_until: datetime
    is_auto_apply: bool = False
    usage_limit: Optional[int] = None
    per_user_limit: int = 1
    show_in_offers_panel: bool = True


class OfferUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    promo_code: Optional[str] = None
    offer_type: Optional[str] = None
    discount_value: Optional[float] = None
    max_discount_cap: Optional[float] = None
    min_order_amount: Optional[float] = None
    scope: Optional[str] = None
    scope_ids: Optional[List[str]] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_active: Optional[bool] = None
    is_auto_apply: Optional[bool] = None
    usage_limit: Optional[int] = None
    per_user_limit: Optional[int] = None
    show_in_offers_panel: Optional[bool] = None


class OfferValidateRequest(BaseModel):
    business_id: str
    promo_code: str
    cart_total: float
    cart_items: List[dict]   # [{product_id, category_id, quantity, price}]
    user_id: Optional[str] = None


# ── Helpers ────────────────────────────────────────────────────────────────

async def _require_admin(request: Request):
    from server import get_current_user
    user = await get_current_user(request)
    if user["role"] not in ("super_admin", "business_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def _check_business_access(user: dict, business_id: str):
    if user["role"] == "super_admin":
        return
    allowed = {a["business_id"] for a in user.get("business_access", [])}
    if business_id not in allowed:
        raise HTTPException(status_code=403, detail="Access denied for this business")


def _calculate_discount(offer: dict, cart_total: float, cart_items: list) -> float:
    """Return the discount amount for this offer given the cart."""
    if offer["min_order_amount"] > 0 and cart_total < offer["min_order_amount"]:
        return 0.0

    offer_type = offer["offer_type"]
    discount = 0.0

    if offer_type == "percentage":
        # Apply only to eligible items based on scope
        eligible_total = _eligible_cart_total(offer, cart_items, cart_total)
        discount = eligible_total * (offer["discount_value"] / 100)
    elif offer_type == "flat_amount":
        eligible_total = _eligible_cart_total(offer, cart_items, cart_total)
        discount = min(offer["discount_value"], eligible_total)
    elif offer_type == "free_delivery":
        discount = 0.0   # Applied at order level — delivery_charge set to 0
    elif offer_type == "buy_x_get_y":
        discount = 0.0   # Placeholder — implement per business rules

    if offer.get("max_discount_cap") and discount > offer["max_discount_cap"]:
        discount = offer["max_discount_cap"]

    return round(discount, 2)


def _eligible_cart_total(offer: dict, cart_items: list, fallback_total: float) -> float:
    """Calculate total of cart items that fall within the offer scope."""
    scope = offer.get("scope", "all_products")
    if scope == "all_products":
        return fallback_total

    scope_ids = set(offer.get("scope_ids", []))
    eligible = 0.0
    for item in cart_items:
        if scope == "specific_products" and item.get("product_id") in scope_ids:
            eligible += item.get("price", 0) * item.get("quantity", 1)
        elif scope == "specific_categories" and item.get("category_id") in scope_ids:
            eligible += item.get("price", 0) * item.get("quantity", 1)
        elif scope == "specific_collections":
            # product collection_tags checked at product-fetch time — approximate here
            eligible += item.get("price", 0) * item.get("quantity", 1)

    return eligible or fallback_total


# ── Public routes ──────────────────────────────────────────────────────────

@router.get("/offers/{business_id}")
async def list_active_offers(business_id: str):
    """Public: active offers shown in the offers panel."""
    now = datetime.now(timezone.utc)
    offers = await db.offers.find(
        {
            "business_id": business_id,
            "is_active": True,
            "show_in_offers_panel": True,
            "valid_from": {"$lte": now},
            "valid_until": {"$gte": now},
        },
        {"_id": 0},
    ).sort("created_at", -1).to_list(20)
    return {"offers": offers, "count": len(offers)}


@router.post("/offers/validate")
async def validate_offer_code(data: OfferValidateRequest):
    """
    Validate a promo code at checkout. Returns discount amount + human message.
    """
    now = datetime.now(timezone.utc)
    offer = await db.offers.find_one(
        {
            "business_id": data.business_id,
            "promo_code": {"$regex": f"^{data.promo_code}$", "$options": "i"},
            "is_active": True,
            "valid_from": {"$lte": now},
            "valid_until": {"$gte": now},
        },
        {"_id": 0},
    )

    if not offer:
        return {"is_valid": False, "discount_amount": 0.0, "message": "Invalid or expired promo code"}

    # Usage limit check
    if offer.get("usage_limit") and offer.get("usage_count", 0) >= offer["usage_limit"]:
        return {"is_valid": False, "discount_amount": 0.0, "message": "This offer has reached its usage limit"}

    # Minimum order check
    if offer["min_order_amount"] > 0 and data.cart_total < offer["min_order_amount"]:
        return {
            "is_valid": False,
            "discount_amount": 0.0,
            "message": f"Minimum order ₹{offer['min_order_amount']:.0f} required for this offer",
        }

    # Per-user limit check
    if data.user_id and offer.get("per_user_limit", 1) > 0:
        used_count = await db.orders.count_documents(
            {"user_id": data.user_id, "promo_code": offer["promo_code"]}
        )
        if used_count >= offer["per_user_limit"]:
            return {"is_valid": False, "discount_amount": 0.0, "message": "You have already used this offer"}

    discount = _calculate_discount(offer, data.cart_total, data.cart_items)
    return {
        "is_valid": True,
        "offer_id": offer["offer_id"],
        "offer": offer,
        "discount_amount": discount,
        "message": f"₹{discount:.0f} discount applied!" if discount > 0 else offer["title"],
    }


# ── Admin routes ───────────────────────────────────────────────────────────

@router.get("/admin/offers/{business_id}")
async def list_all_offers(business_id: str, request: Request):
    """Admin: all offers including expired."""
    user = await _require_admin(request)
    await _check_business_access(user, business_id)

    offers = await db.offers.find(
        {"business_id": business_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    return {"offers": offers, "total": len(offers)}


@router.post("/admin/offers")
async def create_offer(data: OfferCreate, request: Request):
    """Create a new offer."""
    user = await _require_admin(request)
    await _check_business_access(user, data.business_id)

    # Normalise promo code
    promo_code = data.promo_code.upper().strip() if data.promo_code else None

    # Check for duplicate promo code within business
    if promo_code:
        clash = await db.offers.find_one(
            {"business_id": data.business_id, "promo_code": promo_code, "is_active": True}
        )
        if clash:
            raise HTTPException(status_code=400, detail=f"Promo code '{promo_code}' already in use")

    now = datetime.now(timezone.utc)
    offer_id = f"offer_{uuid.uuid4().hex[:10]}"
    doc = {
        "offer_id": offer_id,
        **data.dict(),
        "promo_code": promo_code,
        "is_active": True,
        "usage_count": 0,
        "created_by": user["user_id"],
        "created_at": now,
        "updated_at": now,
    }
    await db.offers.insert_one(doc)
    logger.info("offer created: %s / %s by %s", data.business_id, offer_id, user["user_id"])
    return {"offer_id": offer_id, "message": "Offer created"}


@router.put("/admin/offers/{offer_id}")
async def update_offer(offer_id: str, data: OfferUpdate, request: Request):
    """Update an offer."""
    user = await _require_admin(request)

    offer = await db.offers.find_one({"offer_id": offer_id}, {"_id": 0})
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    await _check_business_access(user, offer["business_id"])

    updates = {k: v for k, v in data.dict(exclude_unset=True).items()}
    if "promo_code" in updates and updates["promo_code"]:
        updates["promo_code"] = updates["promo_code"].upper().strip()
    updates["updated_at"] = datetime.now(timezone.utc)

    await db.offers.update_one({"offer_id": offer_id}, {"$set": updates})
    return {"message": "Offer updated"}


@router.delete("/admin/offers/{offer_id}")
async def deactivate_offer(offer_id: str, request: Request):
    """Soft-delete an offer (is_active = False)."""
    user = await _require_admin(request)

    offer = await db.offers.find_one({"offer_id": offer_id}, {"_id": 0})
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    await _check_business_access(user, offer["business_id"])

    await db.offers.update_one(
        {"offer_id": offer_id},
        {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}},
    )
    return {"message": "Offer deactivated"}


@router.get("/admin/offers/{business_id}/{offer_id}/stats")
async def offer_stats(business_id: str, offer_id: str, request: Request):
    """Usage stats for a specific offer."""
    user = await _require_admin(request)
    await _check_business_access(user, business_id)

    offer = await db.offers.find_one({"offer_id": offer_id}, {"_id": 0})
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    total_orders = await db.orders.count_documents({"offer_id": offer_id})
    total_discount = 0.0
    async for order in db.orders.find({"offer_id": offer_id}, {"_id": 0, "discount_amount": 1}):
        total_discount += order.get("discount_amount", 0)

    return {
        "offer_id": offer_id,
        "usage_count": offer.get("usage_count", 0),
        "total_orders": total_orders,
        "total_discount_given": round(total_discount, 2),
    }
