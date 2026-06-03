#!/usr/bin/env python3
"""Export local MongoDB data into seed_bundle.json for seed_data.py."""
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

from bson import json_util
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

LOCAL_MONGO_URL = os.environ.get("LOCAL_MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "multi_business")
OUTPUT = ROOT_DIR / "seed_bundle.json"

# Stable catalog + demo data; skip ephemeral auth/session noise
COLLECTIONS = [
    "businesses",
    "users",
    "user_profiles",
    "products",
    "inventory",
    "saved_addresses",
    "orders",
    "loyalty_points",
    "categories",
    "reviews",
    "subscriptions",
    "custom_orders",
]


async def export_bundle():
    client = AsyncIOMotorClient(LOCAL_MONGO_URL, serverSelectionTimeoutMS=5000)
    db = client[DB_NAME]
    bundle = {"exported_at": datetime.utcnow().isoformat() + "Z", "db_name": DB_NAME, "collections": {}}

    existing = await db.list_collection_names()
    for name in COLLECTIONS:
        if name not in existing:
            continue
        docs = await db[name].find({}, {"_id": 0}).to_list(10000)
        if docs:
            bundle["collections"][name] = docs
            print(f"  {name}: {len(docs)} documents")

    OUTPUT.write_text(json_util.dumps(bundle, indent=2))
    print(f"\n✅ Wrote {OUTPUT}")
    client.close()


if __name__ == "__main__":
    print(f"Exporting from {LOCAL_MONGO_URL} / {DB_NAME} ...")
    asyncio.run(export_bundle())
