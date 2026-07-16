#!/usr/bin/env python3
"""
seed_test_sessions.py
---------------------
Inserts stable test session tokens and the corresponding user documents
into MongoDB so the CI integration tests can authenticate.

Tokens are hardcoded in all test files:
    CUSTOMER_TOKEN = "test_session_customer_001"
    ADMIN_TOKEN    = "test_session_admin_001"

Run once against any environment:
    python seed_test_sessions.py

Or from CI (MONGO_URL + DB_NAME come from environment / GitHub Secrets).
"""

import asyncio
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME   = os.environ["DB_NAME"]

FAR_FUTURE = datetime.now(timezone.utc) + timedelta(days=3650)   # ~10 years

TEST_USERS = [
    {
        "user_id":         "test_user_customer_001",
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
        "user_id":         "test_user_admin_001",
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

TEST_SESSIONS = [
    {
        "session_id":    "test_session_id_customer_001",
        "user_id":       "test_user_customer_001",
        "session_token": "test_session_customer_001",
        "expires_at":    FAR_FUTURE,
        "created_at":    datetime.now(timezone.utc),
        "ip_address":    "127.0.0.1",
        "user_agent":    "pytest-ci",
    },
    {
        "session_id":    "test_session_id_admin_001",
        "user_id":       "test_user_admin_001",
        "session_token": "test_session_admin_001",
        "expires_at":    FAR_FUTURE,
        "created_at":    datetime.now(timezone.utc),
        "ip_address":    "127.0.0.1",
        "user_agent":    "pytest-ci",
    },
]


async def seed():
    client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=10000)
    db     = client[DB_NAME]

    for user in TEST_USERS:
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": user},
            upsert=True,
        )
        print(f"  upserted user: {user['user_id']}")

    for session in TEST_SESSIONS:
        await db.user_sessions.update_one(
            {"session_token": session["session_token"]},
            {"$set": session},
            upsert=True,
        )
        print(f"  upserted session: {session['session_token']}")

    client.close()
    print("done.")


if __name__ == "__main__":
    asyncio.run(seed())
