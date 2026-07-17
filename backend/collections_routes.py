"""
backend/collections_routes.py

Config-driven collections system (Gifting, Festive, Corporate, etc.).
Collections are purely metadata — products are tagged via collection_tags[].
"""

from __future__ import annotations

import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

db = None

def set_db(database):
    global db
    db = database


# ── Models ─────────────────────────────────────────────────────────────────

class CollectionCreate(BaseModel):
    business_id: str
    display_name: str
    description: str = ""
    banner_image_url: Optional[str] = None
    illustration_url: Optional[str] = None
    sort_order: int = 999
    show_in_nav: bool = False
    show_on_homepage: bool = True


class CollectionUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    banner_image_url: Optional[str] = None
    illustration_url: Optional[str] = None
    sort_order: Optional[int] = None
    show_in_nav: Optional[bool] = None
    show_on_homepage: Optional[bool] = None
    is_active: Optional[bool] = None


# ── Helpers ────────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[&+]", "_and_", slug)
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return re.sub(r"_+", "_", slug).strip("_")


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


# ── Public routes ──────────────────────────────────────────────────────────

@router.get("/collections/{business_id}")
async def list_collections_public(business_id: str):
    """Public: active collections for nav/homepage tiles."""
    cols = await db.collections.find(
        {"business_id": business_id, "is_active": True},
        {"_id": 0},
    ).sort("sort_order", 1).to_list(50)
    return {"collections": cols, "total": len(cols)}


# ── Admin routes ───────────────────────────────────────────────────────────

@router.get("/admin/collections/{business_id}")
async def list_collections_admin(business_id: str, request: Request):
    user = await _require_admin(request)
    await _check_business_access(user, business_id)

    cols = await db.collections.find(
        {"business_id": business_id}, {"_id": 0}
    ).sort("sort_order", 1).to_list(100)
    return {"collections": cols, "total": len(cols)}


@router.post("/admin/collections")
async def create_collection(data: CollectionCreate, request: Request):
    user = await _require_admin(request)
    await _check_business_access(user, data.business_id)

    base_slug = _slugify(data.display_name)
    collection_id = base_slug
    existing = await db.collections.find_one(
        {"business_id": data.business_id, "collection_id": base_slug}
    )
    if existing:
        counter = 2
        while existing:
            collection_id = f"{base_slug}_{counter}"
            existing = await db.collections.find_one(
                {"business_id": data.business_id, "collection_id": collection_id}
            )
            counter += 1

    now = datetime.now(timezone.utc)
    doc = {
        "collection_id": collection_id,
        **data.dict(),
        "is_active": True,
        "created_by": user["user_id"],
        "created_at": now,
        "updated_at": now,
    }
    await db.collections.insert_one(doc)
    return {"collection_id": collection_id, "message": "Collection created"}


@router.put("/admin/collections/{business_id}/{collection_id}")
async def update_collection(
    business_id: str, collection_id: str, data: CollectionUpdate, request: Request
):
    user = await _require_admin(request)
    await _check_business_access(user, business_id)

    col = await db.collections.find_one(
        {"business_id": business_id, "collection_id": collection_id}
    )
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")

    updates = {k: v for k, v in data.dict(exclude_unset=True).items()}
    updates["updated_at"] = datetime.now(timezone.utc)
    await db.collections.update_one(
        {"business_id": business_id, "collection_id": collection_id},
        {"$set": updates},
    )
    return {"message": "Collection updated"}


@router.delete("/admin/collections/{business_id}/{collection_id}")
async def delete_collection(business_id: str, collection_id: str, request: Request):
    user = await _require_admin(request)
    await _check_business_access(user, business_id)

    result = await db.collections.update_one(
        {"business_id": business_id, "collection_id": collection_id},
        {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Collection not found")
    return {"message": "Collection deactivated"}
