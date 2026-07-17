"""
Business Config Routes

Manages business-wide configuration including Prime settings.
Separate from store_config to support multiple stores per business.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from prime.models import PrimeFeatureConfig, PrimePlanConfig, PrimeConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

db = None


def set_db(database):
    global db
    db = database


# ── Models ─────────────────────────────────────────────────────────────────

class BusinessConfigUpdate(BaseModel):
    prime: Optional[PrimeConfig] = None


# ── Helper Functions ───────────────────────────────────────────────────────

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


# ── Public Route ───────────────────────────────────────────────────────────

@router.get("/prime/info/{business_id}")
async def get_prime_info_public(business_id: str):
    """
    Public: returns Prime availability summary for upgrade page.
    """
    config = await db.business_config.find_one(
        {"business_id": business_id},
        {"_id": 0, "prime.enabled": 1, "prime.display_name": 1, "prime.tagline": 1}
    )

    if not config:
        raise HTTPException(
            status_code=404,
            detail=f"Prime not configured for business: {business_id}"
        )

    prime = config.get("prime", {})
    return {
        "enabled": prime.get("enabled", False),
        "display_name": prime.get("display_name", ""),
        "tagline": prime.get("tagline", ""),
    }


# ── Admin Routes ───────────────────────────────────────────────────────────

@router.get("/admin/business-config/{business_id}")
async def get_business_config_admin(business_id: str, request: Request):
    """Admin: full business config including Prime settings."""
    user = await _require_admin(request)
    await _check_business_access(user, business_id)

    config = await db.business_config.find_one(
        {"business_id": business_id},
        {"_id": 0}
    )

    if not config:
        # Return empty config for new businesses
        return {
            "business_id": business_id,
            "prime": {
                "enabled": False,
                "display_name": "",
                "tagline": "",
                "plans": [],
                "features": {}
            }
        }

    return config


@router.put("/admin/business-config/{business_id}")
async def upsert_business_config(business_id: str, data: BusinessConfigUpdate, request: Request):
    """Full replacement of business config. Creates document if it doesn't exist."""
    user = await _require_admin(request)
    await _check_business_access(user, business_id)

    if not data.prime:
        raise HTTPException(status_code=400, detail="No prime configuration provided")

    # Use the full prime dict to ensure nested fields like features are saved
    updates = {"prime": data.prime.dict()}
    updates["updated_at"] = datetime.now(timezone.utc)

    await db.business_config.update_one(
        {"business_id": business_id},
        {
            "$set": updates,
            "$setOnInsert": {
                "business_id": business_id,
                "created_at": datetime.now(timezone.utc)
            }
        },
        upsert=True,
    )
    logger.info("business config updated for %s by %s", business_id, user["user_id"])
    return {"message": "Business config updated"}
