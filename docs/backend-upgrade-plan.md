# Backend Upgrade Plan — Config-Controlled, Scalable Architecture

**Stack:** FastAPI, MongoDB, Python  
**Core Principle:** Every aspect of a business — categories, products, inventory, offers, store config, collections, announcements — is **data-driven and editable via admin UI** with zero code changes.  
**Who controls what:**
- `super_admin` → controls all businesses, can create/edit any business's config
- `business_admin` → controls their own business config (categories, products, offers, store hours, etc.)
- No hardcoded maps, no enum lists in source code for business content

---

## Architecture: The Config-First Data Model

### Single Source of Truth Per Business

Every configurable aspect lives in MongoDB, not in Python code:

```
businesses/          ← business profiles (existing)
categories/          ← NEW: fully managed category tree per business
collections/         ← NEW: product groupings (gifting, festive, etc.)
products/            ← extended with category_id ref, addons, is_veg, tags
inventory/           ← existing + reorder alerts
store_config/        ← NEW: hours, order types, delivery settings
offers/              ← NEW: promo codes and auto-applied discounts
announcements/       ← NEW: announcement bar messages
```

The frontend **never reads a hardcoded list** — it always fetches from the API. Adding a new category like "Namkeen" is a one-click operation in the admin dashboard.

---

## Upgrade 1 — Category Management System

### Why This Matters

The current code has `format_category_name()` — a hardcoded Python dict mapping `category_id` strings to display names. Adding "Namkeen" would require a code change + redeploy. **This must be eliminated completely.**

### 1A. Categories Collection Schema

```python
class Category(BaseModel):
    category_id: str                    # Auto-generated slug: "namkeen"
    business_id: str                    # Scoped per business
    display_name: str                   # "Namkeen" — set by admin
    description: Optional[str] = None  # Optional subtitle
    image_url: Optional[str] = None     # Category hero image
    icon_emoji: Optional[str] = None    # "🥨" — shown in sidebar
    parent_category_id: Optional[str] = None  # For sub-categories
    sort_order: int = 0                 # Controls sidebar ordering
    is_active: bool = True
    is_featured: bool = False           # Show in homepage category tiles
    product_count: int = 0              # Cached, updated by background task
    created_by: str                     # user_id of creator
    created_at: datetime
    updated_at: datetime
```

### 1B. Category CRUD Endpoints

```
GET    /categories/:businessId              → public: list active categories with counts
GET    /admin/categories/:businessId        → admin: list all (including inactive)
POST   /admin/categories                    → create new category
PUT    /admin/categories/:categoryId        → update name, image, sort_order, active
DELETE /admin/categories/:categoryId        → soft delete (is_active = false)
PUT    /admin/categories/reorder            → bulk sort_order update (drag-and-drop)
```

**`POST /admin/categories` request:**
```json
{
  "business_id": "whisked_words",
  "display_name": "Namkeen",
  "description": "Crispy savory snacks",
  "icon_emoji": "🥨",
  "sort_order": 12,
  "is_featured": false
}
```
The `category_id` is **auto-generated** as a URL-safe slug from `display_name` (`"Namkeen"` → `"namkeen"`). No developer input needed.

### 1C. Remove All Hardcoded Category Maps

Delete `format_category_name()` from `backend/ecommerce_routes.py`. Replace all usages with a DB lookup:

```python
# OLD — DELETE THIS
def format_category_name(category_id: str) -> str:
    name_map = {"featured": "Featured Items", "cakes": "Cakes", ...}
    return name_map.get(category_id, category_id.replace("_", " ").title())

# NEW — fetch from DB, cache in-memory for 5 minutes
_category_cache: Dict[str, Dict] = {}

async def get_category_display(business_id: str, category_id: str) -> dict:
    cache_key = f"{business_id}:{category_id}"
    if cache_key not in _category_cache:
        cat = await db.categories.find_one(
            {"business_id": business_id, "category_id": category_id}
        )
        _category_cache[cache_key] = cat or {
            "category_id": category_id,
            "display_name": category_id.replace("_", " ").title()
        }
    return _category_cache[cache_key]
```

