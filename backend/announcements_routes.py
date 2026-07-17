"""
backend/announcements_routes.py

Config-driven announcement bar. Admins create/edit messages via dashboard.
The customer-facing bar fetches the highest-priority active announcement.
"""

from __future__ import annotations

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

class AnnouncementCreate(BaseModel):
    business_id: str
    message: str
    link_url: Optional[str] = None
    link_text: Optional[str] = None
    bg_color: str = "#4A3B32"
    text_color: str = "#FAF8F5"
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    priority: int = 0    # higher = shown first when multiple are active


class AnnouncementUpdate(BaseModel):
    message: Optional[str] = None
    link_url: Optional[str] = None
    link_text: Optional[str] = None
    bg_color: Optional[str] = None
    text_color: Optional[str] = None
    is_active: Optional[bool] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    priority: Optional[int] = None


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


# ── Public routes ──────────────────────────────────────────────────────────

@router.get("/announcements/{business_id}")
async def get_active_announcement(business_id: str):
    """
    Public: returns the highest-priority active announcement for the bar.
    Returns null if none active — frontend should render nothing.
    """
    now = datetime.now(timezone.utc)
    query: dict = {
        "business_id": business_id,
        "is_active": True,
    }
    # Optional time-window filtering
    # valid_from/valid_until are optional — if missing the announcement is always valid
    time_query = [
        {"valid_from": {"$exists": False}},
        {"valid_from": None},
        {"valid_from": {"$lte": now}},
    ]
    time_end_query = [
        {"valid_until": {"$exists": False}},
        {"valid_until": None},
        {"valid_until": {"$gte": now}},
    ]
    query["$and"] = [
        {"$or": time_query},
        {"$or": time_end_query},
    ]

    ann = await db.announcements.find_one(
        query,
        {"_id": 0},
        sort=[("priority", -1)],
    )
    return {"announcement": ann}


# ── Admin routes ───────────────────────────────────────────────────────────

@router.get("/admin/announcements/{business_id}")
async def list_announcements(business_id: str, request: Request):
    user = await _require_admin(request)
    await _check_business_access(user, business_id)

    anns = await db.announcements.find(
        {"business_id": business_id}, {"_id": 0}
    ).sort("priority", -1).to_list(50)
    return {"announcements": anns, "total": len(anns)}


@router.post("/admin/announcements")
async def create_announcement(data: AnnouncementCreate, request: Request):
    user = await _require_admin(request)
    await _check_business_access(user, data.business_id)

    now = datetime.now(timezone.utc)
    ann_id = f"ann_{uuid.uuid4().hex[:10]}"
    doc = {
        "announcement_id": ann_id,
        **data.dict(),
        "is_active": True,
        "created_by": user["user_id"],
        "created_at": now,
        "updated_at": now,
    }
    await db.announcements.insert_one(doc)
    return {"announcement_id": ann_id, "message": "Announcement created"}


@router.put("/admin/announcements/{announcement_id}")
async def update_announcement(
    announcement_id: str, data: AnnouncementUpdate, request: Request
):
    user = await _require_admin(request)

    ann = await db.announcements.find_one({"announcement_id": announcement_id}, {"_id": 0})
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")
    await _check_business_access(user, ann["business_id"])

    updates = {k: v for k, v in data.dict(exclude_unset=True).items()}
    updates["updated_at"] = datetime.now(timezone.utc)
    await db.announcements.update_one(
        {"announcement_id": announcement_id}, {"$set": updates}
    )
    return {"message": "Announcement updated"}


@router.delete("/admin/announcements/{announcement_id}")
async def delete_announcement(announcement_id: str, request: Request):
    user = await _require_admin(request)

    ann = await db.announcements.find_one({"announcement_id": announcement_id}, {"_id": 0})
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")
    await _check_business_access(user, ann["business_id"])

    await db.announcements.delete_one({"announcement_id": announcement_id})
    return {"message": "Announcement deleted"}
