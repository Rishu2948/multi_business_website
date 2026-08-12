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


# Validate production security configuration
def validate_production_config():
    """Validate that production environment has secure configuration."""
    if _is_production():
        errors = []
        
        # Check for insecure webhook verification skip
        if os.environ.get("WEBHOOK_SKIP_VERIFY", "false").lower() == "true":
            errors.append("WEBHOOK_SKIP_VERIFY cannot be true in production")
        
        # Check for MFA enforcement without encryption key
        if os.environ.get("MFA_ENFORCE_FOR_ADMINS", "false").lower() == "true":
            if not os.environ.get("MFA_ENCRYPTION_KEY"):
                errors.append("MFA_ENCRYPTION_KEY is required when MFA_ENFORCE_FOR_ADMINS is true")
        
        # Check for missing JWT secret
        if not os.environ.get("JWT_SECRET"):
            errors.append("JWT_SECRET is required in production")
        
        # Check for missing webhook secret
        if not os.environ.get("RAZORPAY_WEBHOOK_SECRET"):
            errors.append("RAZORPAY_WEBHOOK_SECRET should be set in production for payment security")
        
        if errors:
            error_msg = "Production security configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
            logger.error(error_msg)
            raise RuntimeError(error_msg)


@app.on_event("startup")
async def startup_event():
    """Run startup tasks including security validation."""
    validate_production_config()
    
    # Ensure Auth_Module indexes exist
    try:
        from backend.auth.sessions import ensure_session_indexes
        from backend.auth.audit import ensure_audit_indexes
        await ensure_session_indexes(db)
        await ensure_audit_indexes(db)
        logger.info("Auth_Module indexes created/verified")
    except Exception as e:
        logger.warning(f"Failed to create Auth_Module indexes: {e}")
    
    # Add security headers middleware
    try:
        from backend.auth.headers import SecurityHeadersMiddleware
        from backend.auth.csrf import CSRFProtection, get_allowed_origins
        from starlette.middleware.base import BaseHTTPMiddleware
        
        # Add security headers middleware
        app.add_middleware(SecurityHeadersMiddleware)
        
        # Add CSRF protection middleware
        allowed_origins = get_allowed_origins()
        csrf_middleware = CSRFProtection(allowed_origins)
        app.add_middleware(BaseHTTPMiddleware, dispatch=csrf_middleware)
        
        logger.info("Security middleware added")
    except Exception as e:
        logger.warning(f"Failed to add security middleware: {e}")


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
    """Verify Google ID token and create session with JWT access + refresh tokens"""
    from backend.auth.tokens import TokenManager
    from backend.auth.audit import write_audit_event, AuditEventType
    from backend.auth.mfa import should_enforce_mfa, is_user_mfa_enrolled
    from backend.auth.rbac import is_privileged_role
    
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
        
        # Check if MFA should be enforced for privileged users
        from backend.auth.mfa import should_enforce_mfa, is_user_mfa_enrolled
        from backend.auth.rbac import is_privileged_role
        
        if should_enforce_mfa(user["role"]) and not is_user_mfa_enrolled(user):
            # Return MFA enrollment required
            await write_audit_event(
                db,
                event_type=AuditEventType.LOGIN_FAILURE,
                user_id=user["user_id"],
                ip_address=request.client.host if request.client else None,
                details={"reason": "mfa_enrollment_required"},
                success=False
            )
            return {
                "message": "MFA enrollment required",
                "mfa_required": True,
                "mfa_enrollment": True
            }
        
        if should_enforce_mfa(user["role"]) and is_user_mfa_enrolled(user):
            # Return MFA verification required (create pending session)
            from backend.auth.sessions import create_session
            device_info = {
                "ip_address": request.client.host,
                "user_agent": request.headers.get("user-agent", "")
            }
            session_id, refresh_token = await create_session(
                db,
                user["user_id"],
                604800,  # 7 days
                device_info,
                max_sessions=5
            )
            
            await write_audit_event(
                db,
                event_type=AuditEventType.LOGIN_FAILURE,
                user_id=user["user_id"],
                ip_address=request.client.host if request.client else None,
                details={"reason": "mfa_verification_required"},
                success=False
            )
            
            return {
                "message": "MFA verification required",
                "mfa_required": True,
                "mfa_enrollment": False,
                "session_id": session_id,
                "user": user
            }
        
        # Create session using Auth_Module TokenManager
        token_manager = TokenManager(db)
        device_info = {
            "ip_address": request.client.host,
            "user_agent": request.headers.get("user-agent", "")
        }
        
        session_id, refresh_token = await token_manager.mint_refresh_token(
            user["user_id"],
            device_info,
            max_sessions=5
        )
        
        # Mint access token
        access_token = token_manager.mint_access_token(user["user_id"], session_id)
        
        # Set refresh token as HttpOnly cookie
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=_is_production(),
            samesite="none" if _is_production() else "lax",
            path="/",
            max_age=7 * 24 * 60 * 60,  # 7 days
        )
        
        # Emit audit event for successful login
        await write_audit_event(
            db,
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id=user["user_id"],
            ip_address=request.client.host if request.client else None,
            details={"method": "google_oauth"},
            success=True
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

        # Get Prime memberships for user
        from prime.access import get_enabled_features
        prime_memberships = []
        try:
            memberships_cursor = db.prime_memberships.find(
                {"user_id": user["user_id"], "status": "active", "expires_at": {"$gt": datetime.now(timezone.utc)}},
                {"_id": 0}
            )
            memberships = await memberships_cursor.to_list(length=None)

            for membership in memberships:
                enabled_features = await get_enabled_features(db, membership["business_id"])
                prime_memberships.append({
                    "business_id": membership["business_id"],
                    "status": membership["status"],
                    "expires_at": membership["expires_at"],
                    "enabled_features": enabled_features,
                })
        except Exception as e:
            logger.warning(f"Error fetching prime memberships for {user['user_id']}: {e}")

        return {
            "access_token": access_token,
            "user": {
                "user_id": user["user_id"],
                "email": user["email"],
                "name": user["name"],
                "picture": user["picture"],
                "role": user["role"],
                "business_access": user.get("business_access", []),
                "is_prime": user.get("is_prime", False),
                "prime_memberships": prime_memberships
            },
            "recommendations": recommended_product_ids,
            "preference_summary": preference_vector,
            "message": "Login successful"
        }
    except ValueError as e:
        logger.warning("Invalid Google token: %s", e)
        await write_audit_event(
            db,
            event_type=AuditEventType.LOGIN_FAILURE,
            ip_address=request.client.host if request.client else None,
            details={"reason": "invalid_google_token"},
            success=False
        )
        raise HTTPException(status_code=401, detail="Invalid Google token")
    except Exception as e:
        logger.exception("Google login failed")
        await write_audit_event(
            db,
            event_type=AuditEventType.LOGIN_FAILURE,
            ip_address=request.client.host if request.client else None,
            details={"reason": "internal_error"},
            success=False
        )
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    """Refresh access token using refresh token from cookie"""
    from backend.auth.tokens import TokenManager
    from backend.auth.audit import write_audit_event, AuditEventType
    
    # Get refresh token from cookie
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token required")
    
    try:
        token_manager = TokenManager(db)
        device_info = {
            "ip_address": request.client.host,
            "user_agent": request.headers.get("user-agent", "")
        }
        
        # Rotate refresh token and get new access token
        session_id, new_refresh_token, access_token = await token_manager.rotate_refresh_token(
            refresh_token,
            device_info
        )
        
        # Set new refresh token cookie
        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            httponly=True,
            secure=_is_production(),
            samesite="none" if _is_production() else "lax",
            path="/",
            max_age=7 * 24 * 60 * 60,  # 7 days
        )
        
        # Emit audit event
        await write_audit_event(
            db,
            event_type=AuditEventType.TOKEN_REFRESH,
            ip_address=request.client.host if request.client else None,
            success=True
        )
        
        return {"access_token": access_token}
    
    except HTTPException as e:
        await write_audit_event(
            db,
            event_type=AuditEventType.TOKEN_REFRESH,
            ip_address=request.client.host if request.client else None,
            details={"reason": "invalid_refresh_token"},
            success=False
        )
        raise
    except Exception as e:
        logger.exception("Token refresh failed")
        await write_audit_event(
            db,
            event_type=AuditEventType.TOKEN_REFRESH,
            ip_address=request.client.host if request.client else None,
            details={"reason": "internal_error"},
            success=False
        )
        raise HTTPException(status_code=500, detail="Token refresh failed")


