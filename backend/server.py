from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, Response
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import asyncio
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
from datetime import datetime, timezone, timedelta
import uuid
import httpx

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
db = client[os.environ['DB_NAME']]


def _is_production() -> bool:
    return os.environ.get("ENVIRONMENT", "development").lower() == "production"


def _cors_origins() -> list:
    raw = os.environ.get("CORS_ORIGINS", "http://localhost:3000")
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    if "*" in origins:
        return ["http://localhost:3000"]
    return origins

# Create the main app
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


@api_router.get("/health")
async def health():
    """ALB / ECS health check"""
    return {"status": "ok"}


# ============= AUTHENTICATION MIDDLEWARE =============
async def get_current_user(request: Request):
    """Validate session and return current user"""
    # Try cookie first
    session_token = request.cookies.get("session_token")
    
    # Fallback to Authorization header
    if not session_token:
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header.split(" ")[1]
    
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Validate session
    session = await db.user_sessions.find_one(
        {"session_token": session_token},
        {"_id": 0}
    )
    
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    # Check expiry
    expires_at = session.get("expires_at")
    if expires_at:
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Session expired")
    
    # Get user
    user = await db.users.find_one(
        {"user_id": session["user_id"]},
        {"_id": 0}
    )
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user

# ============= RBAC HELPER =============
def require_role(allowed_roles: list):
    """Decorator to check if user has required role"""
    async def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Access forbidden")
        return current_user
    return role_checker

async def check_business_access(user: dict, business_id: str) -> bool:
    """Check if user has access to specific business"""
    # Super admin has access to all
    if user["role"] == "super_admin":
        return True
    
    # Check business_access array
    for access in user.get("business_access", []):
        if access["business_id"] == business_id:
            return True
    
    return False


async def ensure_user_preferences_indexes() -> None:
    """Create TTL and unique indexes on user_preferences if they don't already exist."""
    # TTL index: MongoDB auto-deletes documents when expires_at is reached (expireAfterSeconds=0)
    await db.user_preferences.create_index(
        [("expires_at", 1)],
        expireAfterSeconds=0,
        background=True,
        name="user_preferences_ttl_expires_at"
    )
    # Unique index on user_id so each user has at most one preferences document
    await db.user_preferences.create_index(
        [("user_id", 1)],
        unique=True,
        background=True,
        name="user_preferences_unique_user_id"
    )


async def compute_preference_vector(user_id: str) -> dict:
    """
    Derive a preference_vector for a user from their product_views and orders.

    Returns:
        {
            "top_flavors": [...],       # up to 3 most frequent flavors
            "top_occasions": [...],     # up to 3 most frequent occasions
            "price_range": {"min": ..., "max": ...}  # from ordered product prices
        }
    """
    from collections import Counter

    flavor_counter: Counter = Counter()
    occasion_counter: Counter = Counter()
    prices: list = []

    # --- gather data from product_views (up to 20 most recent) ---
    viewed = await db.product_views.find(
        {"user_id": user_id},
        {"_id": 0, "product_id": 1}
    ).sort("last_viewed", -1).to_list(20)

    viewed_product_ids = [v["product_id"] for v in viewed]
    if viewed_product_ids:
        viewed_products = await db.products.find(
            {"product_id": {"$in": viewed_product_ids}},
            {"_id": 0, "attributes": 1, "base_price": 1}
        ).to_list(len(viewed_product_ids))

        for p in viewed_products:
            attrs = p.get("attributes", {})
            if isinstance(attrs, dict):
                flavor = attrs.get("flavor") or attrs.get("flavour")
                if flavor:
                    flavor_counter[str(flavor).lower()] += 1
                occasion = attrs.get("occasion")
                if occasion:
                    occasion_counter[str(occasion).lower()] += 1
            price = p.get("base_price")
            if price is not None:
                prices.append(float(price))

    # --- gather data from orders (up to 10 most recent) ---
    user_orders = await db.orders.find(
        {"user_id": user_id},
        {"_id": 0, "items": 1}
    ).sort("created_at", -1).to_list(10)

    ordered_product_ids = []
    for order in user_orders:
        for item in order.get("items", []):
            ordered_product_ids.append(item["product_id"])

    if ordered_product_ids:
        ordered_products = await db.products.find(
            {"product_id": {"$in": ordered_product_ids}},
            {"_id": 0, "attributes": 1, "base_price": 1}
        ).to_list(len(ordered_product_ids))

        for p in ordered_products:
            attrs = p.get("attributes", {})
            if isinstance(attrs, dict):
                flavor = attrs.get("flavor") or attrs.get("flavour")
                if flavor:
                    # Orders weighted 2x over views
                    flavor_counter[str(flavor).lower()] += 2
                occasion = attrs.get("occasion")
                if occasion:
                    occasion_counter[str(occasion).lower()] += 2
            price = p.get("base_price")
            if price is not None:
                prices.append(float(price))

    top_flavors = [f for f, _ in flavor_counter.most_common(3)]
    top_occasions = [o for o, _ in occasion_counter.most_common(3)]

    if prices:
        price_range = {"min": min(prices), "max": max(prices)}
    else:
        price_range = {"min": 0, "max": 0}

    return {
        "top_flavors": top_flavors,
        "top_occasions": top_occasions,
        "price_range": price_range,
    }

