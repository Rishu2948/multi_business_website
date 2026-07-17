"""
migrations/003_seed_store_config_and_offers.py

Seeds:
  - store_config document for whisked_words
  - 2 sample offers
  - 2 sample announcements

Safe to re-run: uses upsert/insert-if-not-exists.

Usage:
    cd backend
    python3 -m migrations.003_seed_store_config_and_offers
"""

import asyncio
import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent.parent / ".env")

BUSINESS_ID = "whisked_words"


async def run():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    now = datetime.now(timezone.utc)

    # ── 1. Store config ────────────────────────────────────────────────────
    existing_store = await db.store_config.find_one({"business_id": BUSINESS_ID})
    if not existing_store:
        store_doc = {
            "business_id": BUSINESS_ID,
            "store_display_name": "Whisked Words",
            "location_label": "Indiranagar, Bengaluru",
            "is_temporarily_closed": False,
            "closed_reason": None,
            "business_hours": [
                {"day": d, "is_open": True, "open_time": "08:00", "close_time": "22:00"}
                for d in ("monday","tuesday","wednesday","thursday","friday")
            ] + [
                {"day": "saturday", "is_open": True, "open_time": "09:00", "close_time": "23:00"},
                {"day": "sunday",   "is_open": True, "open_time": "10:00", "close_time": "21:00"},
            ],
            "order_types": ["delivery", "takeaway"],
            "delivery_radius_km": 10.0,
            "min_order_delivery": 199.0,
            "delivery_charge": 50.0,
            "free_delivery_above": 499.0,
            "estimated_delivery_time": "30-45 mins",
            "estimated_prep_time": "15-20 mins",
            "currency": "INR",
            "currency_symbol": "₹",
            "tax_rate": 0.05,
            "updated_at": now,
        }
        await db.store_config.insert_one(store_doc)
        print("  ✅ store_config created for whisked_words")
    else:
        print("  ⏭  store_config already exists — skipped")

    # ── 2. Sample offers ───────────────────────────────────────────────────
    existing_offers = await db.offers.count_documents({"business_id": BUSINESS_ID})
    if existing_offers == 0:
        offers = [
            {
                "offer_id": f"offer_{uuid.uuid4().hex[:10]}",
                "business_id": BUSINESS_ID,
                "title": "₹200 OFF on First Order",
                "description": "Use code FIRST200 on your first order",
                "promo_code": "FIRST200",
                "offer_type": "flat_amount",
                "discount_value": 200.0,
                "max_discount_cap": None,
                "min_order_amount": 499.0,
                "scope": "all_products",
                "scope_ids": [],
                "valid_from": now,
                "valid_until": now + timedelta(days=365),
                "is_active": True,
                "is_auto_apply": False,
                "usage_limit": 1000,
                "usage_count": 0,
                "per_user_limit": 1,
                "show_in_offers_panel": True,
                "created_by": "migration",
                "created_at": now,
                "updated_at": now,
            },
            {
                "offer_id": f"offer_{uuid.uuid4().hex[:10]}",
                "business_id": BUSINESS_ID,
                "title": "FLAT 15% OFF on Cakes",
                "description": "Valid on all cakes — no minimum order",
                "promo_code": "CAKE15",
                "offer_type": "percentage",
                "discount_value": 15.0,
                "max_discount_cap": 500.0,
                "min_order_amount": 0.0,
                "scope": "specific_categories",
                "scope_ids": ["cakes"],
                "valid_from": now,
                "valid_until": now + timedelta(days=90),
                "is_active": True,
                "is_auto_apply": False,
                "usage_limit": None,
                "usage_count": 0,
                "per_user_limit": 5,
                "show_in_offers_panel": True,
                "created_by": "migration",
                "created_at": now,
                "updated_at": now,
            },
        ]
        await db.offers.insert_many(offers)
        print(f"  ✅ {len(offers)} sample offers created")
    else:
        print(f"  ⏭  {existing_offers} offer(s) already exist — skipped")

    # ── 3. Sample announcements ────────────────────────────────────────────
    existing_anns = await db.announcements.count_documents({"business_id": BUSINESS_ID})
    if existing_anns == 0:
        ann = {
            "announcement_id": f"ann_{uuid.uuid4().hex[:10]}",
            "business_id": BUSINESS_ID,
            "message": "Upto ₹200 OFF on the First Order. Use code FIRST200. T&C apply.",
            "link_url": None,
            "link_text": None,
            "bg_color": "#4A3B32",
            "text_color": "#FAF8F5",
            "is_active": True,
            "valid_from": None,
            "valid_until": None,
            "priority": 10,
            "created_by": "migration",
            "created_at": now,
            "updated_at": now,
        }
        await db.announcements.insert_one(ann)
        print("  ✅ sample announcement created")
    else:
        print(f"  ⏭  {existing_anns} announcement(s) already exist — skipped")

    print("Migration 003 complete.")
    client.close()


if __name__ == "__main__":
    asyncio.run(run())
