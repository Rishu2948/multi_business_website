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

# Import Auth_Module
from backend.auth.dependencies import get_current_user, get_optional_user
from backend.auth.rbac import require_roles, check_business_access

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
async def create_order(order_data: OrderCreate, request: Request, current_user: dict = Depends(get_current_user_with_db)):
    """Create a new order (authenticated only)"""
    user = current_user
    
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
        "user_id": user["user_id"],
        "business_id": "whisked_words",
        "items": [item.dict() for item in order_data.items],
        "delivery_info": order_data.delivery_info.dict(),
        "payment_method": order_data.payment_method,
        "payment_status": "pending",
        "payment_id": None,
        "order_status": "pending",
        "status_history": [{"status": "pending", "timestamp": datetime.now(timezone.utc).isoformat(), "updated_by": "system", "role": "system"}],
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
    await db.carts.delete_one({"user_id": user["user_id"]})
    
    # Send email for COD orders + create notification
    if order["payment_method"] == "cod":
        email = order["delivery_info"].get("email")
        if email:
            from order_management_routes import send_order_email
            import asyncio
            asyncio.create_task(send_order_email(email, order))
    
    from order_management_routes import create_notification
    import asyncio
    asyncio.create_task(create_notification(
        user["user_id"],
        "Order placed successfully",
        f"Your order #{order_id} has been placed. Total: ₹{order['total']}",
        order_id,
        "order_placed"
    ))
    
    return {"order_id": order_id, "message": "Order created successfully"}

@router.get("/my-orders")
async def get_my_orders(current_user: dict = Depends(get_current_user_with_db)):
    """Get orders for logged-in user"""
    orders = await db.orders.find(
        {"user_id": current_user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    return {"orders": orders}

@router.get("/{order_id}")
async def get_order(order_id: str, request: Request, current_user: dict = Depends(get_current_user_with_db)):
    """Get specific order details (authenticated only)"""
    order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
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

@router.put("/{order_id}/status")
async def update_order_status(
    order_id: str, 
    status: str, 
    request: Request,
    current_user: dict = Depends(get_current_user_with_db)
):
    """Update order status (Admin/Staff only with business scope)"""
    # Check role
    if current_user["role"] not in ["super_admin", "business_admin", "staff"]:
        raise HTTPException(status_code=403, detail="Access forbidden. Admin/Staff role required")
    
    order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check business access for non-super_admin
    if current_user["role"] != "super_admin":
        if not await check_business_access(current_user, order.get("business_id", "whisked_words")):
            raise HTTPException(status_code=403, detail="Access denied to this business")
    
    await db.orders.update_one(
        {"order_id": order_id},
        {"$set": {"order_status": status, "updated_at": datetime.now(timezone.utc)}}
    )
    
    # Emit audit event for privileged action
    from backend.auth.audit import write_audit_event, AuditEventType
    await write_audit_event(
        db,
        event_type=AuditEventType.PRIVILEGED_ACTION,
        user_id=current_user["user_id"],
        business_id=order.get("business_id"),
        ip_address=request.client.host if request.client else None,
        details={
            "action": "update_order_status",
            "order_id": order_id,
            "old_status": order.get("order_status"),
            "new_status": status
        },
        success=True
    )
    
    return {"message": "Order status updated"}