@api_router.post("/auth/google")
async def google_login(request: Request, response: Response):
    """Verify Google ID token and create session"""
    body = await request.json()
    token = body.get("token")
    
    if not token:
        raise HTTPException(status_code=400, detail="token required")
    
    try:
        # Verify Google JWT
        client_id = os.environ.get("GOOGLE_CLIENT_ID")
        if not client_id:
            raise HTTPException(status_code=500, detail="Google Client ID not configured")
            
        idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), client_id)
        
        # Check if user exists
        user = await db.users.find_one({"email": idinfo["email"]}, {"_id": 0})
        
        if not user:
            # Create new user
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            user = {
                "user_id": user_id,
                "email": idinfo["email"],
                "name": idinfo.get("name", ""),
                "picture": idinfo.get("picture", ""),
                "role": os.environ.get("DEFAULT_NEW_USER_ROLE", "customer"),
                "business_access": [],
                "status": "active",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "last_login": datetime.now(timezone.utc)
            }
            await db.users.insert_one(user.copy())
        else:
            # Update last login
            await db.users.update_one(
                {"user_id": user["user_id"]},
                {"$set": {"last_login": datetime.now(timezone.utc)}}
            )
        
        # Create session
        session_data = {
            "session_id": str(uuid.uuid4()),
            "user_id": user["user_id"],
            "session_token": f"token_{uuid.uuid4().hex}",
            "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
            "created_at": datetime.now(timezone.utc),
            "ip_address": request.client.host,
            "user_agent": request.headers.get("user-agent", "")
        }
        await db.user_sessions.insert_one(session_data)
        
        # Local dev uses HTTP — Secure cookies are ignored by the browser on http://localhost
        response.set_cookie(
            key="session_token",
            value=session_data["session_token"],
            httponly=True,
            secure=_is_production(),
            samesite="none" if _is_production() else "lax",
            path="/",
            max_age=7 * 24 * 60 * 60,
        )

        # --- Compute preference vector and recommended products for this user ---
        preference_vector = await compute_preference_vector(user["user_id"])

        # Determine which business to pull recommendations from.
        # Use the most recently viewed business, falling back to the first business
        # the user has access to, or any active business if neither is available.
        rec_business_id = None
        recent_view = await db.product_views.find_one(
            {"user_id": user["user_id"]},
            {"_id": 0, "business_id": 1},
            sort=[("last_viewed", -1)]
        )
        if recent_view:
            rec_business_id = recent_view.get("business_id")

        if not rec_business_id:
            # Fall back to first business in user's access list
            accesses = user.get("business_access", [])
            if accesses:
                rec_business_id = accesses[0]["business_id"]

        if not rec_business_id:
            # Fall back to any active business
            any_biz = await db.businesses.find_one({"status": "active"}, {"_id": 0, "business_id": 1})
            if any_biz:
                rec_business_id = any_biz["business_id"]

        recommended_product_ids: list = []
        if rec_business_id:
            top_products = await db.products.find(
                {"business_id": rec_business_id, "status": "active"},
                {"_id": 0, "product_id": 1, "avg_rating": 1}
            ).sort("avg_rating", -1).limit(6).to_list(6)
            recommended_product_ids = [p["product_id"] for p in top_products]

        # Upsert the user_preferences document (TTL-managed by MongoDB, expires in 12 h)
        now_utc = datetime.now(timezone.utc)
        await db.user_preferences.replace_one(
            {"user_id": user["user_id"]},
            {
                "user_id": user["user_id"],
                "recommended_product_ids": recommended_product_ids,
                "preference_vector": preference_vector,
                "computed_at": now_utc.isoformat(),
                "expires_at": (now_utc + timedelta(hours=12)),
            },
            upsert=True
        )

        return {
            "user": {
                "user_id": user["user_id"],
                "email": user["email"],
                "name": user["name"],
                "picture": user["picture"],
                "role": user["role"],
                "business_access": user.get("business_access", []),
                "is_prime": user.get("is_prime", False)
            },
            "recommendations": recommended_product_ids,
            "preference_summary": preference_vector,
            "message": "Login successful"
        }
    except ValueError as e:
        logger.warning("Invalid Google token: %s", e)
        raise HTTPException(status_code=401, detail="Invalid Google token")
    except Exception as e:
        logger.exception("Google login failed")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/auth/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user details"""
    return {
        "user_id": current_user["user_id"],
        "email": current_user["email"],
        "name": current_user["name"],
        "picture": current_user["picture"],
        "role": current_user["role"],
        "business_access": current_user.get("business_access", []),
        "status": current_user["status"],
        "is_prime": current_user.get("is_prime", False)
    }

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response, current_user: dict = Depends(get_current_user)):
    """Logout current user"""
    session_token = request.cookies.get("session_token")
    
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    
    response.delete_cookie(key="session_token", path="/")
    return {"message": "Logged out successfully"}

# ============= BUSINESS ROUTES =============
@api_router.get("/businesses")
async def list_businesses(current_user: dict = Depends(get_current_user)):
    """List all businesses (filtered by access for non-super-admin)"""
    if current_user["role"] == "super_admin":
        businesses = await db.businesses.find({}, {"_id": 0}).to_list(100)
    else:
        # Get businesses user has access to
        business_ids = [access["business_id"] for access in current_user.get("business_access", [])]
        businesses = await db.businesses.find(
            {"business_id": {"$in": business_ids}},
            {"_id": 0}
        ).to_list(100)
    
    return {"businesses": businesses, "total": len(businesses)}

@api_router.get("/businesses/public")
async def list_public_businesses():
    """List all active businesses (public route)"""
    businesses = await db.businesses.find(
        {"status": "active"},
        {"_id": 0}
    ).to_list(100)
    return {"businesses": businesses, "total": len(businesses)}

@api_router.get("/businesses/{business_id}")
async def get_business(business_id: str):
    """Get specific business details (public)"""
    business = await db.businesses.find_one({"business_id": business_id}, {"_id": 0})
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business

# ============= PRODUCT ROUTES =============
@api_router.get("/products")
async def list_products(
    business_id: str,
    category_id: str = None,
    status: str = "active",
    page: int = 1,
    limit: int = 50
):
    """List products (public route)"""
    query = {"business_id": business_id, "status": status}
    if category_id:
        query["category_id"] = category_id
    
    skip = (page - 1) * limit
    products = await db.products.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
    total = await db.products.count_documents(query)
    
    return {
        "products": products,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit
        }
    }

@api_router.get("/products/trending/{business_id}")
async def get_trending_products(business_id: str, limit: int = 6):
    """
    Return pre-computed trending products sorted by trending_score.

    Scores are written directly onto product documents by the background
    refresh job (trending_refresh.py) which runs every 15 minutes.

    Previous implementation: 2N+1 DB round-trips (one aggregation + one
    reviews query per product — classic N+1 problem).
    Current implementation: 1 DB round-trip (indexed sort + limit).
    """
    products = await db.products.find(
        {"business_id": business_id, "status": "active"},
        {"_id": 0}
    ).sort("trending_score", -1).limit(limit).to_list(limit)

    # Graceful fallback: background job hasn't run yet (first boot) or
    # no products have a trending_score field stored yet.
    if not products or products[0].get("trending_score") is None:
        logger.warning(
            "trending scores not yet computed for business=%s — falling back to avg_rating",
            business_id
        )
        products = await db.products.find(
            {"business_id": business_id, "status": "active"},
            {"_id": 0}
        ).sort("avg_rating", -1).limit(limit).to_list(limit)

    return {"trending": products, "total": len(products)}

@api_router.post("/products/track-view")
async def track_product_view(request: Request):
    """Track a product view for the current user (stores in DB for recommendations)"""
    body = await request.json()
    product_id = body.get("product_id")
    business_id = body.get("business_id")
    if not product_id or not business_id:
        raise HTTPException(status_code=400, detail="product_id and business_id required")

    # Get optional user
    user = None
    token = request.cookies.get("session_token") or request.headers.get("authorization", "").replace("Bearer ", "")
    if token:
        session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
        if session:
            user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})

    user_id = user["user_id"] if user else None
    if not user_id:
        return {"message": "View tracked locally only"}

    # Upsert the view record — one entry per user+product, update timestamp + increment count
    await db.product_views.update_one(
        {"user_id": user_id, "product_id": product_id},
        {
            "$set": {
                "business_id": business_id,
                "last_viewed": datetime.now(timezone.utc).isoformat()
            },
            "$inc": {"view_count": 1},
            "$setOnInsert": {
                "user_id": user_id,
                "product_id": product_id,
                "first_viewed": datetime.now(timezone.utc).isoformat()
            }
        },
        upsert=True
    )
    return {"message": "View tracked"}

@api_router.get("/products/recommended/{business_id}")
async def get_recommended_products(request: Request, business_id: str, limit: int = 4):
    """Get personalized product recommendations based on view/order history"""
    # Get optional user
    user = None
    token = request.cookies.get("session_token") or request.headers.get("authorization", "").replace("Bearer ", "")
    if token:
        session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
        if session:
            user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})

    all_products = await db.products.find(
        {"business_id": business_id, "status": "active"},
        {"_id": 0}
    ).to_list(200)

    if not all_products:
        return {"recommended": [], "total": 0, "strategy": "none"}

    user_id = user["user_id"] if user else None
    recommended = []
    strategy = "top_rated"  # default fallback

    if user_id:
        # Get products the user has viewed
        viewed = await db.product_views.find(
            {"user_id": user_id, "business_id": business_id},
            {"_id": 0}
        ).sort("last_viewed", -1).to_list(20)
        viewed_ids = {v["product_id"] for v in viewed}

        # Get products the user has ordered
        user_orders = await db.orders.find(
            {"user_id": user_id},
            {"_id": 0, "items": 1}
        ).to_list(50)
        ordered_ids = set()
        for order in user_orders:
            for item in order.get("items", []):
                ordered_ids.add(item["product_id"])

        # Get categories of viewed/ordered products
        interacted_ids = viewed_ids | ordered_ids
        interacted_categories = set()
        for p in all_products:
            if p["product_id"] in interacted_ids and p.get("category_id"):
                interacted_categories.add(p["category_id"])

        # Strategy 1: Products in same categories user has interacted with, but hasn't bought
        if interacted_categories:
            strategy = "category_match"
            candidates = [
                p for p in all_products
                if p.get("category_id") in interacted_categories
                and p["product_id"] not in ordered_ids
            ]
            if candidates:
                recommended = candidates

        # Strategy 2: Frequently bought together — find what OTHER users who bought the same items also bought
        if not recommended and ordered_ids:
            strategy = "also_bought"
            co_purchase_pipeline = [
                {"$match": {"items.product_id": {"$in": list(ordered_ids)}}},
                {"$match": {"user_id": {"$ne": user_id}}},
                {"$unwind": "$items"},
                {"$match": {"items.product_id": {"$nin": list(ordered_ids)}}},
                {"$group": {"_id": "$items.product_id", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": limit}
            ]
            co_purchases = await db.orders.aggregate(co_purchase_pipeline).to_list(limit)
            co_ids = {cp["_id"] for cp in co_purchases}
            candidates = [p for p in all_products if p["product_id"] in co_ids]
            if candidates:
                recommended = candidates

        # Strategy 3: Products the user hasn't interacted with yet (discovery)
        if not recommended and interacted_ids:
            strategy = "discovery"
            recommended = [p for p in all_products if p["product_id"] not in interacted_ids]

    # Fallback: top-rated products
    if not recommended:
        strategy = "top_rated"
        recommended = all_products

    # Enrich with review data and sort by rating
    enriched = []
    for product in recommended:
        pid = product["product_id"]
        reviews = await db.reviews.find({"product_id": pid}, {"_id": 0, "rating": 1}).to_list(500)
        review_count = len(reviews)
        avg_rating = round(sum(r["rating"] for r in reviews) / review_count, 1) if review_count else 0
        enriched.append({
            **product,
            "review_count": review_count,
            "avg_rating": avg_rating
        })

    enriched.sort(key=lambda x: (x["avg_rating"], x["review_count"]), reverse=True)
    result = enriched[:limit]

    return {"recommended": result, "total": len(result), "strategy": strategy}

@api_router.get("/products/{product_id}")
async def get_product(product_id: str):
    """Get product details (public)"""
    product = await db.products.find_one({"product_id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@api_router.post("/products")
async def create_product(
    request: Request,
    current_user: dict = Depends(require_role(["super_admin", "business_admin", "staff"]))
):
    """Create new product"""
    data = await request.json()
    business_id = data.get("business_id")
    
    if not business_id:
        raise HTTPException(status_code=400, detail="business_id required")
    
    # Check access
    if not await check_business_access(current_user, business_id):
        raise HTTPException(status_code=403, detail="Access denied to this business")
    
    product_id = f"prod_{uuid.uuid4().hex[:12]}"
    product_data = {
        "product_id": product_id,
        "business_id": business_id,
        "category_id": data.get("category_id"),
        "product_name": data.get("product_name"),
        "description": data.get("description", ""),
        "base_price": data.get("base_price", 0),
        "currency": data.get("currency", "INR"),
        "images": data.get("images", []),
        "attributes": data.get("attributes", {}),
        "variants": data.get("variants", []),
        "status": "active",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    # Add variant_id to each variant
    for i, variant in enumerate(product_data["variants"]):
        if "variant_id" not in variant:
            variant["variant_id"] = f"var_{i+1:03d}"
    
    await db.products.insert_one(product_data)
    
    # Create inventory records for each variant
    if product_data["variants"]:
        for variant in product_data["variants"]:
            inventory_data = {
                "inventory_id": f"inv_{uuid.uuid4().hex[:12]}",
                "business_id": business_id,
                "product_id": product_id,
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
    else:
        # No variants, create single inventory
        inventory_data = {
            "inventory_id": f"inv_{uuid.uuid4().hex[:12]}",
            "business_id": business_id,
            "product_id": product_id,
            "variant_id": None,
            "sku": data.get("sku", ""),
            "quantity": {
                "available": data.get("inventory_count", 0),
                "reserved": 0,
                "total": data.get("inventory_count", 0)
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
    
    return {"product_id": product_id, "message": "Product created successfully"}

@api_router.put("/products/{product_id}")
async def update_product(
    product_id: str,
    request: Request,
    current_user: dict = Depends(require_role(["super_admin", "business_admin", "staff"]))
):
    """Update product"""
    product = await db.products.find_one({"product_id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Check access
    if not await check_business_access(current_user, product["business_id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    
    data = await request.json()
    data["updated_at"] = datetime.now(timezone.utc)
    
    await db.products.update_one(
        {"product_id": product_id},
        {"$set": data}
    )

    # Best-effort cache bust — fire and forget, swallow all errors
    try:
        chatbot_url = os.environ.get("CHATBOT_SERVICE_URL", "http://localhost:8001")
        business_id = product["business_id"]
        async with httpx.AsyncClient(timeout=2.0) as client_http:
            await client_http.delete(f"{chatbot_url}/cache/business/{business_id}")
    except Exception:
        pass
    
    return {"message": "Product updated successfully"}

@api_router.delete("/products/{product_id}")
async def delete_product(
    product_id: str,
    current_user: dict = Depends(require_role(["super_admin", "business_admin"]))
):
    """Delete product (soft delete - set status to inactive)"""
    product = await db.products.find_one({"product_id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Check access
    if not await check_business_access(current_user, product["business_id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    
    await db.products.update_one(
        {"product_id": product_id},
        {"$set": {"status": "inactive", "updated_at": datetime.now(timezone.utc)}}
    )

    # Best-effort cache bust — fire and forget, swallow all errors
    try:
        chatbot_url = os.environ.get("CHATBOT_SERVICE_URL", "http://localhost:8001")
        business_id = product["business_id"]
        async with httpx.AsyncClient(timeout=2.0) as client_http:
            await client_http.delete(f"{chatbot_url}/cache/business/{business_id}")
    except Exception:
        pass
    
    return {"message": "Product deleted successfully"}

# ============= INVENTORY ROUTES =============
@api_router.get("/inventory")
async def list_inventory(
    business_id: str,
    low_stock: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """List inventory"""
    # Check access
    if not await check_business_access(current_user, business_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    query = {"business_id": business_id}
    if low_stock:
        query["quantity.available"] = {"$lte": 10}
    
    inventory_items = await db.inventory.find(query, {"_id": 0}).to_list(1000)
    
    # Enrich with product names
    for item in inventory_items:
        product = await db.products.find_one(
            {"product_id": item["product_id"]},
            {"_id": 0, "product_name": 1}
        )
        if product:
            item["product_name"] = product["product_name"]
    
    return {"inventory": inventory_items, "total": len(inventory_items)}

@api_router.put("/inventory/{inventory_id}")
async def update_inventory(
    inventory_id: str,
    request: Request,
    current_user: dict = Depends(require_role(["super_admin", "business_admin", "staff"]))
):
    """Update inventory (stock adjustment)"""
    inventory = await db.inventory.find_one({"inventory_id": inventory_id}, {"_id": 0})
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")
    
    # Check access
    if not await check_business_access(current_user, inventory["business_id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    
    data = await request.json()
    quantity_change = data.get("quantity_change", 0)
    movement_type = data.get("movement_type", "adjustment")
    reason = data.get("reason", "Manual adjustment")
    
    new_available = inventory["quantity"]["available"] + quantity_change
    new_total = inventory["quantity"]["total"] + quantity_change
    
    if new_available < 0:
        raise HTTPException(status_code=400, detail="Insufficient stock")
    
    # Create movement record
    movement = {
        "movement_id": f"mov_{uuid.uuid4().hex[:8]}",
        "type": movement_type,
        "quantity": quantity_change,
        "reason": reason,
        "performed_by": current_user["user_id"],
        "timestamp": datetime.now(timezone.utc)
    }
    
    update_data = {
        "quantity.available": new_available,
        "quantity.total": new_total,
        "last_updated": datetime.now(timezone.utc)
    }
    
    if data.get("location"):
        update_data["location"] = data["location"]
    
    await db.inventory.update_one(
        {"inventory_id": inventory_id},
        {
            "$set": update_data,
            "$push": {"movements": movement}
        }
    )
    
    return {
        "inventory_id": inventory_id,
        "new_quantity": {
            "available": new_available,
            "reserved": inventory["quantity"]["reserved"],
            "total": new_total
        },
        "message": "Inventory updated successfully"
    }

@api_router.get("/inventory/low-stock")
async def get_low_stock(
    business_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get low stock items"""
    if not await check_business_access(current_user, business_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    inventory_items = await db.inventory.find(
        {
            "business_id": business_id,
            "$expr": {"$lte": ["$quantity.available", "$reorder.reorder_level"]}
        },
        {"_id": 0}
    ).to_list(1000)
    
    # Enrich with product names
    for item in inventory_items:
        product = await db.products.find_one(
            {"product_id": item["product_id"]},
            {"_id": 0, "product_name": 1}
        )
        if product:
            item["product_name"] = product["product_name"]
    
    return {"low_stock_items": inventory_items, "total": len(inventory_items)}

# ============= USER MANAGEMENT ROUTES =============
@api_router.get("/users")
async def list_users(
    business_id: str = None,
    current_user: dict = Depends(require_role(["super_admin", "business_admin"]))
):
    """List users"""
    if current_user["role"] == "super_admin":
        # Super admin can see all users
        if business_id:
            users = await db.users.find(
                {"business_access.business_id": business_id},
                {"_id": 0}
            ).to_list(1000)
        else:
            users = await db.users.find({}, {"_id": 0}).to_list(1000)
    else:
        # Business admin can only see users in their business
        if not business_id:
            raise HTTPException(status_code=400, detail="business_id required for business admin")
        
        if not await check_business_access(current_user, business_id):
            raise HTTPException(status_code=403, detail="Access denied")
        
        users = await db.users.find(
            {"business_access.business_id": business_id},
            {"_id": 0}
        ).to_list(1000)
    
    return {"users": users, "total": len(users)}

@api_router.get("/users/search")
async def search_users(
    email: str = None,
    current_user: dict = Depends(require_role(["super_admin", "business_admin"]))
):
    """Search users by email"""
    if not email:
        raise HTTPException(status_code=400, detail="email query required")
    users = await db.users.find(
        {"email": {"$regex": email, "$options": "i"}},
        {"_id": 0}
    ).to_list(10)
    return {"users": users, "total": len(users)}

@api_router.post("/users/{user_id}/role")
async def assign_role(
    user_id: str,
    request: Request,
    current_user: dict = Depends(require_role(["super_admin", "business_admin"]))
):
    """Assign role to user"""
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    data = await request.json()
    business_id = data.get("business_id")
    role = data.get("role")
    
    if not business_id or not role:
        raise HTTPException(status_code=400, detail="business_id and role required")
    
    # Business admin can only assign staff or delivery_agent role in their business
    if current_user["role"] == "business_admin":
        if not await check_business_access(current_user, business_id):
            raise HTTPException(status_code=403, detail="Access denied")
        if role not in ["staff", "delivery_agent"]:
            raise HTTPException(status_code=403, detail="Can only assign staff or delivery_agent role")
    
    # Check if already has access to this business
    existing_access = None
    for access in user.get("business_access", []):
        if access["business_id"] == business_id:
            existing_access = access
            break
    
    if existing_access:
        # Update existing access
        await db.users.update_one(
            {"user_id": user_id, "business_access.business_id": business_id},
            {"$set": {"business_access.$.role": role}}
        )
    else:
        # Add new access
        await db.users.update_one(
            {"user_id": user_id},
            {
                "$push": {
                    "business_access": {
                        "business_id": business_id,
                        "role": role,
                        "assigned_at": datetime.now(timezone.utc)
                    }
                }
            }
        )
    
    return {"message": "Role assigned successfully"}


@api_router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    request: Request,
    current_user: dict = Depends(require_role(["super_admin"])),
):
    """Super admin: update global role and/or business_access"""
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    data = await request.json()
    updates = {"updated_at": datetime.now(timezone.utc)}

    if "role" in data:
        allowed = ["super_admin", "business_admin", "staff", "delivery_agent", "customer"]
        if data["role"] not in allowed:
            raise HTTPException(status_code=400, detail=f"role must be one of {allowed}")
        updates["role"] = data["role"]

    if "business_access" in data:
        if not isinstance(data["business_access"], list):
            raise HTTPException(status_code=400, detail="business_access must be a list")
        updates["business_access"] = data["business_access"]

    if len(updates) == 1:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    await db.users.update_one({"user_id": user_id}, {"$set": updates})
    updated = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    return {"message": "User updated", "user": updated}


