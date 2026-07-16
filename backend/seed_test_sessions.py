#!/usr/bin/env python3
"""
seed_test_sessions.py — CI test data seeder

Seeds all data required by the integration test suite:
- Test users with the exact user_id values hardcoded in test files
- Session tokens (values come from GitHub Secrets / env, never hardcoded)
- Delivery agent user
- Chocolate Truffle Cake product + inventory + 5-star review
- A tracked order for TestOrderTracking
- Loyalty points document for the test customer

Required env vars:
    MONGO_URL, DB_NAME, TEST_CUSTOMER_TOKEN, TEST_ADMIN_TOKEN
"""
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent / ".env")

MONGO_URL           = os.environ.get("MONGO_URL", "")
DB_NAME             = os.environ.get("DB_NAME", "")
TEST_CUSTOMER_TOKEN = os.environ.get("TEST_CUSTOMER_TOKEN", "")
TEST_ADMIN_TOKEN    = os.environ.get("TEST_ADMIN_TOKEN", "")

missing = [k for k, v in {
    "MONGO_URL":           MONGO_URL,
    "DB_NAME":             DB_NAME,
    "TEST_CUSTOMER_TOKEN": TEST_CUSTOMER_TOKEN,
    "TEST_ADMIN_TOKEN":    TEST_ADMIN_TOKEN,
}.items() if not v.strip()]

if missing:
    print(f"ERROR: required env vars not set: {', '.join(missing)}")
    sys.exit(1)

FAR_FUTURE = datetime.now(timezone.utc) + timedelta(days=3650)

# These IDs must match what the test files hardcode
CUSTOMER_USER_ID = "test_customer_001"
ADMIN_USER_ID    = "test_admin_001"
DELIVERY_USER_ID = "user_fb1a35e23da7"
TRACKED_ORDER_ID = "ord_d6b06a5a6b26"
CHOC_PRODUCT_ID  = "prod_choc_truffle_ci"


