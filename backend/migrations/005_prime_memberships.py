"""
Migration 005: Prime Memberships and Business Config

Creates:
- NEW business_config collection for business-wide Prime settings
- prime_memberships collection for subscription tracking
- Migrates existing is_prime users to Prime memberships for whisked_words
"""

import asyncio
from datetime import datetime, timezone, timedelta


async def up(db):
    """Apply migration."""
    print("Starting migration 005: Prime Memberships and Business Config")
    
    # Create business_config collection with indexes
    print("Creating business_config collection...")
    await db.business_config.create_index([("business_id", 1)], unique=True)
    await db.business_config.create_index([("prime.enabled", 1)])
    
    # Seed default business_config for whisked_words
    DEFAULT_PRIME_CONFIG = {
        "business_id": "whisked_words",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "prime": {
            "enabled": True,
            "display_name": "Whisked Words Prime",
            "tagline": "Get unlimited access to our AI shopping assistant",
            "plans": [
                {
                    "plan_id": "prime_monthly",
                    "name": "Prime Monthly",
                    "billing_cycle": "monthly",
                    "price": 149.0,
                    "currency": "INR",
                    "is_active": True,
                    "marketing_features": ["AI Catalog Assistant"],
                    "gateway_product_id": None,
                },
                {
                    "plan_id": "prime_annual",
                    "name": "Prime Annual",
                    "billing_cycle": "annual",
                    "price": 1499.0,
                    "currency": "INR",
                    "is_active": True,
                    "marketing_features": ["AI Catalog Assistant", "Best value — save ₹289"],
                    "gateway_product_id": None,
                },
            ],
            "features": {
                "ai_chatbot": {"enabled": True, "label": "AI Catalog Assistant"},
                "priority_support": {"enabled": False, "label": "Priority Customer Support"},
                "free_delivery": {"enabled": False, "label": "Free Delivery on All Orders"},
                "early_access": {"enabled": False, "label": "Early Access to New Products"},
            },
        },
    }
    
    await db.business_config.update_one(
        {"business_id": "whisked_words"},
        {"$setOnInsert": DEFAULT_PRIME_CONFIG},
        upsert=True,
    )
    print("Seeded default business_config for whisked_words")
    
    # Create prime_memberships collection with indexes
    print("Creating prime_memberships collection...")
    await db.prime_memberships.create_index([("membership_id", 1)], unique=True)
    await db.prime_memberships.create_index([("user_id", 1), ("business_id", 1)], unique=True)
    await db.prime_memberships.create_index([("status", 1), ("expires_at", 1)])
    await db.prime_memberships.create_index([("status", 1), ("auto_renew", 1), ("expires_at", 1)])
    await db.prime_memberships.create_index([("business_id", 1), ("status", 1)])
    
    # Migrate existing is_prime users to Prime memberships
    print("Migrating existing is_prime users...")
    prime_users = await db.users.find({"is_prime": True}).to_list(length=None)
    
    migrated_count = 0
    for user in prime_users:
        user_id = user.get("user_id")
        if not user_id:
            continue
        
        # Check if user already has a membership
        existing = await db.prime_memberships.find_one({
            "user_id": user_id,
            "business_id": "whisked_words",
        })
        
        if existing:
            print(f"  User {user_id} already has membership, skipping")
            continue
        
        # Create membership with 30-day expiry
        membership_id = f"pm_{user_id[:8]}_migrated"
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=30)
        
        membership = {
            "membership_id": membership_id,
            "user_id": user_id,
            "business_id": "whisked_words",
            "plan_id": "prime_monthly",
            "status": "active",
            "started_at": now,
            "expires_at": expires_at,
            "cancelled_at": None,
            "auto_renew": True,
            "granted_by_admin": True,
            "payment_history": [],
            "notifications_sent": [],
            "created_at": now,
            "updated_at": now,
        }
        
        await db.prime_memberships.insert_one(membership)
        migrated_count += 1
        print(f"  Migrated user {user_id} to Prime membership")
    
    print(f"Migration complete: {migrated_count} users migrated")


async def down(db):
    """Rollback migration."""
    print("Rolling back migration 005...")
    
    # Drop collections
    await db.business_config.drop()
    await db.prime_memberships.drop()
    
    print("Rollback complete")


if __name__ == "__main__":
    import sys
    import os
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
    
    # Connect to MongoDB directly
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.environ.get('DB_NAME', 'multi_business_db')
    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
    db = client[db_name]
    
    async def main():
        if len(sys.argv) > 1 and sys.argv[1] == "down":
            await down(db)
        else:
            await up(db)
        
        # Close connection
        client.close()
    
    asyncio.run(main())
