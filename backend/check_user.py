import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.multi_business
    user = await db.users.find_one({"email": "rishabhjain2948@gmail.com"})
    print("User info:", user)

asyncio.run(main())
