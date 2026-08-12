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

# Import Auth_Module
from backend.auth.dependencies import get_current_user, get_optional_user
from backend.auth.rbac import check_business_access

# Override get_current_user to use local db
async def get_current_user_with_db(request: Request):
    """Get current user using local db instance"""
    from backend.auth.dependencies import extract_token
    from backend.auth.tokens import TokenManager
    from backend.auth.sessions import update_last_seen
    
    token = await extract_token(request)
    
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Try as JWT access token first
    try:
        token_manager = TokenManager(db)
        payload = token_manager.verify_access_token(token)
        
        # Load user from DB for authorization
        user = await db.users.find_one(
            {"user_id": payload["sub"]},
            {"_id": 0}
        )
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Update last seen
        await update_last_seen(db, payload["sid"])
        
        return user
    
    except HTTPException:
        # If JWT fails, try legacy session if enabled
        from backend.auth.tokens import validate_legacy_session
        user = await validate_legacy_session(db, token)
        
        if user:
            return user
        
        raise HTTPException(status_code=401, detail="Invalid or expired credentials")

# Override get_optional_user to use local db
async def get_optional_user_with_db(request: Request):
    """Get user if authenticated, None otherwise"""
    try:
        return await get_current_user_with_db(request)
    except HTTPException:
        return None

@router.post("/create")
async def create_custom_order(custom_order: CustomOrderCreate, request: Request, current_user: dict = Depends(get_current_user_with_db)):
    """Create custom cake order (authenticated only)"""
    user = current_user
    
    # Get product
    product = await db.products.find_one({"product_id": custom_order.product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Calculate base price (will be adjusted by admin)
    base_price = product["base_price"]
    
    custom_order_id = f"custom_{uuid.uuid4().hex[:12]}"
    order_data = {
        "custom_order_id": custom_order_id,
        "user_id": user["user_id"],
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
async def get_my_custom_orders(current_user: dict = Depends(get_current_user_with_db)):
    """Get user's custom orders"""
    orders = await db.custom_orders.find(
        {"user_id": current_user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    return {"orders": orders}

@router.get("/admin/all")
async def get_all_custom_orders(current_user: dict = Depends(get_current_user_with_db)):
    """Get all custom orders for admin"""
    # Check role
    if current_user["role"] not in ["super_admin", "business_admin", "staff"]:
        raise HTTPException(status_code=403, detail="Access forbidden. Admin/Staff role required")
    
    orders = await db.custom_orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    
    # Filter by business access for non-super_admin
    if current_user["role"] != "super_admin":
        business_ids = [access["business_id"] for access in current_user.get("business_access", [])]
        orders = [order for order in orders if order.get("business_id") in business_ids]
    
    return {"orders": orders}

@router.get("/{custom_order_id}")
async def get_custom_order(custom_order_id: str, current_user: dict = Depends(get_current_user_with_db)):
    """Get custom order details"""
    order = await db.custom_orders.find_one({"custom_order_id": custom_order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Custom order not found")
    
    # Check if user owns this order or has admin access
    if current_user["role"] == "super_admin":
        return order
    
    if order.get("user_id") == current_user["user_id"]:
        return order
    
    # Check business access for non-owners
    if current_user["role"] in ["business_admin", "staff"]:
        if await check_business_access(current_user, order.get("business_id", "whisked_words")):
            return order
    
    raise HTTPException(status_code=403, detail="Access denied")

@router.put("/{custom_order_id}/status")
async def update_custom_order_status(
    custom_order_id: str, 
    request: Request,
    current_user: dict = Depends(get_current_user_with_db)
):
    """Update custom order status and price (Admin/Staff only)"""
    # Check role
    if current_user["role"] not in ["super_admin", "business_admin", "staff"]:
        raise HTTPException(status_code=403, detail="Access forbidden. Admin/Staff role required")
    
    data = await request.json()
    status = data.get("status")
    price = data.get("price")
    admin_notes = data.get("admin_notes")
    
    valid_statuses = ["pending_quote", "quoted", "confirmed", "rejected"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    # Check business access
    order = await db.custom_orders.find_one({"custom_order_id": custom_order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Custom order not found")
    
    if current_user["role"] != "super_admin":
        if not await check_business_access(current_user, order.get("business_id", "whisked_words")):
            raise HTTPException(status_code=403, detail="Access denied to this business")
    
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
    
    # Emit audit event for privileged action
    from backend.auth.audit import write_audit_event, AuditEventType
    await write_audit_event(
        db,
        event_type=AuditEventType.PRIVILEGED_ACTION,
        user_id=current_user["user_id"],
        business_id=order.get("business_id"),
        ip_address=request.client.host if request.client else None,
        details={
            "action": "update_custom_order_status",
            "custom_order_id": custom_order_id,
            "updates": list(update_data.keys())
        },
        success=True
    )
    
    return {"message": "Custom order updated"}