### 1D. Category Count Sync (Background Task)

Product counts per category are cached on the category document and refreshed every 10 minutes:

```python
async def refresh_category_counts():
    pipeline = [
        {"$match": {"is_active": True}},
        {"$group": {"_id": {"business": "$business_id", "cat": "$category_id"}, "count": {"$sum": 1}}}
    ]
    results = await db.products.aggregate(pipeline).to_list(1000)
    for r in results:
        await db.categories.update_one(
            {"business_id": r["_id"]["business"], "category_id": r["_id"]["cat"]},
            {"$set": {"product_count": r["count"]}}
        )
```

---

## Upgrade 2 — Product Schema: Config-Driven Fields

### 2A. Remove All Hardcoded Product Attributes

Currently `attributes` is a free-form `Dict[str, Any]`. This stays flexible, but the admin UI will provide a **structured form** based on the business's configured attribute schema (see Upgrade 10).

New top-level fields added to product documents:

```python
class ProductCreate(BaseModel):
    business_id: str
    product_name: str
    description: Optional[str] = None
    base_price: float
    category_id: str                        # Must reference a valid category in categories collection
    subcategory_id: Optional[str] = None    # Optional sub-category
    images: Optional[List[dict]] = []
    variants: Optional[List[dict]] = []
    
    # Config-driven fields (all editable via admin UI)
    is_veg: Optional[bool] = None           # True/False/None (not applicable)
    is_featured: bool = False               # Show in "Featured Items" section
    is_bestseller: bool = False             # Manually overrideable; also auto-computed
    has_active_offer: bool = False          # Computed when offer is applied
    collection_tags: List[str] = []         # References collection_ids
    addons: List[ProductAddonGroup] = []    # Add-on groups (see below)
    allergens: List[str] = []               # ["Eggs", "Wheat", "Dairy", "Soy"]
    sort_order: int = 0                     # Within-category ordering
    is_active: bool = True
    attributes: Optional[Dict[str, Any]] = {}  # Flexible extra attrs
```

### 2B. Add-on Groups (Fully Admin-Managed)

```python
class ProductAddonItem(BaseModel):
    addon_item_id: str          # auto-generated
    name: str                   # "Lemon Iced Tea"
    price: float                # 0.0 = included, >0 = extra charge
    is_veg: Optional[bool] = None
    image_url: Optional[str] = None
    is_available: bool = True

class ProductAddonGroup(BaseModel):
    group_id: str               # auto-generated
    group_name: str             # "COLD BEVERAGES"
    type: str                   # "optional" | "required"
    min_select: int = 0
    max_select: int = 1
    display_label: Optional[str] = None  # "You can choose up to 3 options"
    items: List[ProductAddonItem] = []
```

Admin can create, edit, delete addon groups directly from the product edit page. No code changes needed when a new combo type is introduced.

### 2C. Product Endpoints — Extended

```
GET    /products                            → list (extended filters, see below)
GET    /products/:productId                 → single product with full addons
POST   /admin/products                      → create product
PUT    /admin/products/:productId           → full update
PATCH  /admin/products/:productId           → partial update (e.g., toggle is_active)
DELETE /admin/products/:productId           → soft delete

# Add-on management (nested under product)
POST   /admin/products/:productId/addons    → add addon group
PUT    /admin/products/:productId/addons/:groupId   → update group
DELETE /admin/products/:productId/addons/:groupId   → remove group
POST   /admin/products/:productId/addons/:groupId/items  → add item to group
PUT    /admin/products/:productId/addons/:groupId/items/:itemId  → update item
DELETE /admin/products/:productId/addons/:groupId/items/:itemId  → remove item
```

**Extended GET /products filters:**
```
business_id, category_id, subcategory_id, collection,
is_veg, is_featured, is_bestseller, has_active_offer,
min_price, max_price, min_rating, keyword,
sort_by (price_asc|price_desc|rating|popular|newest|sort_order),
limit, offset
```

