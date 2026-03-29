from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, Response
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
import uuid
import httpx

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

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
    expires_at = session["expires_at"]
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

# ============= AUTH ROUTES =============
@api_router.post("/auth/session")
async def create_session(request: Request, response: Response):
    """Exchange session_id for session_token after OAuth"""
    body = await request.json()
    session_id = body.get("session_id")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    
    # Call Emergent OAuth API
    async with httpx.AsyncClient() as http_client:
        try:
            emergent_response = await http_client.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": session_id},
                timeout=10.0
            )
            
            if emergent_response.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid session_id")
            
            oauth_data = emergent_response.json()
            
        except httpx.RequestError as e:
            logging.error(f"OAuth request failed: {e}")
            raise HTTPException(status_code=500, detail="Authentication service unavailable")
    
    # Check if user exists
    user = await db.users.find_one({"email": oauth_data["email"]}, {"_id": 0})
    
    if not user:
        # Create new user with customer role by default
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user = {
            "user_id": user_id,
            "email": oauth_data["email"],
            "name": oauth_data["name"],
            "picture": oauth_data.get("picture", ""),
            "role": "customer",
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
        "session_token": oauth_data["session_token"],
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc),
        "ip_address": request.client.host,
        "user_agent": request.headers.get("user-agent", "")
    }
    await db.user_sessions.insert_one(session_data)
    
    # Set httpOnly cookie
    response.set_cookie(
        key="session_token",
        value=oauth_data["session_token"],
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7*24*60*60
    )
    
    return {
        "user": {
            "user_id": user["user_id"],
            "email": user["email"],
            "name": user["name"],
            "picture": user["picture"],
            "role": user["role"],
            "business_access": user.get("business_access", [])
        },
        "message": "Login successful"
    }

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
        "status": current_user["status"]
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
    
    # Business admin can only assign staff role in their business
    if current_user["role"] == "business_admin":
        if not await check_business_access(current_user, business_id):
            raise HTTPException(status_code=403, detail="Access denied")
        if role not in ["staff"]:
            raise HTTPException(status_code=403, detail="Can only assign staff role")
    
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

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
