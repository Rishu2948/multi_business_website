#!/usr/bin/env python3
"""
Load seed_bundle.json (exported from local MongoDB) into a target database.

Usage:
  # Export local DB → seed_bundle.json
  ./venv/bin/python export_seed_bundle.py

  # Reseed cloud (uses MONGO_URL + DB_NAME from .env)
  ./venv/bin/python seed_data.py --force

  # Reseed local
  LOCAL_MONGO_URL=mongodb://localhost:27017 ./venv/bin/python seed_data.py --force
"""
import argparse
import asyncio
import os
from pathlib import Path
from typing import Optional

from bson import json_util
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

BUNDLE_PATH = ROOT_DIR / "seed_bundle.json"

# Insert order respects typical references (users before orders, etc.)
SEED_ORDER = [
    "businesses",
    "users",
    "user_profiles",
    "categories",
    "products",
    "inventory",
    "saved_addresses",
    "loyalty_points",
    "orders",
    "custom_orders",
    "reviews",
    "subscriptions",
]


def load_bundle() -> dict:
    if not BUNDLE_PATH.exists():
        raise FileNotFoundError(
            f"{BUNDLE_PATH} not found. Run: ./venv/bin/python export_seed_bundle.py"
        )
    return json_util.loads(BUNDLE_PATH.read_text())


async def seed_data(force: bool = False, mongo_url: Optional[str] = None):
    bundle = load_bundle()
    collections = bundle.get("collections", {})

    url = mongo_url or os.environ["MONGO_URL"]
    db_name = os.environ.get("DB_NAME", bundle.get("db_name", "multi_business"))

    print(f"🌱 Seeding {db_name} at {url[:50]}...")
    client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=10000)
    db = client[db_name]

    # Collections we will replace (only those present in bundle)
    to_seed = [c for c in SEED_ORDER if c in collections]
    for c in collections:
        if c not in to_seed:
            to_seed.append(c)

    if not force:
        existing = await db.businesses.count_documents({})
        if existing > 0:
            print("✅ Data already present. Use --force to clear and reseed.")
            client.close()
            return

    if force:
        print("🗑️  Clearing existing seed collections...")
        for name in reversed(to_seed):
            await db[name].delete_many({})

    total = 0
    for name in to_seed:
        docs = collections[name]
        if not docs:
            continue
        await db[name].insert_many(docs)
        total += len(docs)
        print(f"  ✅ {name}: {len(docs)} documents")

    print(f"\n✨ Seeding completed ({total} documents across {len(to_seed)} collections).")
    if "users" in collections:
        admins = [u["email"] for u in collections["users"] if u.get("role") == "super_admin"]
        if admins:
            print(f"📝 Super admin login emails: {', '.join(admins)}")

    client.close()


def main():
    parser = argparse.ArgumentParser(description="Seed database from seed_bundle.json")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Clear seed collections and re-insert bundle data",
    )
    parser.add_argument(
        "--mongo-url",
        default=None,
        help="Override MONGO_URL (default: from .env)",
    )
    args = parser.parse_args()
    asyncio.run(seed_data(force=args.force, mongo_url=args.mongo_url))


if __name__ == "__main__":
    main()
