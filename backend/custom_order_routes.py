from fastapi import APIRouter, HTTPException, Request
from datetime import datetime, timezone
import uuid

router = APIRouter(prefix="/api/custom-orders")

# Database will be set from main server
db = None

def set_db(database):
    global db
    db = database

from ecommerce_models import CustomOrderCreate

async def get_optional_user(request: Request):
    """Get user if authenticated"""
    try:
        session_token = request.cookies.get("session_token") or request.headers.get("authorization", "").replace("Bearer ", "")
        if not session_token:
            return None
        
        session = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
        if not session:
            return None
        
        user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
        return user
    except:
        return None

@router.post("/create")
async def create_custom_order(custom_order: CustomOrderCreate, request: Request):
    """Create custom cake order"""
    user = await get_optional_user(request)
    
    # Get product
    product = await db.products.find_one({"product_id": custom_order.product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Calculate base price (will be adjusted by admin)
    base_price = product["base_price"]
    
    custom_order_id = f"custom_{uuid.uuid4().hex[:12]}"
    order_data = {
        "custom_order_id": custom_order_id,
        "user_id": user["user_id"] if user else None,
        "business_id": "whisked_words",
        "product_id": custom_order.product_id,
        "cake_type": custom_order.cake_type,
        "weight": custom_order.weight,
        "flavor": custom_order.flavor,
        "shape": custom_order.shape,
        "message_on_cake": custom_order.message_on_cake,
        "special_instructions": custom_order.special_instructions,
        "image_reference_url": custom_order.image_reference_url,
        "delivery_date": custom_order.delivery_date,
        "delivery_time": custom_order.delivery_time,
        "delivery_info": custom_order.delivery_info.dict(),
        "price": base_price,
        "status": "pending_quote",
        "admin_notes": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    await db.custom_orders.insert_one(order_data)
    
    return {"custom_order_id": custom_order_id, "message": "Custom order request submitted"}

@router.get("/my-orders")
async def get_my_custom_orders(request: Request):
    """Get user's custom orders"""
    user = await get_optional_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    orders = await db.custom_orders.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    return {"orders": orders}

@router.get("/admin/all")
async def get_all_custom_orders():
    """Get all custom orders for admin"""
    orders = await db.custom_orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return {"orders": orders}

@router.get("/{custom_order_id}")
async def get_custom_order(custom_order_id: str):
    """Get custom order details"""
    order = await db.custom_orders.find_one({"custom_order_id": custom_order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Custom order not found")
    
    return order

@router.put("/{custom_order_id}/status")
async def update_custom_order_status(custom_order_id: str, request: Request):
    """Update custom order status and price"""
    data = await request.json()
    status = data.get("status")
    price = data.get("price")
    admin_notes = data.get("admin_notes")
    
    valid_statuses = ["pending_quote", "quoted", "confirmed", "rejected"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    update_data = {"status": status, "updated_at": datetime.now(timezone.utc)}
    if price is not None:
        update_data["price"] = price
    if admin_notes is not None:
        update_data["admin_notes"] = admin_notes
    
    result = await db.custom_orders.update_one(
        {"custom_order_id": custom_order_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Custom order not found")
    
    return {"message": "Custom order updated"}
