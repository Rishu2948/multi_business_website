import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timezone
import uuid

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

async def seed_data():
    print("🌱 Starting database seeding...")
    
    # Check if businesses already exist
    existing_businesses = await db.businesses.count_documents({})
    if existing_businesses > 0:
        print("✅ Businesses already seeded. Skipping...")
        return
    
    # Create 4 businesses
    businesses = [
        {
            "business_id": "rishabh_garments",
            "business_name": "Rishabh Garments",
            "business_type": "kids_wear",
            "description": "Premium kids wear collection for all ages",
            "logo_url": "https://images.pexels.com/photos/5560013/pexels-photo-5560013.jpeg",
            "contact": {
                "email": "contact@rishabhgarments.com",
                "phone": "+91-9876543210",
                "address": {
                    "street": "123 Fashion Street",
                    "city": "Mumbai",
                    "state": "Maharashtra",
                    "pincode": "400001",
                    "country": "India"
                }
            },
            "settings": {
                "currency": "INR",
                "timezone": "Asia/Kolkata",
                "inventory_alerts": {
                    "low_stock_threshold": 10,
                    "enable_email_alerts": True
                }
            },
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        },
        {
            "business_id": "jain_jewellers",
            "business_name": "Jain Jewellers",
            "business_type": "jewellery",
            "description": "Exquisite gold and diamond jewellery",
            "logo_url": "https://images.pexels.com/photos/3641056/pexels-photo-3641056.jpeg",
            "contact": {
                "email": "contact@jainjewellers.com",
                "phone": "+91-9876543211",
                "address": {
                    "street": "456 Jewel Plaza",
                    "city": "Jaipur",
                    "state": "Rajasthan",
                    "pincode": "302001",
                    "country": "India"
                }
            },
            "settings": {
                "currency": "INR",
                "timezone": "Asia/Kolkata",
                "inventory_alerts": {
                    "low_stock_threshold": 5,
                    "enable_email_alerts": True
                }
            },
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        },
        {
            "business_id": "jain_sarees",
            "business_name": "Jain Sarees",
            "business_type": "saree",
            "description": "Traditional and designer sarees",
            "logo_url": "https://images.pexels.com/photos/36194190/pexels-photo-36194190.jpeg",
            "contact": {
                "email": "contact@jainsarees.com",
                "phone": "+91-9876543212",
                "address": {
                    "street": "789 Silk Road",
                    "city": "Surat",
                    "state": "Gujarat",
                    "pincode": "395001",
                    "country": "India"
                }
            },
            "settings": {
                "currency": "INR",
                "timezone": "Asia/Kolkata",
                "inventory_alerts": {
                    "low_stock_threshold": 8,
                    "enable_email_alerts": True
                }
            },
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        },
        {
            "business_id": "whisked_words",
            "business_name": "Whisked Words",
            "business_type": "bakery",
            "description": "Artisan bakery with fresh pastries and custom cakes",
            "logo_url": "https://images.pexels.com/photos/192933/pexels-photo-192933.jpeg",
            "contact": {
                "email": "contact@whiskedwords.com",
                "phone": "+91-9876543213",
                "address": {
                    "street": "321 Baker's Lane",
                    "city": "Bangalore",
                    "state": "Karnataka",
                    "pincode": "560001",
                    "country": "India"
                }
            },
            "settings": {
                "currency": "INR",
                "timezone": "Asia/Kolkata",
                "inventory_alerts": {
                    "low_stock_threshold": 15,
                    "enable_email_alerts": True
                }
            },
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
    ]
    
    await db.businesses.insert_many(businesses)
    print(f"✅ Created {len(businesses)} businesses")
    
    # Create a super admin user
    super_admin = {
        "user_id": f"user_{uuid.uuid4().hex[:12]}",
        "email": "superadmin@multibiz.com",
        "name": "Super Admin",
        "picture": "",
        "role": "super_admin",
        "business_access": [],
        "status": "active",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "last_login": datetime.now(timezone.utc)
    }
    
    # Check if super admin already exists
    existing_admin = await db.users.find_one({"email": "superadmin@multibiz.com"})
    if not existing_admin:
        await db.users.insert_one(super_admin)
        print(f"✅ Created super admin user: {super_admin['email']}")
    
    # Create sample products for each business
    print("🌱 Creating sample products...")
    
    # Rishabh Garments products
    rg_products = [
        {
            "product_id": f"prod_{uuid.uuid4().hex[:12]}",
            "business_id": "rishabh_garments",
            "category_id": None,
            "product_name": "Boys Cotton T-Shirt",
            "description": "100% cotton, comfortable fit for active kids",
            "base_price": 499.00,
            "currency": "INR",
            "images": [{"url": "https://images.pexels.com/photos/5560013/pexels-photo-5560013.jpeg", "alt": "Kids wear", "is_primary": True}],
            "attributes": {
                "age_group": "5-7 years",
                "sizes": ["S", "M", "L"],
                "colors": ["Red", "Blue", "Green"],
                "material": "100% Cotton",
                "brand": "RG Kids"
            },
            "variants": [
                {"variant_id": "var_001", "sku": "RG-TS-001-RED-M", "size": "M", "color": "Red", "additional_price": 0, "inventory_count": 50},
                {"variant_id": "var_002", "sku": "RG-TS-001-BLUE-M", "size": "M", "color": "Blue", "additional_price": 0, "inventory_count": 30}
            ],
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        },
        {
            "product_id": f"prod_{uuid.uuid4().hex[:12]}",
            "business_id": "rishabh_garments",
            "category_id": None,
            "product_name": "Girls Party Dress",
            "description": "Beautiful party wear dress for special occasions",
            "base_price": 1299.00,
            "currency": "INR",
            "images": [{"url": "https://images.pexels.com/photos/5560013/pexels-photo-5560013.jpeg", "alt": "Girls dress", "is_primary": True}],
            "attributes": {
                "age_group": "3-5 years",
                "sizes": ["S", "M", "L"],
                "colors": ["Pink", "Purple"],
                "material": "Cotton Blend",
                "brand": "RG Kids"
            },
            "variants": [
                {"variant_id": "var_001", "sku": "RG-DR-002-PINK-M", "size": "M", "color": "Pink", "additional_price": 0, "inventory_count": 25}
            ],
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
    ]
    
    # Jain Jewellers products
    jj_products = [
        {
            "product_id": f"prod_{uuid.uuid4().hex[:12]}",
            "business_id": "jain_jewellers",
            "category_id": None,
            "product_name": "Gold Necklace",
            "description": "22K gold necklace with intricate traditional design",
            "base_price": 85000.00,
            "currency": "INR",
            "images": [{"url": "https://images.pexels.com/photos/3641056/pexels-photo-3641056.jpeg", "alt": "Gold necklace", "is_primary": True}],
            "attributes": {
                "metal_type": "Gold",
                "purity": "22K",
                "weight": "25.5g",
                "stone_type": "Ruby",
                "making_charges": 5000.00,
                "hallmark": True
            },
            "variants": [],
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
    ]
    
    # Jain Sarees products
    js_products = [
        {
            "product_id": f"prod_{uuid.uuid4().hex[:12]}",
            "business_id": "jain_sarees",
            "category_id": None,
            "product_name": "Banarasi Silk Saree",
            "description": "Authentic Banarasi silk saree with golden zari work",
            "base_price": 5999.00,
            "currency": "INR",
            "images": [{"url": "https://images.pexels.com/photos/36194190/pexels-photo-36194190.jpeg", "alt": "Banarasi saree", "is_primary": True}],
            "attributes": {
                "fabric": "Pure Silk",
                "design": "Traditional Zari",
                "length": "6.5 meters",
                "color": "Red",
                "occasion": "Wedding, Festival"
            },
            "variants": [],
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
    ]
    
    # Whisked Words products
    ww_products = [
        {
            "product_id": f"prod_{uuid.uuid4().hex[:12]}",
            "business_id": "whisked_words",
            "category_id": None,
            "product_name": "Chocolate Truffle Cake",
            "description": "Rich chocolate cake with truffle filling",
            "base_price": 850.00,
            "currency": "INR",
            "images": [{"url": "https://images.pexels.com/photos/192933/pexels-photo-192933.jpeg", "alt": "Chocolate cake", "is_primary": True}],
            "attributes": {
                "weight": "500g",
                "serves": "4-6 people",
                "ingredients": ["Flour", "Cocoa", "Sugar", "Butter", "Eggs"],
                "allergens": ["Gluten", "Dairy", "Eggs"],
                "shelf_life": "2 days",
                "storage": "Refrigerated",
                "customizable": True
            },
            "variants": [
                {"variant_id": "var_001", "sku": "WW-CAKE-001-500G", "weight": "500g", "additional_price": 0, "inventory_count": 10},
                {"variant_id": "var_002", "sku": "WW-CAKE-001-1KG", "weight": "1kg", "additional_price": 750.00, "inventory_count": 5}
            ],
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
    ]
    
    all_products = rg_products + jj_products + js_products + ww_products
    await db.products.insert_many(all_products)
    print(f"✅ Created {len(all_products)} sample products")
    
    # Create inventory records
    print("🌱 Creating inventory records...")
    inventory_count = 0
    for product in all_products:
        if product["variants"]:
            for variant in product["variants"]:
                inventory_data = {
                    "inventory_id": f"inv_{uuid.uuid4().hex[:12]}",
                    "business_id": product["business_id"],
                    "product_id": product["product_id"],
                    "variant_id": variant["variant_id"],
                    "sku": variant.get("sku", ""),
                    "quantity": {
                        "available": variant.get("inventory_count", 0),
                        "reserved": 0,
                        "total": variant.get("inventory_count", 0)
                    },
                    "location": {
                        "warehouse": "Main Warehouse",
                        "shelf": "",
                        "bin": ""
                    },
                    "reorder": {
                        "reorder_level": 10,
                        "reorder_quantity": 50,
                        "supplier": ""
                    },
                    "last_restocked": datetime.now(timezone.utc),
                    "last_updated": datetime.now(timezone.utc),
                    "movements": []
                }
                await db.inventory.insert_one(inventory_data)
                inventory_count += 1
        else:
            # No variants
            inventory_data = {
                "inventory_id": f"inv_{uuid.uuid4().hex[:12]}",
                "business_id": product["business_id"],
                "product_id": product["product_id"],
                "variant_id": None,
                "sku": "",
                "quantity": {
                    "available": 1,
                    "reserved": 0,
                    "total": 1
                },
                "location": {
                    "warehouse": "Main Warehouse",
                    "shelf": "",
                    "bin": ""
                },
                "reorder": {
                    "reorder_level": 1,
                    "reorder_quantity": 5,
                    "supplier": ""
                },
                "last_restocked": datetime.now(timezone.utc),
                "last_updated": datetime.now(timezone.utc),
                "movements": []
            }
            await db.inventory.insert_one(inventory_data)
            inventory_count += 1
    
    print(f"✅ Created {inventory_count} inventory records")
    
    print("✨ Database seeding completed successfully!")
    print("\n📝 Test Credentials:")
    print(f"   Super Admin: {super_admin['email']}")
    print(f"   (Login via Google OAuth)")

if __name__ == "__main__":
    asyncio.run(seed_data())
    client.close()
