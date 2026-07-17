"""
migrations/002_seed_categories.py

Reads distinct category_id values already on products and creates
category documents for any that are missing. Idempotent — safe to re-run.

After this runs, admins can rename/reorder/add-image via the Category Manager UI.

Usage:
    cd backend
    python -m migrations.002_seed_categories
"""

import asyncio
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent.parent / ".env")

# Human-readable defaults for known slugs — admin can override via UI
KNOWN_NAMES: dict[str, str] = {
    "featured":           "Featured Items",
    "value_combos":       "Value Combos",
    "cakes":              "Cakes",
    "pastries":           "Pastries",
    "brownies":           "Brownies",
    "desserts_cupcakes":  "Desserts & Cupcakes",
    "sandwiches":         "Sandwiches & Savouries",
    "croissants":         "Croissants, Danishes & Muffins",
    "tea_cakes":          "Tea Cakes",
    "biscuits":           "Biscuits, Cookies & Crackers",
    "gifting":            "Gifting",
    "breads":             "Breads",
    "cake_addons":        "Cake Add-Ons",
    "beverages":          "Beverages",
    "snacks":             "Snacks",
    "namkeen":            "Namkeen",
}


def _auto_display_name(slug: str) -> str:
    return KNOWN_NAMES.get(slug, slug.replace("_", " ").title())


async def run():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    print("Migration 002: Seeding categories from existing product category_ids...")

    # Find all distinct (business_id, category_id) pairs across products
    pipeline = [
        {"$match": {"category_id": {"$exists": True, "$ne": None}}},
        {"$group": {
            "_id": {"business_id": "$business_id", "category_id": "$category_id"},
            "count": {"$sum": 1},
        }},
    ]
    combos = await db.products.aggregate(pipeline).to_list(10000)
    print(f"  Found {len(combos)} distinct business+category pairs")

    created = 0
    skipped = 0
    now = datetime.now(timezone.utc)

    for combo in combos:
        business_id = combo["_id"]["business_id"]
        category_id = combo["_id"]["category_id"]
        product_count = combo["count"]

        # Skip if category doc already exists
        existing = await db.categories.find_one(
            {"business_id": business_id, "category_id": category_id}
        )
        if existing:
            skipped += 1
            continue

        display_name = _auto_display_name(category_id)
        doc = {
            "category_id": category_id,
            "business_id": business_id,
            "display_name": display_name,
            "description": "",
            "image_url": None,
            "icon_emoji": None,
            "parent_category_id": None,
            "sort_order": 999,
            "is_featured": category_id == "featured",
            "is_active": True,
            "product_count": product_count,
            "created_by": "migration",
            "created_at": now,
            "updated_at": now,
        }
        await db.categories.insert_one(doc)
        created += 1
        print(f"  Created: {business_id} / {category_id} ({display_name})")

    print(f"Migration 002 complete — created {created}, skipped {skipped} existing.")
    client.close()


if __name__ == "__main__":
    asyncio.run(run())