---

## Upgrade 3 — Collections System (Admin-Managed)

Collections are **user-created product groupings** managed entirely via admin UI. Examples: Gifting, Festive, Corporate, New Arrivals, Speciality Cakes.

### Collections Collection Schema

```python
class Collection(BaseModel):
    collection_id: str              # Auto slug: "gifting"
    business_id: str
    display_name: str               # "Gifting"
    description: str
    banner_image_url: Optional[str] = None
    illustration_url: Optional[str] = None
    filters: Optional[dict] = {}    # Pre-set filters for this collection page
    sort_order: int = 0
    is_active: bool = True
    show_in_nav: bool = False       # Show as nav link in navbar
    show_on_homepage: bool = True   # Show as tile on business home
    created_at: datetime
    updated_at: datetime
```

### Endpoints

```
GET  /collections/:businessId              → public: active collections
GET  /admin/collections/:businessId        → admin: all collections
POST /admin/collections                    → create collection
PUT  /admin/collections/:collectionId      → update
DELETE /admin/collections/:collectionId    → soft delete

# Products are tagged to collections via product's collection_tags field
PUT  /admin/products/:productId/collections  → set collection_tags array
```

Products are assigned to collections by editing the product's `collection_tags` from the product edit form. A collection is just a filter view — it doesn't store product references directly (avoids sync issues).

---

## Upgrade 4 — Store Config (Admin-Managed)

Every setting shown in the order navbar is editable from the admin dashboard.

### Store Config Schema

```python
class BusinessHours(BaseModel):
    day: str            # "monday", "tuesday", etc.
    is_open: bool = True
    open_time: str      # "08:00"
    close_time: str     # "22:00"

class StoreConfig(BaseModel):
    business_id: str
    store_display_name: str             # Shown in order navbar
    location_label: str                 # "HSR Layout, Bengaluru"
    is_temporarily_closed: bool = False
    closed_reason: Optional[str] = None # "Closed for maintenance"
    business_hours: List[BusinessHours] = []
    order_types: List[str] = ["delivery"]  # ["delivery", "takeaway", "dine_in"]
    delivery_radius_km: float = 10.0
    min_order_delivery: float = 199.0
    delivery_charge: float = 50.0
    free_delivery_above: Optional[float] = None  # Free delivery if order > X
    estimated_delivery_time: str = "30-45 mins"
    estimated_prep_time: str = "15-20 mins"
    currency: str = "INR"
    currency_symbol: str = "₹"
    tax_rate: float = 0.05              # 5% GST
    is_open: bool = True                # Computed field
    updated_at: datetime
```

### Endpoints

```
GET  /store/info/:businessId          → public: current store status + settings
GET  /admin/store/:businessId         → admin: full config
PUT  /admin/store/:businessId         → full update
PATCH /admin/store/:businessId        → partial update (e.g., toggle temporarily_closed)
```

**`is_open` computation** (done server-side, not hardcoded):
```python
def compute_is_open(config: StoreConfig) -> bool:
    if config.is_temporarily_closed:
        return False
    from datetime import datetime
    import pytz
    now = datetime.now(pytz.timezone("Asia/Kolkata"))
    day = now.strftime("%A").lower()
    today = next((h for h in config.business_hours if h.day == day), None)
    if not today or not today.is_open:
        return False
    current_time = now.strftime("%H:%M")
    return today.open_time <= current_time <= today.close_time
```

---

## Upgrade 5 — Offers System (Admin-Managed)

### Offers Collection Schema