@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    """Logout user by revoking session and clearing cookies"""
    from backend.auth.tokens import TokenManager
    from backend.auth.audit import write_audit_event, AuditEventType
    
    # Get refresh token from cookie
    refresh_token = request.cookies.get("refresh_token")
    
    try:
        if refresh_token:
            token_manager = TokenManager(db)
            session = await token_manager.verify_refresh_token(refresh_token)
            if session:
                # Revoke session
                from backend.auth.sessions import revoke_session
                await revoke_session(db, session.session_id)
        
        # Clear cookies
        response.delete_cookie(
            key="refresh_token",
            path="/",
            secure=_is_production(),
            samesite="none" if _is_production() else "lax"
        )
        response.delete_cookie(
            key="session_token",
            path="/",
            secure=_is_production(),
            samesite="none" if _is_production() else "lax"
        )
        
        # Emit audit event
        await write_audit_event(
            db,
            event_type=AuditEventType.LOGOUT,
            ip_address=request.client.host if request.client else None,
            success=True
        )
        
        return {"message": "Logged out successfully"}
    
    except Exception as e:
        logger.exception("Logout failed")
        # Still clear cookies even if revocation fails
        response.delete_cookie(
            key="refresh_token",
            path="/",
            secure=_is_production(),
            samesite="none" if _is_production() else "lax"
        )
        response.delete_cookie(
            key="session_token",
            path="/",
            secure=_is_production(),
            samesite="none" if _is_production() else "lax"
        )
        return {"message": "Logged out successfully"}