# ============= ANALYTICS ROUTES =============
@api_router.get("/analytics/dashboard")
async def get_dashboard_stats(
    business_id: str = None,
    current_user: dict = Depends(get_current_user)
):
    """Get dashboard statistics"""
    if current_user["role"] != "super_admin":
        if not business_id:
            raise HTTPException(status_code=400, detail="business_id required")
        if not await check_business_access(current_user, business_id):
            raise HTTPException(status_code=403, detail="Access denied")
    
    if current_user["role"] == "super_admin" and not business_id:
        # System-wide stats
        total_products = await db.products.count_documents({"status": "active"})
        total_businesses = await db.businesses.count_documents({"status": "active"})
        total_users = await db.users.count_documents({})
        low_stock_items = await db.inventory.count_documents(
            {"$expr": {"$lte": ["$quantity.available", "$reorder.reorder_level"]}}
        )
        
        return {
            "system_stats": {
                "total_businesses": total_businesses,
                "total_products": total_products,
                "total_users": total_users,
                "low_stock_items": low_stock_items
            }
        }
    else:
        # Business-specific stats
        total_products = await db.products.count_documents({"business_id": business_id, "status": "active"})
        low_stock_items = await db.inventory.count_documents({
            "business_id": business_id,
            "$expr": {"$lte": ["$quantity.available", "$reorder.reorder_level"]}
        })
        out_of_stock_items = await db.inventory.count_documents({
            "business_id": business_id,
            "quantity.available": 0
        })
        
        # Calculate inventory value
        inventory_items = await db.inventory.find({"business_id": business_id}, {"_id": 0}).to_list(10000)
        total_inventory_value = 0
        for item in inventory_items:
            product = await db.products.find_one(
                {"product_id": item["product_id"]},
                {"_id": 0, "base_price": 1}
            )
            if product:
                total_inventory_value += product["base_price"] * item["quantity"]["available"]
        
        return {
            "business_stats": {
                "total_products": total_products,
                "total_inventory_value": round(total_inventory_value, 2),
                "low_stock_items": low_stock_items,
                "out_of_stock_items": out_of_stock_items
            }
        }

