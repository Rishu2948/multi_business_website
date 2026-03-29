import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

async def update_user_roles():
    print("🔄 Updating user roles...")
    
    # Update rishabhjain2948@gmail.com to business_admin for Whisked Words
    user1 = await db.users.find_one({"email": "rishabhjain2948@gmail.com"}, {"_id": 0})
    
    if user1:
        await db.users.update_one(
            {"email": "rishabhjain2948@gmail.com"},
            {
                "$set": {
                    "role": "business_admin",
                    "business_access": [
                        {
                            "business_id": "whisked_words",
                            "role": "business_admin",
                            "assigned_at": datetime.now(timezone.utc)
                        }
                    ],
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        print(f"✅ Updated rishabhjain2948@gmail.com to business_admin for Whisked Words")
    else:
        print("ℹ️  User rishabhjain2948@gmail.com not found. They need to login first via Google OAuth.")
    
    # Update rishu.jain2948@gmail.com to customer
    user2 = await db.users.find_one({"email": "rishu.jain2948@gmail.com"}, {"_id": 0})
    
    if user2:
        await db.users.update_one(
            {"email": "rishu.jain2948@gmail.com"},
            {
                "$set": {
                    "role": "customer",
                    "business_access": [],
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        print(f"✅ Updated rishu.jain2948@gmail.com to customer")
    else:
        print("ℹ️  User rishu.jain2948@gmail.com not found. They need to login first via Google OAuth.")
    
    print("\n📋 Current user roles:")
    all_users = await db.users.find({}, {"_id": 0, "email": 1, "name": 1, "role": 1, "business_access": 1}).to_list(100)
    for user in all_users:
        business_info = ""
        if user.get("business_access"):
            businesses = [ba["business_id"] for ba in user["business_access"]]
            business_info = f" (Access: {', '.join(businesses)})"
        print(f"  - {user['email']}: {user['role']}{business_info}")
    
    print("\n✨ Role updates completed!")

if __name__ == "__main__":
    asyncio.run(update_user_roles())
    client.close()