@api_router.get("/auth/me")
async def get_current_user_info(request: Request):
    """Get current authenticated user details using Auth_Module"""
    from backend.auth.dependencies import get_current_user_with_db
    
    # Override get_current_user to use local db
    async def get_current_user_with_db_local(request: Request):
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
    
    current_user = await get_current_user_with_db_local(request)
    # Get Prime memberships for user
    from prime.access import get_enabled_features
    prime_memberships = []
    try:
        memberships_cursor = db.prime_memberships.find(
            {"user_id": current_user["user_id"], "status": "active", "expires_at": {"$gt": datetime.now(timezone.utc)}},
            {"_id": 0}
        )
        memberships = await memberships_cursor.to_list(length=None)

        for membership in memberships:
            enabled_features = await get_enabled_features(db, membership["business_id"])
            prime_memberships.append({
                "business_id": membership["business_id"],
                "status": membership["status"],
                "expires_at": membership["expires_at"],
                "enabled_features": enabled_features,
            })
    except Exception as e:
        logger.warning(f"Error fetching prime memberships for {current_user['user_id']}: {e}")

    return {
        "user_id": current_user["user_id"],
        "email": current_user["email"],
        "name": current_user["name"],
        "picture": current_user["picture"],
        "role": current_user["role"],
        "business_access": current_user.get("business_access", []),
        "status": current_user["status"],
        "is_prime": current_user.get("is_prime", False),
        "prime_memberships": prime_memberships
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
    subcategory_id: str = None,
    collection: str = None,
    is_veg: bool = None,
    is_featured: bool = None,
    is_bestseller: bool = None,
    has_active_offer: bool = None,
    min_price: float = None,
    max_price: float = None,
    min_rating: float = None,
    keyword: str = None,
    sort_by: str = "sort_order",
    status: str = "active",
    page: int = 1,
    limit: int = 50
):
    """List products (public) — all filter params optional and backward-compatible."""
    query: dict = {"business_id": business_id, "status": status}

    if category_id:
        query["category_id"] = category_id
    if subcategory_id:
        query["subcategory_id"] = subcategory_id
    if collection:
        query["collection_tags"] = {"$in": [collection]}
    if is_veg is not None:
        query["is_veg"] = is_veg
    if is_featured is not None:
        query["is_featured"] = is_featured
    if is_bestseller is not None:
        query["is_bestseller"] = is_bestseller
    if has_active_offer is not None:
        query["has_active_offer"] = has_active_offer
    if min_price is not None or max_price is not None:
        price_filter: dict = {}
        if min_price is not None:
            price_filter["$gte"] = min_price
        if max_price is not None:
            price_filter["$lte"] = max_price
        query["base_price"] = price_filter
    if min_rating is not None:
        query["avg_rating"] = {"$gte": min_rating}
    if keyword:
        query["$text"] = {"$search": keyword}

    sort_map = {
        "price_asc":   [("base_price", 1)],
        "price_desc":  [("base_price", -1)],
        "rating":      [("avg_rating", -1)],
        "popular":     [("total_ordered", -1)],
        "newest":      [("created_at", -1)],
        "sort_order":  [("sort_order", 1)],
        "trending":    [("trending_score", -1)],
    }
    sort = sort_map.get(sort_by, [("sort_order", 1)])

    skip = (page - 1) * limit
    products = await db.products.find(query, {"_id": 0}).sort(sort).skip(skip).limit(limit).to_list(limit)
    total = await db.products.count_documents(query)

    return {
        "products": products,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit,
        },
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
        "subcategory_id": data.get("subcategory_id"),
        "product_name": data.get("product_name"),
        "description": data.get("description", ""),
        "base_price": data.get("base_price", 0),
        "currency": data.get("currency", "INR"),
        "images": data.get("images", []),
        "attributes": data.get("attributes", {}),
        "variants": data.get("variants", []),
        # New config-driven fields
        "is_veg": data.get("is_veg", None),
        "is_featured": data.get("is_featured", False),
        "is_bestseller": data.get("is_bestseller", False),
        "has_active_offer": False,
        "collection_tags": data.get("collection_tags", []),
        "addons": data.get("addons", []),
        "allergens": data.get("allergens", []),
        "sort_order": data.get("sort_order", 999),
        "status": "active",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
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

    # Track if role or business_access changed
    privilege_changed = False

    if "role" in data:
        allowed = ["super_admin", "business_admin", "staff", "delivery_agent", "customer"]
        if data["role"] not in allowed:
            raise HTTPException(status_code=400, detail=f"role must be one of {allowed}")
        if user.get("role") != data["role"]:
            privilege_changed = True
        updates["role"] = data["role"]

    if "business_access" in data:
        if not isinstance(data["business_access"], list):
            raise HTTPException(status_code=400, detail="business_access must be a list")
        if user.get("business_access") != data["business_access"]:
            privilege_changed = True
        updates["business_access"] = data["business_access"]

    if len(updates) == 1:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    await db.users.update_one({"user_id": user_id}, {"$set": updates})
    
    # Revoke all sessions if privileges changed
    if privilege_changed:
        from backend.auth.sessions import revoke_all_sessions
        revoked_count = await revoke_all_sessions(db, user_id)
        logger.info(f"Revoked {revoked_count} sessions for user {user_id} due to privilege change")
        
        # Emit audit event
        from backend.auth.audit import write_audit_event, AuditEventType
        await write_audit_event(
            db,
            event_type=AuditEventType.ROLE_CHANGED if "role" in updates else AuditEventType.BUSINESS_ACCESS_CHANGED,
            user_id=user_id,
            ip_address=request.client.host if request.client else None,
            details={"updated_by": current_user["user_id"], "changes": list(updates.keys())},
            success=True
        )
    
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