```python
class OfferType(str, Enum):
    percentage = "percentage"
    flat_amount = "flat_amount"
    free_delivery = "free_delivery"
    buy_x_get_y = "buy_x_get_y"

class OfferScope(str, Enum):
    all_products = "all_products"
    specific_categories = "specific_categories"   # category_ids list
    specific_products = "specific_products"        # product_ids list
    specific_collections = "specific_collections"  # collection_ids list

class Offer(BaseModel):
    offer_id: str
    business_id: str
    title: str                          # "FLAT 15% OFF on all combos"
    description: Optional[str] = None  # Shown in offers panel
    promo_code: Optional[str] = None   # None = auto-applied
    offer_type: OfferType
    discount_value: float
    max_discount_cap: Optional[float] = None
    min_order_amount: float = 0.0
    scope: OfferScope = OfferScope.all_products
    scope_ids: List[str] = []           # category/product/collection ids
    valid_from: datetime
    valid_until: datetime
    is_active: bool = True
    is_auto_apply: bool = False         # Apply without code
    usage_limit: Optional[int] = None
    usage_count: int = 0
    per_user_limit: int = 1
    show_in_offers_panel: bool = True
    created_by: str
    created_at: datetime
    updated_at: datetime
```

### Endpoints

```
GET  /offers/:businessId               → public: active displayable offers
POST /offers/validate                  → validate promo code at checkout
GET  /admin/offers/:businessId         → admin: all offers including expired
POST /admin/offers                     → create offer
PUT  /admin/offers/:offerId            → update offer
DELETE /admin/offers/:offerId          → deactivate
GET  /admin/offers/:offerId/stats      → usage statistics
```

---

## Upgrade 6 — Announcement Bar (Admin-Managed)

```python
class Announcement(BaseModel):
    announcement_id: str
    business_id: str
    message: str                # "Upto Rs. 200 OFF on the First Order. T&C apply."
    link_url: Optional[str] = None
    link_text: Optional[str] = None
    bg_color: str = "#4A3B32"
    text_color: str = "#FAF8F5"
    is_active: bool = True
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    priority: int = 0           # Higher = shown first if multiple active
    created_at: datetime
    updated_at: datetime
```

```
GET  /announcements/:businessId   → active announcement (public)
GET  /admin/announcements/:businessId  → admin: all
POST /admin/announcements         → create
PUT  /admin/announcements/:id     → update
DELETE /admin/announcements/:id   → delete
```

---

## Upgrade 7 — Cart & Order: Add-ons + Offer Support

### Extended Cart Item

```python
class SelectedAddonItem(BaseModel):
    addon_item_id: str
    name: str
    price: float

class SelectedAddonGroup(BaseModel):
    group_id: str
    group_name: str
    selected_items: List[SelectedAddonItem]

class CartItem(BaseModel):
    product_id: str
    variant_id: Optional[str] = None
    product_name: str
    quantity: int
    price: float
    addons_price: float = 0.0
    total_item_price: float = 0.0
    image_url: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = {}
    selected_addons: List[SelectedAddonGroup] = []   # NEW

class CartCreate(BaseModel):
    product_id: str
    variant_id: Optional[str] = None
    quantity: int = 1
    selected_addons: List[SelectedAddonGroup] = []   # NEW
```

### Extended Order

```python
class OrderType(str, Enum):
    delivery = "delivery"
    takeaway = "takeaway"
    dine_in = "dine_in"

class OrderCreate(BaseModel):
    items: List[OrderItem]
    delivery_info: DeliveryInfo
    payment_method: str
    subtotal: float
    tax: float
    delivery_charge: float
    discount_amount: float = 0.0
    promo_code: Optional[str] = None
    offer_id: Optional[str] = None
    total: float
    order_type: OrderType = OrderType.delivery
    notes: Optional[str] = None
```

---

## Upgrade 8 — Background Tasks

```python
# File: backend/trending_refresh.py (extend existing)

async def refresh_product_stats():
    """Every 30 min: update total_ordered + is_bestseller."""
    ...

async def refresh_category_counts():
    """Every 10 min: sync product_count on each category document."""
    ...

async def expire_offers():
    """Every hour: set is_active=False on expired offers."""
    await db.offers.update_many(
        {"valid_until": {"$lt": datetime.utcnow()}, "is_active": True},
        {"$set": {"is_active": False}}
    )

async def sync_has_active_offer():
    """Every hour: update has_active_offer flag on products based on active offers."""
    active_offers = await db.offers.find({"is_active": True}).to_list(100)
    # Build set of affected product_ids and category_ids
    # Update products.has_active_offer accordingly
    ...
```

