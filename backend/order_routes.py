from fastapi import APIRouter, HTTPException, Request, Depends
from datetime import datetime, timezone
import uuid

router = APIRouter(prefix="/api/orders")

# Database will be set from main server
db = None

def set_db(database):
    global db
    db = database

# Import models
from ecommerce_models import OrderCreate, Order

# Helper to get optional user
async def get_optional_user(request: Request):
    """Get user if authenticated, return None otherwise"""
    try:
        session_token = request.cookies.get("session_token") or request.headers.get("authorization", "").replace("Bearer ", "")
        if not session_token:
            return None
        
        session = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
        if not session:
            return None
        
        expires_at = session["expires_at"]
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        if expires_at < datetime.now(timezone.utc):
            return None
        
        user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
        return user
    except:
        return None

@router.post("/create")
async def create_order(order_data: OrderCreate, request: Request):
    """Create a new order"""
    user = await get_optional_user(request)
    
    # Validate stock availability
    for item in order_data.items:
        query = {"product_id": item.product_id}
        if item.variant_id:
            query["variant_id"] = item.variant_id
        else:
            query["variant_id"] = None
        
        inventory = await db.inventory.find_one(query, {"_id": 0})
        
        # Fallback: try without variant_id filter if no match
        if not inventory:
            inventory = await db.inventory.find_one(
                {"product_id": item.product_id},
                {"_id": 0}
            )
        
        if not inventory or inventory["quantity"]["available"] < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for {item.product_name}"
            )
    
    # Create order
    order_id = f"ord_{uuid.uuid4().hex[:12]}"
    order = {
        "order_id": order_id,
        "user_id": user["user_id"] if user else None,
        "business_id": "whisked_words",
        "items": [item.dict() for item in order_data.items],
        "delivery_info": order_data.delivery_info.dict(),
        "payment_method": order_data.payment_method,
        "payment_status": "pending",
        "payment_id": None,
        "order_status": "pending",
        "subtotal": order_data.subtotal,
        "tax": order_data.tax,
        "delivery_charge": order_data.delivery_charge,
        "total": order_data.total,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    await db.orders.insert_one(order)
    
    # Reserve inventory
    for item in order_data.items:
        inv_query = {"product_id": item.product_id}
        if item.variant_id:
            inv_query["variant_id"] = item.variant_id
        else:
            inv_query["variant_id"] = None
        
        # Try exact match first, then fallback
        result = await db.inventory.update_one(
            inv_query,
            {
                "$inc": {
                    "quantity.available": -item.quantity,
                    "quantity.reserved": item.quantity
                }
            }
        )
        if result.modified_count == 0:
            await db.inventory.update_one(
                {"product_id": item.product_id},
                {
                    "$inc": {
                        "quantity.available": -item.quantity,
                        "quantity.reserved": item.quantity
                    }
                }
            )
    
    # Clear cart
    if user:
        await db.carts.delete_one({"user_id": user["user_id"]})
    else:
        session_id = request.cookies.get("guest_session_id")
        if session_id:
            await db.carts.delete_one({"session_id": session_id})
    
    return {"order_id": order_id, "message": "Order created successfully"}

@router.get("/my-orders")
async def get_my_orders(request: Request):
    """Get orders for logged-in user"""
    user = await get_optional_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    orders = await db.orders.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    return {"orders": orders}

@router.get("/{order_id}")
async def get_order(order_id: str, request: Request):
    """Get specific order details"""
    order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check if user owns this order (for logged-in users)
    user = await get_optional_user(request)
    if user and order.get("user_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return order

@router.put("/{order_id}/status")
async def update_order_status(order_id: str, status: str, request: Request):
    """Update order status (Admin only)"""
    # This should have admin auth, but for now we'll allow it
    order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    await db.orders.update_one(
        {"order_id": order_id},
        {"$set": {"order_status": status, "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {"message": "Order status updated"}
