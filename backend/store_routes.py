"""
backend/store_routes.py

Config-driven store settings: hours, order types, delivery config.
All values editable by super_admin or business_admin — no code changes needed.
"""

from __future__ import annotations

import logging
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

class BusinessHours(BaseModel):
    day: str            # "monday" … "sunday"
    is_open: bool = True
    open_time: str = "08:00"   # HH:MM 24h
    close_time: str = "22:00"


class StoreConfigUpdate(BaseModel):
    store_display_name: Optional[str] = None
    location_label: Optional[str] = None
    is_temporarily_closed: Optional[bool] = None
    closed_reason: Optional[str] = None
    business_hours: Optional[List[BusinessHours]] = None
    order_types: Optional[List[str]] = None   # ["delivery","takeaway","dine_in"]
    delivery_radius_km: Optional[float] = None
    min_order_delivery: Optional[float] = None
    delivery_charge: Optional[float] = None
    free_delivery_above: Optional[float] = None
    estimated_delivery_time: Optional[str] = None
    estimated_prep_time: Optional[str] = None
    currency: Optional[str] = None
    currency_symbol: Optional[str] = None
    tax_rate: Optional[float] = None


_DEFAULT_HOURS = [
    {"day": d, "is_open": True, "open_time": "08:00", "close_time": "22:00"}
    for d in ("monday","tuesday","wednesday","thursday","friday","saturday","sunday")
]

_DEFAULT_CONFIG = {
    "store_display_name": "",
    "location_label": "",
    "is_temporarily_closed": False,
    "closed_reason": None,
    "business_hours": _DEFAULT_HOURS,
    "order_types": ["delivery"],
    "delivery_radius_km": 10.0,
    "min_order_delivery": 199.0,
    "delivery_charge": 50.0,
    "free_delivery_above": None,
    "estimated_delivery_time": "30-45 mins",
    "estimated_prep_time": "15-20 mins",
    "currency": "INR",
    "currency_symbol": "₹",
    "tax_rate": 0.05,
}


def _compute_is_open(config: dict) -> bool:
    """Determine if the store is currently open based on its hour config."""
    if config.get("is_temporarily_closed"):
        return False
    try:
        import pytz
        now = datetime.now(pytz.timezone("Asia/Kolkata"))
    except Exception:
        now = datetime.now(timezone.utc)

    day_name = now.strftime("%A").lower()
    hours = config.get("business_hours", _DEFAULT_HOURS)
    today = next((h for h in hours if h["day"] == day_name), None)
    if not today or not today.get("is_open", True):
        return False

    current_hhmm = now.strftime("%H:%M")
    return today.get("open_time", "00:00") <= current_hhmm <= today.get("close_time", "23:59")


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


# ── Public route ───────────────────────────────────────────────────────────

@router.get("/store/info/{business_id}")
async def get_store_info(business_id: str):
    """
    Public: returns current store status for the order navbar.
    Falls back to sensible defaults if store_config document doesn't exist yet.
    """
    config = await db.store_config.find_one({"business_id": business_id}, {"_id": 0})

    if not config:
        # Bootstrap from the business document
        biz = await db.businesses.find_one({"business_id": business_id}, {"_id": 0})
        if not biz:
            raise HTTPException(status_code=404, detail="Business not found")
        config = {
            **_DEFAULT_CONFIG,
            "business_id": business_id,
            "store_display_name": biz.get("business_name", ""),
            "location_label": biz.get("contact", {}).get("city", ""),
        }

    config["is_open"] = _compute_is_open(config)
    config.pop("_id", None)
    return config


# ── Admin routes ───────────────────────────────────────────────────────────

@router.get("/admin/store/{business_id}")
async def get_store_config_admin(business_id: str, request: Request):
    """Admin: full store config including all editable fields."""
    user = await _require_admin(request)
    await _check_business_access(user, business_id)

    config = await db.store_config.find_one({"business_id": business_id}, {"_id": 0})
    if not config:
        biz = await db.businesses.find_one({"business_id": business_id}, {"_id": 0})
        config = {
            **_DEFAULT_CONFIG,
            "business_id": business_id,
            "store_display_name": biz.get("business_name", "") if biz else "",
            "location_label": biz.get("contact", {}).get("city", "") if biz else "",
        }
    config["is_open"] = _compute_is_open(config)
    config.pop("_id", None)
    return config


@router.put("/admin/store/{business_id}")
async def upsert_store_config(business_id: str, data: StoreConfigUpdate, request: Request):
    """Full replacement of store config. Creates document if it doesn't exist."""
    user = await _require_admin(request)
    await _check_business_access(user, business_id)

    updates = data.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided")

    # Serialise BusinessHours objects to plain dicts
    if "business_hours" in updates and updates["business_hours"]:
        updates["business_hours"] = [
            h.dict() if hasattr(h, "dict") else h
            for h in updates["business_hours"]
        ]

    updates["updated_at"] = datetime.now(timezone.utc)

    await db.store_config.update_one(
        {"business_id": business_id},
        {"$set": updates, "$setOnInsert": {"business_id": business_id, "created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    logger.info("store config updated for %s by %s", business_id, user["user_id"])
    return {"message": "Store config updated"}


@router.patch("/admin/store/{business_id}")
async def patch_store_config(business_id: str, request: Request):
    """
    Partial update — accepts any subset of fields as raw JSON.
    Useful for quick toggles like is_temporarily_closed.
    """
    user = await _require_admin(request)
    await _check_business_access(user, business_id)

    data = await request.json()
    data.pop("business_id", None)   # prevent overwrite of the key field
    data["updated_at"] = datetime.now(timezone.utc)

    await db.store_config.update_one(
        {"business_id": business_id},
        {"$set": data, "$setOnInsert": {"business_id": business_id, "created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {"message": "Store config patched"}
