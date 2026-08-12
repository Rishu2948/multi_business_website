from fastapi import APIRouter, HTTPException, Request
from datetime import datetime, timezone
import uuid

# Reviews Router
reviews_router = APIRouter(prefix="/api/reviews")

# Loyalty Router
loyalty_router = APIRouter(prefix="/api/loyalty")

# Subscriptions Router
subscriptions_router = APIRouter(prefix="/api/subscriptions")

# Database will be set from main server
db = None

def set_db(database):
    global db
    db = database

from ecommerce_models import ReviewCreate, SubscriptionCreate

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
        if not session:
            return None
        
        user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
        return user
    except:
        return None

# ============= REVIEW ROUTES =============
@reviews_router.post("/create")
async def create_review(review: ReviewCreate, request: Request):
    """Create product review"""
    user = await get_optional_user_with_db(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Check if user already reviewed this product
    existing_review = await db.reviews.find_one(
        {"product_id": review.product_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    if existing_review:
        raise HTTPException(status_code=400, detail="You have already reviewed this product")
    
    review_id = f"rev_{uuid.uuid4().hex[:12]}"
    review_data = {
        "review_id": review_id,
        "product_id": review.product_id,
        "user_id": user["user_id"],
        "user_name": user["name"],
        "rating": review.rating,
        "comment": review.comment,
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.reviews.insert_one(review_data)
    
    # Award 50 loyalty points for review
    await db.loyalty_points.update_one(
        {"user_id": user["user_id"]},
        {
            "$inc": {"points": 50, "total_earned": 50},
            "$setOnInsert": {"user_id": user["user_id"], "tier": "bronze", "total_redeemed": 0}
        },
        upsert=True
    )
    
    points_txn = {
        "transaction_id": f"pts_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "points": 50,
        "type": "earned",
        "reason": "Product review",
        "order_id": None,
        "created_at": datetime.now(timezone.utc)
    }
    await db.points_transactions.insert_one(points_txn)
    
    return {"review_id": review_id, "message": "Review submitted successfully", "points_earned": 50}

@reviews_router.get("/product/{product_id}")
async def get_product_reviews(product_id: str):
    """Get all reviews for a product"""
    reviews = await db.reviews.find(
        {"product_id": product_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # Calculate average rating
    if reviews:
        avg_rating = sum(r["rating"] for r in reviews) / len(reviews)
    else:
        avg_rating = 0
    
    return {
        "reviews": reviews,
        "total": len(reviews),
        "average_rating": round(avg_rating, 1)
    }

# ============= LOYALTY ROUTES =============
@loyalty_router.get("/points")
async def get_loyalty_points(request: Request):
    """Get user's loyalty points"""
    user = await get_optional_user_with_db(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    loyalty = await db.loyalty_points.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not loyalty:
        loyalty = {
            "user_id": user["user_id"],
            "points": 0,
            "total_earned": 0,
            "total_redeemed": 0,
            "tier": "bronze"
        }
    
    # Get tier based on total earned
    total_earned = loyalty["total_earned"]
    if total_earned >= 10000:
        tier = "platinum"
    elif total_earned >= 5000:
        tier = "gold"
    elif total_earned >= 2000:
        tier = "silver"
    else:
        tier = "bronze"
    
    loyalty["tier"] = tier
    await db.loyalty_points.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"tier": tier}},
        upsert=True
    )
    
    return loyalty

@loyalty_router.get("/transactions")
async def get_points_transactions(request: Request):
    """Get user's points transaction history"""
    user = await get_optional_user_with_db(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    transactions = await db.points_transactions.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    return {"transactions": transactions}

# ============= SUBSCRIPTION ROUTES =============
@subscriptions_router.post("/create")
async def create_subscription(subscription: SubscriptionCreate, request: Request):
    """Create product subscription"""
    user = await get_optional_user_with_db(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    subscription_id = f"sub_{uuid.uuid4().hex[:12]}"
    subscription_data = {
        "subscription_id": subscription_id,
        "user_id": user["user_id"],
        "business_id": "whisked_words",
        "product_ids": subscription.product_ids,
        "frequency": subscription.frequency,
        "delivery_days": subscription.delivery_days,
        "delivery_time": subscription.delivery_time,
        "start_date": subscription.start_date,
        "next_delivery": subscription.start_date,  # Will be calculated based on frequency
        "delivery_info": subscription.delivery_info.dict(),
        "status": "active",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    await db.subscriptions.insert_one(subscription_data)
    
    return {"subscription_id": subscription_id, "message": "Subscription created successfully"}

@subscriptions_router.get("/my-subscriptions")
async def get_my_subscriptions(request: Request):
    """Get user's subscriptions"""
    user = await get_optional_user_with_db(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    subscriptions = await db.subscriptions.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).to_list(100)
    
    return {"subscriptions": subscriptions}

@subscriptions_router.put("/{subscription_id}/pause")
async def pause_subscription(subscription_id: str, request: Request):
    """Pause subscription"""
    user = await get_optional_user_with_db(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    subscription = await db.subscriptions.find_one(
        {"subscription_id": subscription_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    await db.subscriptions.update_one(
        {"subscription_id": subscription_id},
        {"$set": {"status": "paused", "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {"message": "Subscription paused"}

@subscriptions_router.put("/{subscription_id}/resume")
async def resume_subscription(subscription_id: str, request: Request):
    """Resume subscription"""
    user = await get_optional_user_with_db(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    await db.subscriptions.update_one(
        {"subscription_id": subscription_id, "user_id": user["user_id"]},
        {"$set": {"status": "active", "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {"message": "Subscription resumed"}

@subscriptions_router.delete("/{subscription_id}")
async def cancel_subscription(subscription_id: str, request: Request):
    """Cancel subscription"""
    user = await get_optional_user_with_db(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    await db.subscriptions.update_one(
        {"subscription_id": subscription_id, "user_id": user["user_id"]},
        {"$set": {"status": "cancelled", "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {"message": "Subscription cancelled"}
