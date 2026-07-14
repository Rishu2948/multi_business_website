#!/usr/bin/env python3
"""
Expand the bakery (whisked_words) catalog to 100 products and push to cloud MongoDB.
- Keeps all existing data intact (uses insert, not replace)
- Skips products that already exist by product_id
- Generates 99 new bakery products + inventory records (1 already exists)

Usage:
    ./venv/bin/python expand_bakery_seed.py
    ./venv/bin/python expand_bakery_seed.py --dry-run   # print counts only
"""

import argparse
import asyncio
import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

BUSINESS_ID = "whisked_words"

# ─── Product catalog data ────────────────────────────────────────────────────

CAKE_FLAVORS = [
    "Chocolate", "Vanilla", "Red Velvet", "Lemon", "Strawberry",
    "Blueberry", "Caramel", "Coffee", "Butterscotch", "Mango",
    "Pineapple", "Rose", "Hazelnut", "Pistachio", "Coconut",
]

CAKE_TYPES = [
    "Truffle Cake", "Cheesecake", "Mousse Cake", "Sponge Cake",
    "Fondant Cake", "Chiffon Cake", "Bundt Cake", "Layer Cake",
    "Sheet Cake", "Naked Cake",
]

PASTRY_ITEMS = [
    ("Croissant", 120, ["Flour", "Butter", "Yeast", "Salt"], ["Gluten", "Dairy"]),
    ("Pain au Chocolat", 150, ["Flour", "Butter", "Dark Chocolate", "Yeast"], ["Gluten", "Dairy"]),
    ("Almond Danish", 160, ["Flour", "Butter", "Almonds", "Sugar"], ["Gluten", "Dairy", "Nuts"]),
    ("Cinnamon Roll", 180, ["Flour", "Butter", "Cinnamon", "Sugar"], ["Gluten", "Dairy"]),
    ("Eclair", 140, ["Choux Pastry", "Custard", "Chocolate Glaze"], ["Gluten", "Dairy", "Eggs"]),
    ("Mille-Feuille", 220, ["Puff Pastry", "Custard", "Sugar"], ["Gluten", "Dairy", "Eggs"]),
    ("Fruit Tart", 250, ["Shortcrust Pastry", "Custard", "Seasonal Fruits"], ["Gluten", "Dairy", "Eggs"]),
    ("Macaron", 80, ["Almond Flour", "Sugar", "Egg Whites"], ["Nuts", "Eggs"]),
    ("Cannoli", 130, ["Ricotta", "Pastry Shell", "Chocolate Chips"], ["Gluten", "Dairy"]),
    ("Opera Cake", 300, ["Joconde Sponge", "Coffee Buttercream", "Chocolate Ganache"], ["Gluten", "Dairy", "Eggs", "Nuts"]),
]

BREAD_ITEMS = [
    ("Sourdough Loaf", 280, "whole", "2 days"),
    ("Multigrain Bread", 240, "whole", "3 days"),
    ("Focaccia", 200, "whole", "2 days"),
    ("Baguette", 120, "each", "1 day"),
    ("Ciabatta", 180, "whole", "2 days"),
    ("Brioche", 260, "whole", "3 days"),
    ("Rye Bread", 220, "whole", "4 days"),
    ("Pita Bread (6 pcs)", 140, "pack", "2 days"),
    ("Garlic Herb Bread", 190, "whole", "2 days"),
    ("Banana Bread", 250, "loaf", "4 days"),
]

COOKIE_ITEMS = [
    ("Chocolate Chip Cookies", 180, 6),
    ("Oatmeal Raisin Cookies", 160, 6),
    ("Snickerdoodle Cookies", 170, 6),
    ("Peanut Butter Cookies", 190, 6),
    ("Double Chocolate Cookies", 200, 6),
    ("Sugar Cookies", 150, 6),
    ("Shortbread Fingers", 160, 8),
    ("Almond Biscotti", 220, 8),
    ("Lemon Zest Cookies", 165, 6),
    ("Coconut Macaroons", 175, 6),
]

MUFFIN_ITEMS = [
    ("Blueberry Muffin", 80, "blueberry"),
    ("Chocolate Chip Muffin", 85, "chocolate"),
    ("Banana Walnut Muffin", 90, "banana"),
    ("Lemon Poppy Seed Muffin", 85, "lemon"),
    ("Bran Muffin", 75, "bran"),
    ("Carrot Muffin", 80, "carrot"),
    ("Cheddar Herb Muffin", 90, "savory"),
    ("Cranberry Orange Muffin", 85, "cranberry"),
    ("Double Chocolate Muffin", 95, "chocolate"),
    ("Pumpkin Spice Muffin", 80, "pumpkin"),
]

