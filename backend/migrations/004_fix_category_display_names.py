"""
migrations/004_fix_category_display_names.py

Fixes display names for categories seeded by expand_bakery_seed.py
which used "cat_cakes", "cat_pastries" etc. as category_id values.
Also sets reasonable sort_order so categories appear in logical order.

Safe to re-run — only updates, never inserts.

Usage:
    cd backend
    python3 -m migrations.004_fix_category_display_names
"""

import asyncio
import os
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent.parent / ".env")

# Map category_id → (display_name, icon_emoji, sort_order)
CATEGORY_FIX_MAP = {
    # Seeded by expand_bakery_seed.py
    "cat_cakes":     ("Cakes",                  "🎂", 10),
    "cat_pastries":  ("Pastries",               "🥐", 20),
    "cat_breads":    ("Breads",                 "🍞", 30),
    "cat_cookies":   ("Cookies & Biscuits",     "🍪", 40),
    "cat_muffins":   ("Muffins & Cupcakes",     "🧁", 50),
    "cat_specials":  ("Seasonal Specials",      "✨", 60),

    # Seeded by original seed_data / seed_bundle
    "featured":         ("Featured Items",      "⭐", 1),
    "value_combos":     ("Value Combos",        "💰", 2),
    "cakes":            ("Cakes",               "🎂", 10),
    "pastries":         ("Pastries",            "🥐", 20),
    "brownies":         ("Brownies",            "🍫", 25),
    "desserts_cupcakes":("Desserts & Cupcakes", "🧁", 30),
    "sandwiches":       ("Sandwiches & Savouries","🥪", 35),
    "croissants":       ("Croissants, Danishes & Muffins","🥐", 40),
    "tea_cakes":        ("Tea Cakes",           "🍰", 45),
    "biscuits":         ("Biscuits & Crackers", "🍪", 50),
    "gifting":          ("Gifting",             "🎁", 55),
    "breads":           ("Breads",              "🍞", 60),
    "cake_addons":      ("Cake Add-Ons",        "🎀", 65),
    "beverages":        ("Beverages",           "☕", 70),
    "snacks":           ("Snacks",              "🥨", 75),
    "namkeen":          ("Namkeen",             "🥨", 76),
}


async def run():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    now = datetime.now(timezone.utc)
    updated = 0
    skipped = 0

    print("Migration 004: Fixing category display names and sort orders...")

    for category_id, (display_name, icon_emoji, sort_order) in CATEGORY_FIX_MAP.items():
        result = await db.categories.update_many(
            {"category_id": category_id},
            {"$set": {
                "display_name": display_name,
                "icon_emoji": icon_emoji,
                "sort_order": sort_order,
                "updated_at": now,
            }}
        )
        if result.modified_count > 0:
            updated += result.modified_count
            print(f"  ✅ Updated: {category_id} → '{display_name}' (sort: {sort_order})")
        else:
            skipped += 1

    print(f"\nMigration 004 complete — updated {updated}, not found/unchanged: {skipped}")
    client.close()


if __name__ == "__main__":
    asyncio.run(run())
