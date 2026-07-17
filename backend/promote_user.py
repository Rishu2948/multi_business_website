#!/usr/bin/env python3
"""
promote_user.py — Promote a user to super_admin or business_admin.

Usage:
    cd backend
    python3 promote_user.py --email your@email.com --role super_admin
    python3 promote_user.py --email your@email.com --role business_admin --business whisked_words
"""

import argparse
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent / ".env")


async def promote(email: str, role: str, business_id: str = None):
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        print(f"❌ User not found: {email}")
        print("   Make sure the user has logged in at least once.")
        client.close()
        return

    print(f"  Found user: {user['name']} ({user['email']}) — current role: {user['role']}")

    updates = {"role": role}

    # For business_admin, also add business_access entry
    if role == "business_admin" and business_id:
        from datetime import datetime, timezone
        business_access = user.get("business_access", [])
        # Remove existing entry for this business
        business_access = [a for a in business_access if a.get("business_id") != business_id]
        business_access.append({
            "business_id": business_id,
            "role": "business_admin",
            "assigned_at": datetime.now(timezone.utc)
        })
        updates["business_access"] = business_access

    result = await db.users.update_one({"email": email}, {"$set": updates})

    if result.modified_count:
        print(f"  ✅ {email} promoted to {role}")
        if business_id:
            print(f"     Business access granted: {business_id}")
    else:
        print(f"  ℹ️  No changes made (user may already have this role)")

    client.close()


def main():
    parser = argparse.ArgumentParser(description="Promote a user to admin role")
    parser.add_argument("--email", required=True, help="User email address")
    parser.add_argument("--role", default="super_admin",
                        choices=["super_admin", "business_admin", "staff", "delivery_agent", "customer"],
                        help="Role to assign (default: super_admin)")
    parser.add_argument("--business", default=None,
                        help="Business ID for business_admin role (e.g. whisked_words)")
    args = parser.parse_args()

    print(f"\n🔑 Promoting user: {args.email} → {args.role}")
    asyncio.run(promote(args.email, args.role, args.business))
    print()


if __name__ == "__main__":
    main()
