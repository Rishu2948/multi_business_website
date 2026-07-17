"""
migrations/001_add_product_fields.py

Safe, idempotent migration — adds new product fields with defaults.
Run once after deployment. Re-running is safe (only touches docs missing the fields).

Usage:
    cd backend
    python -m migrations.001_add_product_fields
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent.parent / ".env")


async def run():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    print("Migration 001: Adding new product fields...")

    # 1. Add top-level product flags with safe defaults
    r1 = await db.products.update_many(
        {"is_veg": {"$exists": False}},
        {"$set": {"is_veg": None}},
    )
    print(f"  is_veg added to {r1.modified_count} products")

    r2 = await db.products.update_many(
        {"is_featured": {"$exists": False}},
        {"$set": {"is_featured": False}},
    )
    print(f"  is_featured added to {r2.modified_count} products")

    r3 = await db.products.update_many(
        {"is_bestseller": {"$exists": False}},
        {"$set": {"is_bestseller": False}},
    )
    print(f"  is_bestseller added to {r3.modified_count} products")

    r4 = await db.products.update_many(
        {"has_active_offer": {"$exists": False}},
        {"$set": {"has_active_offer": False}},
    )
    print(f"  has_active_offer added to {r4.modified_count} products")

    r5 = await db.products.update_many(
        {"collection_tags": {"$exists": False}},
        {"$set": {"collection_tags": []}},
    )
    print(f"  collection_tags added to {r5.modified_count} products")

    r6 = await db.products.update_many(
        {"addons": {"$exists": False}},
        {"$set": {"addons": []}},
    )
    print(f"  addons added to {r6.modified_count} products")

    r7 = await db.products.update_many(
        {"allergens": {"$exists": False}},
        {"$set": {"allergens": []}},
    )
    print(f"  allergens added to {r7.modified_count} products")

    r8 = await db.products.update_many(
        {"sort_order": {"$exists": False}},
        {"$set": {"sort_order": 999}},
    )
    print(f"  sort_order added to {r8.modified_count} products")

    # 2. Move attributes.is_veg → product.is_veg where set
    products_with_attr_veg = await db.products.find(
        {"attributes.is_veg": {"$exists": True, "$ne": None}},
        {"_id": 0, "product_id": 1, "attributes": 1},
    ).to_list(10000)

    promoted = 0
    for p in products_with_attr_veg:
        await db.products.update_one(
            {"product_id": p["product_id"], "is_veg": None},
            {"$set": {"is_veg": p["attributes"]["is_veg"]}},
        )
        promoted += 1
    print(f"  is_veg promoted from attributes for {promoted} products")

    print("Migration 001 complete.")
    client.close()


if __name__ == "__main__":
    asyncio.run(run())