# Include the router in the main app
app.include_router(api_router)

# ============= E-COMMERCE ROUTES INTEGRATION =============
# Import and register e-commerce routes
import ecommerce_routes
import payment_routes
import order_routes
import custom_order_routes
import additional_routes

# Set database for all e-commerce modules
ecommerce_routes.set_db(db)
payment_routes.set_db(db)
order_routes.set_db(db)
custom_order_routes.set_db(db)
import order_management_routes
order_management_routes.set_db(db)
import sse_routes
sse_routes.set_db(db)
additional_routes.set_db(db)
import location_routes
location_routes.set_db(db)

# Include routers
app.include_router(ecommerce_routes.router)
app.include_router(payment_routes.router)
app.include_router(order_routes.router)
app.include_router(custom_order_routes.router)
app.include_router(additional_routes.reviews_router)
app.include_router(additional_routes.loyalty_router)
app.include_router(additional_routes.subscriptions_router)
app.include_router(order_management_routes.router)
app.include_router(sse_routes.router)
app.include_router(location_routes.router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

async def ensure_compound_indexes() -> None:
    """
    Create all performance-critical compound indexes idempotently.

    These indexes are the difference between a collection scan and an
    index-only scan on the most frequently hit query patterns.

    Index naming convention: {collection}_{fields}_idx
    All created with background=True so startup doesn't block traffic.
    """
    # ── products ──────────────────────────────────────────────────────────
    # Catalog list queries: filter by business + status, sort by trending
    await db.products.create_index(
        [("business_id", 1), ("status", 1), ("trending_score", -1)],
        background=True,
        name="products_business_status_trending_idx"
    )
    # Category-filtered catalog queries
    await db.products.create_index(
        [("business_id", 1), ("status", 1), ("category_id", 1)],
        background=True,
        name="products_business_status_category_idx"
    )

    # ── product_views ─────────────────────────────────────────────────────
    # Recommendation engine: fetch a user's recent views per business
    await db.product_views.create_index(
        [("user_id", 1), ("business_id", 1), ("last_viewed", -1)],
        background=True,
        name="product_views_user_business_time_idx"
    )

    # ── orders ────────────────────────────────────────────────────────────
    # Admin dashboard: orders for a business, newest first
    await db.orders.create_index(
        [("business_id", 1), ("created_at", -1)],
        background=True,
        name="orders_business_time_idx"
    )
    # My orders page + recommendation engine: a user's order history
    await db.orders.create_index(
        [("user_id", 1), ("created_at", -1)],
        background=True,
        name="orders_user_time_idx"
    )
    # Order management: filter by status within a business
    await db.orders.create_index(
        [("business_id", 1), ("order_status", 1), ("created_at", -1)],
        background=True,
        name="orders_business_status_time_idx"
    )

    # ── reviews ───────────────────────────────────────────────────────────
    # Review lookup per product (used by trending refresh aggregation)
    await db.reviews.create_index(
        [("product_id", 1)],
        background=True,
        name="reviews_product_idx"
    )

    logger.info("compound indexes created / verified")


async def _trending_refresh_loop() -> None:
    """
    Background asyncio task: refreshes trending scores every 15 minutes.

    Runs inside the same event loop as FastAPI — shares the Motor db
    connection pool with no extra overhead.

    If two ECS tasks run simultaneously, both write the same computed
    values (idempotent). No correctness issue; minor redundant work.
    The fix for multi-container is a Redis distributed lock — tracked
    as a future improvement.
    """
    import trending_refresh  # local import avoids circular dependency at module load

    # Short initial delay so the app is fully ready before first run
    await asyncio.sleep(5)

    while True:
        try:
            businesses = await db.businesses.find(
                {"status": "active"},
                {"_id": 0, "business_id": 1}
            ).to_list(100)

            for biz in businesses:
                await trending_refresh.refresh_trending_scores(db, biz["business_id"])

        except Exception:
            logger.exception("trending refresh loop error — will retry in 15 min")

        await asyncio.sleep(15 * 60)   # 15 minutes


@app.on_event("startup")
async def startup_event():
    await ensure_user_preferences_indexes()
    await ensure_compound_indexes()
    asyncio.create_task(_trending_refresh_loop())