---

## Upgrade 9 — MongoDB Indexes

```python
async def create_indexes():
    # Categories
    await db.categories.create_index([("business_id", 1), ("is_active", 1), ("sort_order", 1)])
    await db.categories.create_index([("business_id", 1), ("category_id", 1)], unique=True)

    # Products
    await db.products.create_index([("business_id", 1), ("category_id", 1), ("is_active", 1)])
    await db.products.create_index([("business_id", 1), ("collection_tags", 1)])
    await db.products.create_index([("business_id", 1), ("is_featured", 1)])
    await db.products.create_index([("business_id", 1), ("is_bestseller", 1)])
    await db.products.create_index([("business_id", 1), ("is_veg", 1)])
    await db.products.create_index([("business_id", 1), ("avg_rating", -1)])
    await db.products.create_index([("business_id", 1), ("total_ordered", -1)])
    await db.products.create_index([("product_name", "text"), ("description", "text")])

    # Collections
    await db.collections.create_index([("business_id", 1), ("is_active", 1)])

    # Offers
    await db.offers.create_index([("business_id", 1), ("is_active", 1), ("valid_until", 1)])
    await db.offers.create_index([("promo_code", 1)])

    # Store config
    await db.store_config.create_index([("business_id", 1)], unique=True)

    # Announcements
    await db.announcements.create_index([("business_id", 1), ("is_active", 1), ("priority", -1)])
```

---

## Upgrade 10 — Admin Dashboard: New Management Sections

These are the pages needed in the frontend admin UI (described here for backend context — full UI detail in `ui-upgrade-plan.md`).

### Backend endpoints backing each admin section:

**Category Manager** (replaces hardcoded category map):
```
GET/POST/PUT/DELETE /admin/categories/:businessId
PUT /admin/categories/reorder   → bulk sort_order update
```

**Product Manager** (extends existing add product modal):
```
GET/POST/PUT/DELETE /admin/products
POST/PUT/DELETE /admin/products/:id/addons/**
PUT /admin/products/:id/collections
PATCH /admin/products/:id (toggle is_active, is_featured, etc.)
```

**Collection Manager**:
```
GET/POST/PUT/DELETE /admin/collections/:businessId
```

**Offers Manager**:
```
GET/POST/PUT/DELETE /admin/offers/:businessId
POST /offers/validate (used by checkout)
```

**Store Config Manager**:
```
GET/PUT/PATCH /admin/store/:businessId
```

**Announcement Manager**:
```
GET/POST/PUT/DELETE /admin/announcements/:businessId
```

**Inventory Manager** (extends existing):
```
# Existing endpoints extended with:
PUT /admin/inventory/:id/reorder-level  → set reorder threshold
GET /admin/inventory/alerts/:businessId → low stock + out of stock
```

---

## Upgrade 11 — Role-Based Access Control (Enforcement)

All admin endpoints must enforce role checks. Current state is unclear — add explicit middleware:

```python
# backend/auth_middleware.py
def require_role(*roles: str):
    """Dependency: ensures authenticated user has one of the required roles."""
    async def checker(current_user = Depends(get_current_user)):
        if current_user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return checker

def require_business_access(business_id_param: str = "business_id"):
    """Ensures business_admin can only modify their own business."""
    async def checker(
        business_id: str,
        current_user = Depends(get_current_user)
    ):
        if current_user["role"] == "super_admin":
            return current_user  # super_admin can access any business
        if current_user.get("business_id") != business_id:
            raise HTTPException(status_code=403, detail="Access denied for this business")
        return current_user
    return checker

# Usage in routes:
@router.post("/admin/categories", dependencies=[Depends(require_role("super_admin", "business_admin"))])
async def create_category(data: CategoryCreate, current_user=Depends(require_business_access())):
    ...
```