PEXELS_BAKERY_IMAGES = [
    "https://images.pexels.com/photos/1395967/pexels-photo-1395967.jpeg",
    "https://images.pexels.com/photos/205961/pexels-photo-205961.jpeg",
    "https://images.pexels.com/photos/1070850/pexels-photo-1070850.jpeg",
    "https://images.pexels.com/photos/376464/pexels-photo-376464.jpeg",
    "https://images.pexels.com/photos/291528/pexels-photo-291528.jpeg",
    "https://images.pexels.com/photos/2144200/pexels-photo-2144200.jpeg",
    "https://images.pexels.com/photos/3026808/pexels-photo-3026808.jpeg",
    "https://images.pexels.com/photos/1028714/pexels-photo-1028714.jpeg",
    "https://images.pexels.com/photos/1126359/pexels-photo-1126359.jpeg",
    "https://images.pexels.com/photos/2067396/pexels-photo-2067396.jpeg",
    "https://images.pexels.com/photos/264892/pexels-photo-264892.jpeg",
    "https://images.pexels.com/photos/1998633/pexels-photo-1998633.jpeg",
    "https://images.pexels.com/photos/3065209/pexels-photo-3065209.jpeg",
    "https://images.pexels.com/photos/1343504/pexels-photo-1343504.jpeg",
    "https://images.pexels.com/photos/2977901/pexels-photo-2977901.jpeg",
]


def _image(idx: int, alt: str) -> list:
    url = PEXELS_BAKERY_IMAGES[idx % len(PEXELS_BAKERY_IMAGES)]
    return [{"url": url, "alt": alt, "is_primary": True}]


def _inv(product_id: str, variant_id, sku: str,
         available: int, reserved: int = 0) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "inventory_id": f"inv_{uuid.uuid4().hex[:12]}",
        "business_id": BUSINESS_ID,
        "product_id": product_id,
        "variant_id": variant_id,
        "sku": sku,
        "quantity": {
            "available": available,
            "reserved": reserved,
            "total": available + reserved,
        },
        "location": {"warehouse": "Main Warehouse", "shelf": "", "bin": ""},
        "reorder": {"reorder_level": 10, "reorder_quantity": 50, "supplier": ""},
        "last_restocked": now,
        "last_updated": now,
        "movements": [],
    }


