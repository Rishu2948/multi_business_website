#!/usr/bin/env python3
"""
seed_test_sessions.py
---------------------
Inserts CI test session tokens into MongoDB so the integration tests can
authenticate. Token values are never hardcoded here — they are read from
environment variables (set as GitHub Secrets in CI, or locally via .env).

Required env vars:
    MONGO_URL              — MongoDB connection string
    DB_NAME                — database name
    TEST_CUSTOMER_TOKEN    — Bearer token the tests send as the customer
    TEST_ADMIN_TOKEN       — Bearer token the tests send as the admin

In CI these come from GitHub Secrets.
Locally you can add them to backend/.env for development.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent / ".env")

MONGO_URL            = os.environ["MONGO_URL"]
DB_NAME              = os.environ["DB_NAME"]
TEST_CUSTOMER_TOKEN  = os.environ["TEST_CUSTOMER_TOKEN"]
TEST_ADMIN_TOKEN     = os.environ["TEST_ADMIN_TOKEN"]

FAR_FUTURE = datetime.now(timezone.utc) + timedelta(days=3650)   # ~10 years


async def seed():
    client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=10000)
    db     = client[DB_NAME]

    # ── Users ─────────────────────────────────────────────────────────────
    test_users = [
        {
            "user_id":         "test_user_customer_ci",
            "email":           "testcustomer@ci.local",
            "name":            "CI Customer",
            "picture":         "",
            "role":            "customer",
            "business_access": [],
            "status":          "active",
            "is_prime":        False,
            "created_at":      datetime.now(timezone.utc),
            "updated_at":      datetime.now(timezone.utc),
            "last_login":      datetime.now(timezone.utc),
        },
        {
            "user_id":         "test_user_admin_ci",
            "email":           "testadmin@ci.local",
            "name":            "CI Admin",
            "picture":         "",
            "role":            "business_admin",
            "business_access": [
                {"business_id": "whisked_words",    "role": "business_admin"},
                {"business_id": "rishabh_garments", "role": "business_admin"},
                {"business_id": "jain_jewellers",   "role": "business_admin"},
                {"business_id": "jain_sarees",      "role": "business_admin"},
            ],
            "status":          "active",
            "is_prime":        False,
            "created_at":      datetime.now(timezone.utc),
            "updated_at":      datetime.now(timezone.utc),
            "last_login":      datetime.now(timezone.utc),
        },
    ]

    # ── Sessions — tokens come from env, not from this file ───────────────
    test_sessions = [
        {
            "session_id":    "test_session_id_customer_ci",
            "user_id":       "test_user_customer_ci",
            "session_token": TEST_CUSTOMER_TOKEN,   # value from GitHub Secret
            "expires_at":    FAR_FUTURE,
            "created_at":    datetime.now(timezone.utc),
            "ip_address":    "127.0.0.1",
            "user_agent":    "pytest-ci",
        },
        {
            "session_id":    "test_session_id_admin_ci",
            "user_id":       "test_user_admin_ci",
            "session_token": TEST_ADMIN_TOKEN,       # value from GitHub Secret
            "expires_at":    FAR_FUTURE,
            "created_at":    datetime.now(timezone.utc),
            "ip_address":    "127.0.0.1",
            "user_agent":    "pytest-ci",
        },
    ]

    for user in test_users:
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": user},
            upsert=True,
        )
        print(f"  upserted user: {user['user_id']}")

    for session in test_sessions:
        await db.user_sessions.update_one(
            {"session_token": session["session_token"]},
            {"$set": session},
            upsert=True,
        )
        print(f"  upserted session for: {session['user_id']}")

    client.close()
    print("done.")


if __name__ == "__main__":
    asyncio.run(seed())
