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

async def update_businesses():
    print("🔄 Updating businesses with parent company info...")
    
    # Update each business to add parent company and domain info
    updates = [
        {
            "business_id": "rishabh_garments",
            "update": {
                "$set": {
                    "parent_company": "Jain Industries",
                    "independent_domain": "rishabhgarments.com",
                    "theme_color": "#0A0A0A",
                    "is_independent_site": True
                }
            }
        },
        {
            "business_id": "jain_jewellers",
            "update": {
                "$set": {
                    "parent_company": "Jain Industries",
                    "independent_domain": "jainjewellers.com",
                    "theme_color": "#8B7355",
                    "is_independent_site": True
                }
            }
        },
        {
            "business_id": "jain_sarees",
            "update": {
                "$set": {
                    "parent_company": "Jain Industries",
                    "independent_domain": "jainsarees.com",
                    "theme_color": "#C41E3A",
                    "is_independent_site": True
                }
            }
        },
        {
            "business_id": "whisked_words",
            "update": {
                "$set": {
                    "parent_company": "Jain Industries",
                    "independent_domain": "whiskedwords.com",
                    "theme_color": "#D4A574",
                    "is_independent_site": True
                }
            }
        }
    ]
    
    for update_data in updates:
        result = await db.businesses.update_one(
            {"business_id": update_data["business_id"]},
            update_data["update"]
        )
        print(f"✅ Updated {update_data['business_id']}")
    
    print("✨ All businesses updated with parent company info!")

if __name__ == "__main__":
    asyncio.run(update_businesses())
    client.close()