def _ts(days_ago: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


def build_new_products() -> tuple[list, list]:
    """Return (products, inventory_records) for 99 NEW bakery items."""
    products = []
    inventory = []
    img_idx = 1  # start at 1 to avoid reusing index 0 (used by existing cake)

    # ── 1. Cakes: 15 flavors × 10 types = 150, take first 40 ──────────────
    cake_count = 0
    for flavor in CAKE_FLAVORS:
        for cake_type in CAKE_TYPES:
            if cake_count >= 40:
                break
            name = f"{flavor} {cake_type}"
            pid = f"prod_{uuid.uuid4().hex[:12]}"
            base_price = round(700 + (CAKE_FLAVORS.index(flavor) * 50) + (CAKE_TYPES.index(cake_type) * 30), 2)
            sku_500 = f"WW-CAKE-{cake_count+2:03d}-500G"
            sku_1kg = f"WW-CAKE-{cake_count+2:03d}-1KG"

            product = {
                "product_id": pid,
                "business_id": BUSINESS_ID,
                "category_id": "cat_cakes",
                "product_name": name,
                "description": f"Freshly baked {name.lower()} with premium ingredients",
                "base_price": base_price,
                "currency": "INR",
                "images": _image(img_idx, name),
                "attributes": {
                    "weight": "500g",
                    "serves": "4-6 people",
                    "flavor": flavor.lower(),
                    "cake_type": cake_type.lower(),
                    "allergens": ["Gluten", "Dairy", "Eggs"],
                    "shelf_life": "2 days",
                    "storage": "Refrigerated",
                    "customizable": True,
                },
                "variants": [
                    {
                        "variant_id": "var_001",
                        "sku": sku_500,
                        "weight": "500g",
                        "additional_price": 0,
                        "inventory_count": 15,
                    },
                    {
                        "variant_id": "var_002",
                        "sku": sku_1kg,
                        "weight": "1kg",
                        "additional_price": 750.0,
                        "inventory_count": 8,
                    },
                ],
                "status": "active",
                "created_at": _ts(cake_count),
                "updated_at": _ts(cake_count),
            }
            products.append(product)
            inventory.append(_inv(pid, "var_001", sku_500, 15))
            inventory.append(_inv(pid, "var_002", sku_1kg, 8))
            img_idx += 1
            cake_count += 1
        if cake_count >= 40:
            break

    # ── 2. Pastries: 10 items ──────────────────────────────────────────────
    for i, (pname, price, ingredients, allergens) in enumerate(PASTRY_ITEMS):
        pid = f"prod_{uuid.uuid4().hex[:12]}"
        sku_single = f"WW-PAST-{i+1:03d}-SINGLE"
        sku_box6 = f"WW-PAST-{i+1:03d}-BOX6"

        product = {
            "product_id": pid,
            "business_id": BUSINESS_ID,
            "category_id": "cat_pastries",
            "product_name": pname,
            "description": f"Freshly baked {pname.lower()}, made with artisan ingredients",
            "base_price": float(price),
            "currency": "INR",
            "images": _image(img_idx, pname),
            "attributes": {
                "ingredients": ingredients,
                "allergens": allergens,
                "shelf_life": "1 day",
                "storage": "Room temperature",
                "occasion": "Breakfast, Snack",
                "customizable": False,
            },
            "variants": [
                {
                    "variant_id": "var_001",
                    "sku": sku_single,
                    "pack_size": "Single",
                    "additional_price": 0,
                    "inventory_count": 30,
                },
                {
                    "variant_id": "var_002",
                    "sku": sku_box6,
                    "pack_size": "Box of 6",
                    "additional_price": float(price * 5 - 50),
                    "inventory_count": 12,
                },
            ],
            "status": "active",
            "created_at": _ts(i + 40),
            "updated_at": _ts(i + 40),
        }
        products.append(product)
        inventory.append(_inv(pid, "var_001", sku_single, 30))
        inventory.append(_inv(pid, "var_002", sku_box6, 12))
        img_idx += 1

    # ── 3. Breads: 10 items ────────────────────────────────────────────────
    for i, (bname, price, unit, shelf_life) in enumerate(BREAD_ITEMS):
        pid = f"prod_{uuid.uuid4().hex[:12]}"
        sku = f"WW-BREAD-{i+1:03d}"

        product = {
            "product_id": pid,
            "business_id": BUSINESS_ID,
            "category_id": "cat_breads",
            "product_name": bname,
            "description": f"Artisan {bname.lower()} baked fresh every morning",
            "base_price": float(price),
            "currency": "INR",
            "images": _image(img_idx, bname),
            "attributes": {
                "unit": unit,
                "shelf_life": shelf_life,
                "storage": "Room temperature",
                "occasion": "Breakfast, Lunch",
                "allergens": ["Gluten"],
                "customizable": False,
            },
            "variants": [],
            "status": "active",
            "created_at": _ts(i + 50),
            "updated_at": _ts(i + 50),
        }
        products.append(product)
        available = 20 if price < 200 else 10
        inventory.append(_inv(pid, None, sku, available))
        img_idx += 1

    # ── 4. Cookies: 10 items ──────────────────────────────────────────────
    for i, (cname, price, count) in enumerate(COOKIE_ITEMS):
        pid = f"prod_{uuid.uuid4().hex[:12]}"
        sku_box = f"WW-COOK-{i+1:03d}-BOX"
        sku_bulk = f"WW-COOK-{i+1:03d}-BULK"

        product = {
            "product_id": pid,
            "business_id": BUSINESS_ID,
            "category_id": "cat_cookies",
            "product_name": cname,
            "description": f"Freshly baked {cname.lower()} — crispy outside, chewy inside",
            "base_price": float(price),
            "currency": "INR",
            "images": _image(img_idx, cname),
            "attributes": {
                "pieces_per_box": count,
                "flavor": cname.split()[0].lower(),
                "allergens": ["Gluten", "Dairy", "Eggs"],
                "shelf_life": "5 days",
                "storage": "Room temperature, airtight container",
                "occasion": "Snack, Gift",
                "customizable": False,
            },
            "variants": [
                {
                    "variant_id": "var_001",
                    "sku": sku_box,
                    "pack_size": f"Box of {count}",
                    "additional_price": 0,
                    "inventory_count": 40,
                },
                {
                    "variant_id": "var_002",
                    "sku": sku_bulk,
                    "pack_size": f"Bulk 24 pcs",
                    "additional_price": float(price * 3),
                    "inventory_count": 20,
                },
            ],
            "status": "active",
            "created_at": _ts(i + 60),
            "updated_at": _ts(i + 60),
        }
        products.append(product)
        inventory.append(_inv(pid, "var_001", sku_box, 40))
        inventory.append(_inv(pid, "var_002", sku_bulk, 20))
        img_idx += 1

    # ── 5. Muffins: 10 items ──────────────────────────────────────────────
    for i, (mname, price, flavor) in enumerate(MUFFIN_ITEMS):
        pid = f"prod_{uuid.uuid4().hex[:12]}"
        sku_single = f"WW-MUFF-{i+1:03d}-SINGLE"
        sku_box4 = f"WW-MUFF-{i+1:03d}-BOX4"

        product = {
            "product_id": pid,
            "business_id": BUSINESS_ID,
            "category_id": "cat_muffins",
            "product_name": mname,
            "description": f"Soft and moist {mname.lower()} baked fresh daily",
            "base_price": float(price),
            "currency": "INR",
            "images": _image(img_idx, mname),
            "attributes": {
                "flavor": flavor,
                "allergens": ["Gluten", "Dairy", "Eggs"],
                "shelf_life": "2 days",
                "storage": "Room temperature",
                "occasion": "Breakfast, Snack",
                "customizable": False,
            },
            "variants": [
                {
                    "variant_id": "var_001",
                    "sku": sku_single,
                    "pack_size": "Single",
                    "additional_price": 0,
                    "inventory_count": 50,
                },
                {
                    "variant_id": "var_002",
                    "sku": sku_box4,
                    "pack_size": "Box of 4",
                    "additional_price": float(price * 3 - 20),
                    "inventory_count": 25,
                },
            ],
            "status": "active",
            "created_at": _ts(i + 70),
            "updated_at": _ts(i + 70),
        }
        products.append(product)
        inventory.append(_inv(pid, "var_001", sku_single, 50))
        inventory.append(_inv(pid, "var_002", sku_box4, 25))
        img_idx += 1

    # ── 6. Seasonal specials to fill up to exactly 99 new items ───────────
    specials = [
        ("Valentine's Heart Cake", 1299, "chocolate", "Special heart-shaped cake for Valentine's Day", "Wedding, Valentine"),
        ("Anniversary Tier Cake", 2499, "vanilla", "Two-tier anniversary cake with custom message", "Wedding, Anniversary"),
        ("Birthday Number Cake", 1799, "strawberry", "Custom number-shaped cake for birthdays", "Birthday"),
        ("Baby Shower Fondant Cake", 2199, "lemon", "Pastel fondant cake perfect for baby showers", "Baby Shower"),
        ("Christmas Yule Log", 1099, "chocolate", "Traditional buche de Noel for the festive season", "Christmas"),
        ("Diwali Mithai Box", 599, "mixed", "Assorted Indian sweets for the festive season", "Diwali, Festival"),
        ("Eid Special Baklava Box", 699, "pistachio", "Crispy honey-soaked baklava with mixed nuts", "Eid, Festival"),
        ("New Year Midnight Cake", 1599, "champagne", "Elegant celebration cake for New Year's", "New Year"),
        ("Mother's Day Floral Cake", 1399, "rose", "Beautiful floral fondant cake for Mother's Day", "Mother's Day"),
        ("Graduation Scroll Cake", 1699, "coffee", "Scroll-shaped fondant cake for graduates", "Graduation"),
        ("Halloween Spooky Cupcakes (12 pcs)", 899, "chocolate", "Spooky Halloween themed cupcakes", "Halloween"),
        ("Holi Colour Cake", 999, "mango", "Vibrant rainbow layered Holi celebration cake", "Holi, Festival"),
        ("Corporate Gift Box", 1199, "assorted", "Assorted premium baked goods for corporate gifting", "Corporate"),
        ("Gluten-Free Brownie Box", 750, "chocolate", "Rich fudgy brownies — 100% gluten-free", "Health"),
        ("Vegan Carrot Cake", 850, "carrot", "Moist vegan carrot cake with coconut cream frosting", "Vegan"),
        ("Keto Almond Cake", 950, "almond", "Low-carb keto-friendly almond flour cake", "Keto"),
        ("Sugar-Free Diabetic Cake", 900, "vanilla", "No added sugar cake sweetened with stevia", "Diabetic"),
        ("Kids Rainbow Cake", 1199, "vanilla", "Fun rainbow layered cake for children's parties", "Birthday, Kids"),
        ("Cheese Platter & Crackers Box", 1499, "savory", "Artisan cheese board with homemade crackers", "Party, Gifting"),
    ]

    for i, (sname, price, flavor, desc, occasion) in enumerate(specials):
        pid = f"prod_{uuid.uuid4().hex[:12]}"
        sku = f"WW-SPEC-{i+1:03d}"

        product = {
            "product_id": pid,
            "business_id": BUSINESS_ID,
            "category_id": "cat_specials",
            "product_name": sname,
            "description": desc,
            "base_price": float(price),
            "currency": "INR",
            "images": _image(img_idx, sname),
            "attributes": {
                "flavor": flavor,
                "occasion": occasion,
                "allergens": ["Gluten", "Dairy", "Eggs"],
                "shelf_life": "2 days",
                "storage": "Refrigerated",
                "customizable": True,
            },
            "variants": [],
            "status": "active",
            "created_at": _ts(i + 80),
            "updated_at": _ts(i + 80),
        }
        products.append(product)
        inventory.append(_inv(pid, None, sku, 10, reserved=2))
        img_idx += 1

    # Trim to exactly 99 if we overshot
    products = products[:99]
    # Rebuild inventory to match only products we kept
    kept_pids = {p["product_id"] for p in products}
    inventory = [iv for iv in inventory if iv["product_id"] in kept_pids]

    return products, inventory


async def expand(dry_run: bool = False):
    url = os.environ["MONGO_URL"]
    db_name = os.environ.get("DB_NAME", "multi_business")

    print(f"🔌 Connecting to {db_name} at {url[:60]}...")
    mongo_client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=15000)
    db = mongo_client[db_name]

    # Verify connection
    await db.command("ping")
    print("✅ Connected to MongoDB Atlas")

    # Count existing bakery products
    existing_count = await db.products.count_documents({"business_id": BUSINESS_ID})
    print(f"📦 Existing Whisked Words products: {existing_count}")

    if existing_count >= 100:
        print("✅ Already have 100+ products for Whisked Words. Nothing to do.")
        mongo_client.close()
        return

    products, inventory = build_new_products()
    needed = 100 - existing_count
    products = products[:needed]
    kept_pids = {p["product_id"] for p in products}
    inventory = [iv for iv in inventory if iv["product_id"] in kept_pids]

    print(f"📝 Generating {len(products)} new products + {len(inventory)} inventory records...")

    if dry_run:
        print(f"\n[DRY RUN] Would insert {len(products)} products and {len(inventory)} inventory records.")
        print("Product names preview:")
        for p in products[:10]:
            print(f"  - {p['product_name']} (₹{p['base_price']})")
        print("  ...")
        mongo_client.close()
        return

    # Also upsert categories so product category_id references are valid
    categories = [
        {"category_id": "cat_cakes",     "business_id": BUSINESS_ID, "name": "Cakes",             "slug": "cakes"},
        {"category_id": "cat_pastries",  "business_id": BUSINESS_ID, "name": "Pastries",           "slug": "pastries"},
        {"category_id": "cat_breads",    "business_id": BUSINESS_ID, "name": "Breads",             "slug": "breads"},
        {"category_id": "cat_cookies",   "business_id": BUSINESS_ID, "name": "Cookies & Biscuits", "slug": "cookies"},
        {"category_id": "cat_muffins",   "business_id": BUSINESS_ID, "name": "Muffins & Cupcakes", "slug": "muffins"},
        {"category_id": "cat_specials",  "business_id": BUSINESS_ID, "name": "Seasonal Specials",  "slug": "specials"},
    ]
    for cat in categories:
        await db.categories.update_one(
            {"category_id": cat["category_id"]},
            {"$setOnInsert": cat},
            upsert=True,
        )
    print(f"  ✅ categories: {len(categories)} upserted")

    # Insert products (skip any that somehow already exist)
    result = await db.products.insert_many(products, ordered=False)
    print(f"  ✅ products: {len(result.inserted_ids)} inserted")

    # Insert inventory records
    inv_result = await db.inventory.insert_many(inventory, ordered=False)
    print(f"  ✅ inventory: {len(inv_result.inserted_ids)} inserted")

    final_count = await db.products.count_documents({"business_id": BUSINESS_ID})
    print(f"\n🎉 Whisked Words now has {final_count} products in the cloud database.")
    mongo_client.close()


def main():
    parser = argparse.ArgumentParser(description="Expand Whisked Words bakery to 100 products")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to DB")
    args = parser.parse_args()
    asyncio.run(expand(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