async def seed():
    client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=10000)
    db = client[DB_NAME]

    # 1. Users
    for user in [
        {
            "user_id": CUSTOMER_USER_ID, "email": "testcustomer@whiskedwords.com",
            "name": "CI Customer", "picture": "", "role": "customer",
            "business_access": [], "status": "active", "is_prime": False,
            "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
            "last_login": datetime.now(timezone.utc),
        },
        {
            "user_id": ADMIN_USER_ID, "email": "testadmin@whiskedwords.com",
            "name": "CI Admin", "picture": "", "role": "business_admin",
            "business_access": [
                {"business_id": "whisked_words",    "role": "business_admin"},
                {"business_id": "rishabh_garments", "role": "business_admin"},
                {"business_id": "jain_jewellers",   "role": "business_admin"},
                {"business_id": "jain_sarees",      "role": "business_admin"},
            ],
            "status": "active", "is_prime": False,
            "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
            "last_login": datetime.now(timezone.utc),
        },
        {
            "user_id": DELIVERY_USER_ID, "email": "testdelivery@whiskedwords.com",
            "name": "CI Delivery Agent", "picture": "", "role": "delivery_agent",
            "business_access": [{"business_id": "whisked_words", "role": "delivery_agent"}],
            "status": "active", "is_prime": False, "phone": "9999999999",
            "base_pincode": "400001", "active_orders": 0,
            "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
            "last_login": datetime.now(timezone.utc),
        },
    ]:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": user}, upsert=True)
        print(f"  upserted user: {user['user_id']}")

    # 2. Sessions (token values come from env)
    for session in [
        {
            "session_id": "test_session_id_customer_ci", "user_id": CUSTOMER_USER_ID,
            "session_token": TEST_CUSTOMER_TOKEN, "expires_at": FAR_FUTURE,
            "created_at": datetime.now(timezone.utc), "ip_address": "127.0.0.1", "user_agent": "pytest-ci",
        },
        {
            "session_id": "test_session_id_admin_ci", "user_id": ADMIN_USER_ID,
            "session_token": TEST_ADMIN_TOKEN, "expires_at": FAR_FUTURE,
            "created_at": datetime.now(timezone.utc), "ip_address": "127.0.0.1", "user_agent": "pytest-ci",
        },
    ]:
        await db.user_sessions.update_one(
            {"session_token": session["session_token"]}, {"$set": session}, upsert=True
        )
        print(f"  upserted session: {session['user_id']}")

    # 3. Chocolate Truffle Cake — find real product or create CI one
    choc = await db.products.find_one(
        {"business_id": "whisked_words", "product_name": {"$regex": "Chocolate Truffle", "$options": "i"}},
        {"_id": 0, "product_id": 1}
    )
    choc_pid = choc["product_id"] if choc else CHOC_PRODUCT_ID
    if not choc:
        await db.products.update_one(
            {"product_id": choc_pid},
            {"$set": {
                "product_id": choc_pid, "business_id": "whisked_words",
                "product_name": "Chocolate Truffle Cake", "base_price": 850.0,
                "currency": "INR", "status": "active", "category_id": "cat_cakes",
                "description": "Rich chocolate cake", "images": [],
                "attributes": {"flavor": "chocolate", "weight": "500g"}, "variants": [],
            }},
            upsert=True
        )
        print(f"  upserted CI Chocolate Truffle Cake: {choc_pid}")
    else:
        print(f"  found Chocolate Truffle Cake: {choc_pid}")

    # 4. Inventory for Chocolate Truffle Cake (needed by order creation tests)
    await db.inventory.update_one(
        {"product_id": choc_pid, "variant_id": None},
        {"$set": {
            "inventory_id": f"inv_ci_{choc_pid}", "business_id": "whisked_words",
            "product_id": choc_pid, "variant_id": None, "sku": "CI-CHOC-001",
            "quantity": {"available": 100, "reserved": 0, "total": 100},
            "last_restocked": datetime.now(timezone.utc), "last_updated": datetime.now(timezone.utc),
        }},
        upsert=True
    )
    print(f"  ensured inventory for: {choc_pid}")

    # 5. 5-star review for Chocolate Truffle Cake
    await db.reviews.update_one(
        {"product_id": choc_pid, "user_id": CUSTOMER_USER_ID},
        {"$set": {
            "review_id": f"rev_ci_{choc_pid}", "product_id": choc_pid,
            "user_id": CUSTOMER_USER_ID, "user_name": "CI Customer",
            "rating": 5, "comment": "CI seed review",
            "created_at": datetime.now(timezone.utc),
        }},
        upsert=True
    )
    print(f"  upserted 5-star review for: {choc_pid}")

    # 6. Tracked order (TestOrderTracking uses hardcoded ord_d6b06a5a6b26)
    await db.orders.update_one(
        {"order_id": TRACKED_ORDER_ID},
        {"$set": {
            "order_id": TRACKED_ORDER_ID, "user_id": CUSTOMER_USER_ID,
            "business_id": "whisked_words",
            "items": [{"product_id": choc_pid, "product_name": "Chocolate Truffle Cake",
                       "quantity": 1, "price": 850.0, "subtotal": 850.0, "variant_id": None}],
            "delivery_info": {"name": "CI Customer", "phone": "9876543210",
                              "email": "testcustomer@whiskedwords.com",
                              "address": "123 CI Street", "city": "Bangalore",
                              "state": "Karnataka", "pincode": "560001"},
            "payment_method": "cod", "payment_status": "pending", "order_status": "pending",
            "subtotal": 850.0, "tax": 153.0, "delivery_charge": 50.0, "total": 1053.0,
            "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        }},
        upsert=True
    )
    print(f"  upserted tracked order: {TRACKED_ORDER_ID}")

    # 7. Loyalty points for test customer
    await db.loyalty_points.update_one(
        {"user_id": CUSTOMER_USER_ID},
        {"$setOnInsert": {
            "user_id": CUSTOMER_USER_ID, "points": 0,
            "total_earned": 0, "total_redeemed": 0, "tier": "bronze",
        }},
        upsert=True
    )
    print(f"  ensured loyalty_points for: {CUSTOMER_USER_ID}")

    client.close()
    print("done.")


if __name__ == "__main__":
    asyncio.run(seed())
