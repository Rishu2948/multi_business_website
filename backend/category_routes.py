"""
backend/category_routes.py

Config-driven category management. Categories live in the `categories`
MongoDB collection — no hardcoded name maps anywhere in the codebase.

Accessible to:
  - super_admin : any business
  - business_admin : own business only
  - public GET /api/categories/:businessId — for customer-facing sidebar
"""

from __future__ import annotations

import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

db = None

def set_db(database):
    global db
    db = database


# ── Pydantic models ────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    business_id: str
    display_name: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    icon_emoji: Optional[str] = None
    parent_category_id: Optional[str] = None
    sort_order: int = 999
    is_featured: bool = False


class CategoryUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    icon_emoji: Optional[str] = None
    parent_category_id: Optional[str] = None
    sort_order: Optional[int] = None
    is_featured: Optional[bool] = None
    is_active: Optional[bool] = None


class CategoryReorderItem(BaseModel):
    category_id: str
    sort_order: int


# ── Helpers ────────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    """Convert display name to a URL-safe category_id slug.
    e.g. "Namkeen & Snacks" → "namkeen_snacks"
    """
    slug = name.lower().strip()
    slug = re.sub(r"[&+]", "_and_", slug)
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug


async def _get_user(request: Request):
    from server import get_current_user
    return await get_current_user(request)


async def _require_admin(request: Request):
    user = await _get_user(request)
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

@router.get("/categories/{business_id}")
async def list_categories_public(business_id: str, is_featured: bool = None):
    """
    Public endpoint used by the customer-facing sidebar and homepage tiles.
    Returns only active categories, sorted by sort_order.
    """
    query: dict = {"business_id": business_id, "is_active": True}
    if is_featured is not None:
        query["is_featured"] = is_featured

    cats = await db.categories.find(query, {"_id": 0}).sort("sort_order", 1).to_list(200)
    return {"categories": cats, "total": len(cats)}


# ── Admin routes ───────────────────────────────────────────────────────────

@router.get("/admin/categories/{business_id}")
async def list_categories_admin(business_id: str, request: Request):
    """Admin: list all categories (including inactive)."""
    user = await _require_admin(request)
    await _check_business_access(user, business_id)

    cats = await db.categories.find(
        {"business_id": business_id}, {"_id": 0}
    ).sort("sort_order", 1).to_list(200)
    return {"categories": cats, "total": len(cats)}


@router.post("/admin/categories")
async def create_category(data: CategoryCreate, request: Request):
    """
    Create a new category. The category_id slug is auto-generated from
    display_name — no developer input needed.
    """
    user = await _require_admin(request)
    await _check_business_access(user, data.business_id)

    base_slug = _slugify(data.display_name)
    category_id = base_slug

    # Ensure uniqueness within business — append counter if clash
    existing = await db.categories.find_one(
        {"business_id": data.business_id, "category_id": base_slug}
    )
    if existing:
        counter = 2
        while existing:
            category_id = f"{base_slug}_{counter}"
            existing = await db.categories.find_one(
                {"business_id": data.business_id, "category_id": category_id}
            )
            counter += 1

    now = datetime.now(timezone.utc)
    doc = {
        "category_id": category_id,
        "business_id": data.business_id,
        "display_name": data.display_name,
        "description": data.description or "",
        "image_url": data.image_url,
        "icon_emoji": data.icon_emoji,
        "parent_category_id": data.parent_category_id,
        "sort_order": data.sort_order,
        "is_featured": data.is_featured,
        "is_active": True,
        "product_count": 0,
        "created_by": user["user_id"],
        "created_at": now,
        "updated_at": now,
    }
    await db.categories.insert_one(doc)
    logger.info("category created: %s / %s by %s", data.business_id, category_id, user["user_id"])
    return {"category_id": category_id, "message": "Category created"}


@router.put("/admin/categories/{business_id}/{category_id}")
async def update_category(
    business_id: str,
    category_id: str,
    data: CategoryUpdate,
    request: Request,
):
    """Update category fields. Any field omitted keeps its existing value."""
    user = await _require_admin(request)
    await _check_business_access(user, business_id)

    cat = await db.categories.find_one(
        {"business_id": business_id, "category_id": category_id}
    )
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    updates = {k: v for k, v in data.dict(exclude_unset=True).items() if v is not None or k in ("is_active", "is_featured", "sort_order")}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates["updated_at"] = datetime.now(timezone.utc)
    await db.categories.update_one(
        {"business_id": business_id, "category_id": category_id},
        {"$set": updates},
    )
    return {"message": "Category updated"}


@router.delete("/admin/categories/{business_id}/{category_id}")
async def delete_category(business_id: str, category_id: str, request: Request):
    """
    Soft-delete a category (is_active = False).
    Products in this category are NOT deleted — they just won't show in nav.
    """
    user = await _require_admin(request)
    await _check_business_access(user, business_id)

    result = await db.categories.update_one(
        {"business_id": business_id, "category_id": category_id},
        {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"message": "Category deactivated"}


@router.put("/admin/categories/{business_id}/reorder/bulk")
async def reorder_categories(
    business_id: str,
    items: list[CategoryReorderItem],
    request: Request,
):
    """
    Bulk update sort_order for drag-and-drop reordering.
    Accepts [{category_id, sort_order}, ...].
    """
    user = await _require_admin(request)
    await _check_business_access(user, business_id)

    from pymongo import UpdateOne
    ops = [
        UpdateOne(
            {"business_id": business_id, "category_id": item.category_id},
            {"$set": {"sort_order": item.sort_order, "updated_at": datetime.now(timezone.utc)}},
        )
        for item in items
    ]
    if ops:
        await db.categories.bulk_write(ops, ordered=False)

    return {"message": f"Reordered {len(ops)} categories"}