**Role matrix for new endpoints:**

| Endpoint | super_admin | business_admin | staff |
|---|---|---|---|
| Create/edit/delete category | ✅ any business | ✅ own business | ❌ |
| Create/edit product | ✅ | ✅ own | ❌ |
| Manage offers | ✅ | ✅ own | ❌ |
| Edit store config | ✅ | ✅ own | ❌ |
| View inventory | ✅ | ✅ own | ✅ own |
| Adjust inventory | ✅ | ✅ own | ✅ own |
| Create announcement | ✅ | ✅ own | ❌ |

---

## File Structure (New Files Only)

```
backend/
├── NEW: category_routes.py         # Category CRUD
├── NEW: collections_routes.py      # Collections CRUD
├── NEW: store_routes.py            # Store config endpoints
├── NEW: offers_routes.py           # Offers CRUD + validate
├── NEW: announcements_routes.py    # Announcement bar config
├── NEW: auth_middleware.py         # Role enforcement helpers
├── NEW: category_cache.py          # In-memory category cache
│
├── MODIFY: ecommerce_models.py     # Add addons, is_veg, collection_tags, etc.
├── MODIFY: ecommerce_routes.py     # Remove format_category_name(), extend GET /products
├── MODIFY: server.py               # Register new routers, startup indexes + cache warm
├── MODIFY: trending_refresh.py     # Add category count + offer expiry tasks
│
└── migrations/
    ├── 001_add_product_fields.py   # Safe defaults for new product fields
    └── 002_seed_categories.py      # Seed existing category_ids into categories collection
```

---

## Migration Plan

Run in this exact order — all backward compatible:

```
1. Run 001_add_product_fields.py
   → Adds is_veg, is_featured, collection_tags, addons, sort_order to all products

2. Run 002_seed_categories.py
   → Reads distinct category_id values from products collection
   → Creates category documents for each (display_name = auto-formatted slug)
   → Admin then refines names/images/sort_order via UI

3. Create all MongoDB indexes (non-blocking)

4. Deploy new route files (additive — no breaking changes)

5. Deploy ecommerce_models.py changes (all new fields have Optional/defaults)

6. Deploy extended GET /products (new params are all optional)

7. Remove format_category_name() — replace with DB lookup

8. Deploy trending_refresh.py updates (add new background tasks)

9. Seed store_config document for whisked_words via admin UI or migration

10. Seed 2–3 sample offers via admin UI
```

---

## Testing Checklist

| Test | Assertion |
|---|---|
| `POST /admin/categories` | Slug auto-generated, appears in `GET /categories/:businessId` |
| Create "Namkeen" category | Shows in sidebar without any code change |
| `PUT /admin/categories/reorder` | Sidebar order updates on next fetch |
| Delete category | Products in it still exist; category hidden from nav |
| `GET /products?category_id=namkeen` | Returns only namkeen products |
| `GET /products?is_veg=true` | Returns only veg products |
| `GET /products?collection=gifting` | Returns tagged products |
| `POST /admin/offers` with scope=category | Offer applies only to that category at checkout |
| `POST /offers/validate` | Returns correct discount; respects per_user_limit |
| `PATCH /admin/store/:businessId` closed=true | `GET /store/info` returns `is_open: false` |
| `POST /admin/products/:id/addons` | Addon group saved; appears in product detail |
| business_admin cannot edit another business | Returns 403 |
| super_admin can edit any business | Returns 200 |


1	Backend core: categories, products extended, routes	~60,000
2	Admin UI: CategoryManager + ProductManager + AddonsBuilder	~80,000
3	Admin UI: Offers, Store Config, Announcements, Collections	~70,000
4	Customer UI: ProductCatalog overhaul + sidebar + chips	~60,000
5	Customer UI: Modals, cards, floating cart, navbar	~70,000
6	Migrations, seed data, testing, polish