# ── New config-driven modules ──────────────────────────────────────────────
import category_routes
import store_routes
import offers_routes
import collections_routes
import announcements_routes
import business_config_routes
import prime_routes

category_routes.set_db(db)
store_routes.set_db(db)
offers_routes.set_db(db)
collections_routes.set_db(db)
announcements_routes.set_db(db)
business_config_routes.set_db(db)
prime_routes.set_db(db)

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
app.include_router(category_routes.router)
app.include_router(store_routes.router)
app.include_router(offers_routes.router)
app.include_router(collections_routes.router)
app.include_router(announcements_routes.router)
app.include_router(business_config_routes.router)
app.include_router(prime_routes.router)

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
    """
    import trending_refresh

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

        await asyncio.sleep(15 * 60)


async def _category_counts_loop() -> None:
    """Refresh product_count on category docs every 10 minutes."""
    import trending_refresh
    await asyncio.sleep(30)   # start after trending refresh
    while True:
        try:
            await trending_refresh.refresh_category_counts(db)
        except Exception:
            logger.exception("category counts refresh error")
        await asyncio.sleep(10 * 60)


async def _offers_maintenance_loop() -> None:
    """Expire stale offers and sync has_active_offer flags hourly."""
    import trending_refresh
    await asyncio.sleep(60)
    while True:
        try:
            await trending_refresh.expire_offers(db)
            await trending_refresh.sync_has_active_offer(db)
        except Exception:
            logger.exception("offers maintenance error")
        await asyncio.sleep(60 * 60)


async def ensure_new_indexes() -> None:
    """Create indexes for new collections added in Session 1."""
    # categories
    await db.categories.create_index(
        [("business_id", 1), ("is_active", 1), ("sort_order", 1)],
        background=True, name="categories_business_active_order_idx"
    )
    await db.categories.create_index(
        [("business_id", 1), ("category_id", 1)],
        unique=True, background=True, name="categories_business_id_unique_idx"
    )
    # products — new filter fields
    await db.products.create_index(
        [("business_id", 1), ("category_id", 1), ("status", 1)],
        background=True, name="products_business_category_status_idx"
    )
    await db.products.create_index(
        [("business_id", 1), ("collection_tags", 1)],
        background=True, name="products_business_collection_tags_idx"
    )
    await db.products.create_index(
        [("business_id", 1), ("is_veg", 1), ("status", 1)],
        background=True, name="products_business_veg_status_idx"
    )
    await db.products.create_index(
        [("business_id", 1), ("is_bestseller", 1)],
        background=True, name="products_business_bestseller_idx"
    )
    await db.products.create_index(
        [("business_id", 1), ("has_active_offer", 1)],
        background=True, name="products_business_offer_idx"
    )
    # Text search index — created once manually; name in DB is
    # "business_id_1_product_name_text_description_text". Skipped here
    # to avoid IndexOptionsConflict on every startup.
    # offers
    await db.offers.create_index(
        [("business_id", 1), ("is_active", 1), ("valid_until", 1)],
        background=True, name="offers_business_active_expiry_idx"
    )
    await db.offers.create_index(
        [("promo_code", 1)],
        background=True, name="offers_promo_code_idx"
    )
    # collections
    await db.collections.create_index(
        [("business_id", 1), ("is_active", 1)],
        background=True, name="collections_business_active_idx"
    )
    # store_config
    await db.store_config.create_index(
        [("business_id", 1)],
        unique=True, background=True, name="store_config_business_unique_idx"
    )
    # announcements
    await db.announcements.create_index(
        [("business_id", 1), ("is_active", 1), ("priority", -1)],
        background=True, name="announcements_business_active_priority_idx"
    )
    logger.info("new session-1 indexes created / verified")


@app.on_event("startup")
async def startup_event():
    await ensure_user_preferences_indexes()
    await ensure_compound_indexes()
    await ensure_new_indexes()
    asyncio.create_task(_trending_refresh_loop())
    asyncio.create_task(_category_counts_loop())
    asyncio.create_task(_offers_maintenance_loop())

    # Start Prime scheduler
    try:
        from prime.scheduler import start_scheduler
        await start_scheduler(db)
        logger.info("Prime scheduler started")
    except Exception as e:
        logger.error(f"Failed to start Prime scheduler: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    # Stop Prime scheduler
    try:
        from prime.scheduler import stop_scheduler
        await stop_scheduler()
        logger.info("Prime scheduler stopped")
    except Exception as e:
        logger.error(f"Failed to stop Prime scheduler: {e}")
