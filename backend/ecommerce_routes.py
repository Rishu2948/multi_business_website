from fastapi import APIRouter, HTTPException, Request, Depends, Response
from datetime import datetime, timezone, timedelta
import uuid
import os
from motor.motor_asyncio import AsyncIOMotorClient
from ecommerce_models import (
    CartCreate, CartUpdate, Cart, CartItem,
    OrderCreate, Order, OrderItem,
    CustomOrderCreate, CustomOrder,
    ReviewCreate, Review,
    LoyaltyPoints, PointsTransaction,
    SubscriptionCreate, Subscription,
    PaymentTransaction
)
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest, CheckoutSessionResponse

# Get database connection (will be set from main server.py)
db = None

def set_db(database):
    global db
    db = database

router = APIRouter(prefix="/api/ecommerce")

# Helper function to get current user (optional, for guest checkout)
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

# ============= CART ROUTES =============
@router.post("/cart/add")
async def add_to_cart(item: CartCreate, request: Request):
    """Add item to cart (works for both guest and logged-in users)"""
    user = await get_optional_user(request)
    
    # Get or create session ID for guest users
    session_id = request.cookies.get("guest_session_id")
    if not session_id:
        session_id = f"guest_{uuid.uuid4().hex[:16]}"
    
    # Get product details
    product = await db.products.find_one({"product_id": item.product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Find cart
    if user:
        cart = await db.carts.find_one({"user_id": user["user_id"]}, {"_id": 0})
    else:
        cart = await db.carts.find_one({"session_id": session_id}, {"_id": 0})
    
    # Create cart item
    cart_item = {
        "product_id": item.product_id,
        "variant_id": item.variant_id,
        "product_name": product["product_name"],
        "quantity": item.quantity,
        "price": product["base_price"],
        "image_url": product["images"][0]["url"] if product.get("images") else None,
        "attributes": product.get("attributes", {})
    }
    
    if cart:
        # Update existing cart
        existing_item = None
        for idx, ci in enumerate(cart["items"]):
            if ci["product_id"] == item.product_id and ci.get("variant_id") == item.variant_id:
                existing_item = idx
                break
        
        if existing_item is not None:
            # Update quantity
            cart["items"][existing_item]["quantity"] += item.quantity
        else:
            # Add new item
            cart["items"].append(cart_item)
        
        # Recalculate total
        cart["total_amount"] = sum(ci["price"] * ci["quantity"] for ci in cart["items"])
        cart["updated_at"] = datetime.now(timezone.utc)
        
        await db.carts.update_one(
            {"cart_id": cart["cart_id"]},
            {"$set": {"items": cart["items"], "total_amount": cart["total_amount"], "updated_at": cart["updated_at"]}}
        )
    else:
        # Create new cart
        cart_id = f"cart_{uuid.uuid4().hex[:12]}"
        cart = {
            "cart_id": cart_id,
            "user_id": user["user_id"] if user else None,
            "session_id": session_id if not user else None,
            "items": [cart_item],
            "total_amount": cart_item["price"] * cart_item["quantity"],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        await db.carts.insert_one(cart)
    
    response = Response(content=str({"message": "Item added to cart", "cart_id": cart["cart_id"]}), media_type="application/json")
    if not user:
        response.set_cookie(key="guest_session_id", value=session_id, max_age=30*24*60*60)  # 30 days
    
    return {"message": "Item added to cart", "cart_id": cart["cart_id"]}

@router.get("/cart")
async def get_cart(request: Request):
    """Get current cart"""
    user = await get_optional_user(request)
    session_id = request.cookies.get("guest_session_id")
    
    if user:
        cart = await db.carts.find_one({"user_id": user["user_id"]}, {"_id": 0})
    elif session_id:
        cart = await db.carts.find_one({"session_id": session_id}, {"_id": 0})
    else:
        return {"items": [], "total_amount": 0}
    
    if not cart:
        return {"items": [], "total_amount": 0}
    
    return cart

@router.put("/cart/{product_id}")
async def update_cart_item(product_id: str, update: CartUpdate, request: Request, variant_id: str = None):
    """Update item quantity in cart"""
    user = await get_optional_user(request)
    session_id = request.cookies.get("guest_session_id")
    
    if user:
        cart = await db.carts.find_one({"user_id": user["user_id"]}, {"_id": 0})
    elif session_id:
        cart = await db.carts.find_one({"session_id": session_id}, {"_id": 0})
    else:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    # Find and update item
    for item in cart["items"]:
        if item["product_id"] == product_id and item.get("variant_id") == variant_id:
            item["quantity"] = update.quantity
            break
    
    # Recalculate total
    cart["total_amount"] = sum(item["price"] * item["quantity"] for item in cart["items"])
    cart["updated_at"] = datetime.now(timezone.utc)
    
    await db.carts.update_one(
        {"cart_id": cart["cart_id"]},
        {"$set": {"items": cart["items"], "total_amount": cart["total_amount"], "updated_at": cart["updated_at"]}}
    )
    
    return {"message": "Cart updated", "cart": cart}

@router.delete("/cart/{product_id}")
async def remove_from_cart(product_id: str, request: Request, variant_id: str = None):
    """Remove item from cart"""
    user = await get_optional_user(request)
    session_id = request.cookies.get("guest_session_id")
    
    if user:
        cart = await db.carts.find_one({"user_id": user["user_id"]}, {"_id": 0})
    elif session_id:
        cart = await db.carts.find_one({"session_id": session_id}, {"_id": 0})
    else:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    # Remove item
    cart["items"] = [item for item in cart["items"] 
                      if not (item["product_id"] == product_id and item.get("variant_id") == variant_id)]
    
    # Recalculate total
    cart["total_amount"] = sum(item["price"] * item["quantity"] for item in cart["items"])
    cart["updated_at"] = datetime.now(timezone.utc)
    
    await db.carts.update_one(
        {"cart_id": cart["cart_id"]},
        {"$set": {"items": cart["items"], "total_amount": cart["total_amount"], "updated_at": cart["updated_at"]}}
    )
    
    return {"message": "Item removed from cart"}

@router.delete("/cart")
async def clear_cart(request: Request):
    """Clear entire cart"""
    user = await get_optional_user(request)
    session_id = request.cookies.get("guest_session_id")
    
    if user:
        await db.carts.delete_one({"user_id": user["user_id"]})
    elif session_id:
        await db.carts.delete_one({"session_id": session_id})
    
    return {"message": "Cart cleared"}
