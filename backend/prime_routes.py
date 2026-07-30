"""
Prime Subscription Routes

Handles Prime subscription lifecycle: plans, subscribe, cancel, webhooks.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel

from prime.models import (
    MembershipStatus,
    SubscribeRequest,
    MembershipResponse,
    PlansResponse,
)
from prime.service import (
    get_plans,
    create_pending_membership,
    activate_membership,
    cancel_membership,
    reactivate_membership,
    get_membership,
    get_all_memberships,
    admin_grant,
    admin_revoke,
    sync_razorpay_plans,
    initiate_subscription_payment,
    verify_and_activate_payment,
)
from prime.webhooks import handle_razorpay_webhook
from prime.payment import razorpay_client
from prime.renewals import run_renewal_job
from prime.analytics import get_prime_analytics, get_prime_analytics_all_businesses, get_membership_churn_rate, get_revenue_forecast
from prime.coupons import create_coupon, validate_coupon, apply_coupon, get_coupons, disable_coupon, calculate_discounted_price
from prime.models import CouponType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prime")

db = None


def set_db(database):
    global db
    db = database


# ── Helper Functions ───────────────────────────────────────────────────────

async def _require_auth(request: Request):
    from server import get_current_user
    return await get_current_user(request)


async def _require_admin(request: Request):
    from server import get_current_user
    user = await get_current_user(request)
    if user["role"] not in ("super_admin", "business_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def _check_business_access(user: dict, business_id: str):
    if user["role"] == "super_admin":
        return
    allowed = {a["business_id"] for a in user.get("business_access", [])}
    if business_id not in allowed:
        raise HTTPException(status_code=403, detail="Access denied for this business")


# ── Public Routes ───────────────────────────────────────────────────────────

@router.get("/plans/{business_id}")
async def get_plans_public(business_id: str):
    """Public: get available plans and enabled features."""
    plans_data = await get_plans(db, business_id)
    
    if not plans_data["enabled"]:
        raise HTTPException(
            status_code=404,
            detail=f"Prime not available for business: {business_id}"
        )
    
    return PlansResponse(
        enabled=plans_data["enabled"],
        display_name=plans_data["display_name"],
        tagline=plans_data["tagline"],
        plans=plans_data["plans"],
        enabled_features=plans_data["enabled_features"],
    )


@router.get("/upgrade-info/{business_id}")
async def get_upgrade_info(business_id: str, request: Request):
    """Get plans + user's membership if authenticated."""
    plans_data = await get_plans(db, business_id)
    
    if not plans_data["enabled"]:
        raise HTTPException(
            status_code=404,
            detail=f"Prime not available for business: {business_id}"
        )
    
    response = {
        "enabled": plans_data["enabled"],
        "display_name": plans_data["display_name"],
        "tagline": plans_data["tagline"],
        "plans": plans_data["plans"],
        "enabled_features": plans_data["enabled_features"],
    }
    
    # Add membership info if authenticated
    try:
        user = await _require_auth(request)
        membership = await get_membership(db, user["user_id"], business_id)
        if membership:
            response["membership"] = {
                "membership_id": membership["membership_id"],
                "status": membership["status"],
                "expires_at": membership["expires_at"],
                "auto_renew": membership["auto_renew"],
                "plan_id": membership["plan_id"],
            }
    except:
        # Not authenticated, return public info only
        pass
    
    return response


# ── Authenticated Routes ───────────────────────────────────────────────────

@router.post("/subscribe")
async def subscribe(request: Request, data: SubscribeRequest):
    """Start subscription checkout."""
    user = await _require_auth(request)

    # Validate business config
    plans_data = await get_plans(db, data.business_id)
    if not plans_data["enabled"]:
        raise HTTPException(
            status_code=404,
            detail=f"Prime not available for business: {data.business_id}"
        )

    # For MVP: Activate membership directly without payment
    # In production, this would create pending membership and redirect to payment gateway
    try:
        from prime.service import admin_grant
        membership = await admin_grant(
            db, user["user_id"], user["user_id"], data.business_id, data.plan_id
        )
    except ValueError as e:
        if "already exists" in str(e):
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "message": "Membership activated",
        "membership_id": membership["membership_id"],
        "status": membership["status"],
    }


@router.get("/my-membership")
async def get_my_membership(business_id: str = Query(...), request: Request = None):
    """Get user's membership for a specific business."""
    user = await _require_auth(request)
    
    membership = await get_membership(db, user["user_id"], business_id)
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")
    
    # Get plan details
    plans_data = await get_plans(db, business_id)
    plan = next((p for p in plans_data.get("plans", []) if p["plan_id"] == membership["plan_id"]), None)
    
    return MembershipResponse(
        membership_id=membership["membership_id"],
        business_id=membership["business_id"],
        plan_id=membership["plan_id"],
        status=membership["status"],
        started_at=membership["started_at"],
        expires_at=membership["expires_at"],
        auto_renew=membership["auto_renew"],
        plan_name=plan["name"] if plan else membership["plan_id"],
        price=plan["price"] if plan else 0,
        billing_cycle=plan["billing_cycle"] if plan else "monthly",
        enabled_features=plans_data.get("enabled_features", []),
    )


@router.get("/my-memberships")
async def get_my_memberships(request: Request):
    """Get all memberships for the authenticated user."""
    user = await _require_auth(request)
    
    memberships = await get_all_memberships(db, user["user_id"])
    
    result = []
    for membership in memberships:
        plans_data = await get_plans(db, membership["business_id"])
        plan = next((p for p in plans_data.get("plans", []) if p["plan_id"] == membership["plan_id"]), None)
        
        result.append({
            "membership_id": membership["membership_id"],
            "business_id": membership["business_id"],
            "status": membership["status"],
            "expires_at": membership["expires_at"],
            "auto_renew": membership["auto_renew"],
            "plan_name": plan["name"] if plan else membership["plan_id"],
            "enabled_features": plans_data.get("enabled_features", []),
        })
    
    return result


@router.post("/cancel")
async def cancel_subscription(request: Request, business_id: str = Query(...)):
    """Cancel auto-renew for membership."""
    user = await _require_auth(request)

    try:
        membership = await cancel_membership(db, user["user_id"], business_id)
        return {"message": "Membership cancelled", "expires_at": membership["expires_at"]}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/reactivate")
async def reactivate_subscription(request: Request, business_id: str = Query(...)):
    """Re-enable auto-renew for membership."""
    user = await _require_auth(request)

    try:
        membership = await reactivate_membership(db, user["user_id"], business_id)
        return {"message": "Membership reactivated", "auto_renew": membership["auto_renew"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Admin Routes ───────────────────────────────────────────────────────────

@router.get("/admin/memberships")
async def get_admin_memberships(
    business_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    request: Request = None,
):
    """Get paginated list of memberships for a business (admin only)."""
    user = await _require_admin(request)

    # If business_id is provided, check access
    if business_id:
        await _check_business_access(user, business_id)
    elif user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Only super admins can view all businesses")

    skip = (page - 1) * limit

    # Build query based on business_id
    query = {"business_id": business_id} if business_id else {}

    cursor = db.prime_memberships.find(
        query,
        {"_id": 0}
    ).skip(skip).limit(limit)

    memberships = await cursor.to_list(length=None)

    total = await db.prime_memberships.count_documents(query)

    return {
        "memberships": memberships,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.post("/admin/grant/{user_id}")
async def admin_grant_membership(user_id: str, request: Request):
    """Manually grant a membership (super_admin only)."""
    user = await _require_admin(request)
    if user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    
    # Get business_id and plan_id from request body
    data = await request.json()
    business_id = data.get("business_id")
    plan_id = data.get("plan_id")
    
    if not business_id or not plan_id:
        raise HTTPException(status_code=400, detail="business_id and plan_id required")
    
    try:
        membership = await admin_grant(db, user["user_id"], user_id, business_id, plan_id)
        return {"message": "Membership granted", "membership_id": membership["membership_id"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/revoke/{user_id}")
async def admin_revoke_membership(user_id: str, request: Request):
    """Manually revoke a membership (super_admin only)."""
    user = await _require_admin(request)
    if user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    
    data = await request.json()
    business_id = data.get("business_id")
    
    if not business_id:
        raise HTTPException(status_code=400, detail="business_id required")
    
    try:
        membership = await admin_revoke(db, user["user_id"], user_id, business_id)
        return {"message": "Membership revoked"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/admin/run-renewal-job")
async def run_renewal_job_endpoint(request: Request):
    """Manually trigger the renewal job (super_admin only)."""
    user = await _require_admin(request)
    if user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")

    results = await run_renewal_job(db)
    return results


# ── Analytics Routes ───────────────────────────────────────────────────────

@router.get("/admin/analytics/{business_id}")
async def get_business_analytics(business_id: str, days: int = 30, request: Request = None):
    """Get Prime analytics for a specific business (admin only)."""
    user = await _require_admin(request)
    await _check_business_access(user, business_id)

    analytics = await get_prime_analytics(db, business_id, days)
    return analytics


@router.get("/admin/analytics/all")
async def get_all_business_analytics(days: int = 30, request: Request = None):
    """Get Prime analytics across all businesses (super_admin only)."""
    user = await _require_admin(request)
    if user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")

    analytics = await get_prime_analytics_all_businesses(db, days)
    return analytics


@router.get("/admin/churn-rate/{business_id}")
async def get_churn_rate(business_id: str, days: int = 30, request: Request = None):
    """Get churn rate for a business (admin only)."""
    user = await _require_admin(request)
    await _check_business_access(user, business_id)

    churn_rate = await get_membership_churn_rate(db, business_id, days)
    return churn_rate


@router.get("/admin/revenue-forecast/{business_id}")
async def get_revenue_forecast_endpoint(business_id: str, months: int = 6, request: Request = None):
    """Get revenue forecast for a business (admin only)."""
    user = await _require_admin(request)
    await _check_business_access(user, business_id)

    forecast = await get_revenue_forecast(db, business_id, months)
    return forecast


# ── Coupon Management Routes ─────────────────────────────────────────────────

@router.post("/admin/coupons")
async def create_coupon_endpoint(request: Request):
    """Create a new discount coupon (admin only)."""
    user = await _require_admin(request)
    data = await request.json()

    business_id = data.get("business_id")
    await _check_business_access(user, business_id)

    coupon = await create_coupon(
        db,
        business_id=business_id,
        code=data.get("code"),
        coupon_type=CouponType(data.get("coupon_type")),
        discount_value=data.get("discount_value"),
        created_by=user["user_id"],
        currency=data.get("currency", "INR"),
        trial_days=data.get("trial_days"),
        max_uses=data.get("max_uses"),
        valid_from=data.get("valid_from"),
        valid_until=data.get("valid_until"),
        applicable_plans=data.get("applicable_plans"),
    )

    return {"success": True, "coupon": coupon}


@router.get("/coupons/validate")
async def validate_coupon_endpoint(code: str, business_id: str, plan_id: str):
    """Validate a coupon code (public)."""
    try:
        validation = await validate_coupon(db, business_id, code, plan_id)
        return validation
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/coupons/apply")
async def apply_coupon_endpoint(request: Request):
    """Apply a coupon to a subscription (authenticated)."""
    user = await _require_auth(request)
    data = await request.json()

    try:
        result = await apply_coupon(db, data["coupon_id"], user["user_id"])
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/admin/coupons/{business_id}")
async def get_coupons_endpoint(business_id: str, include_expired: bool = False, request: Request = None):
    """Get all coupons for a business (admin only)."""
    user = await _require_admin(request)
    await _check_business_access(user, business_id)

    coupons = await get_coupons(db, business_id, include_expired)
    return {"coupons": coupons}


@router.post("/admin/coupons/{coupon_id}/disable")
async def disable_coupon_endpoint(coupon_id: str, request: Request):
    """Disable a coupon (admin only)."""
    user = await _require_admin(request)

    try:
        result = await disable_coupon(db, coupon_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Payment Integration Routes ───────────────────────────────────────────────

@router.post("/admin/sync-plans/{business_id}")
async def sync_payment_plans(business_id: str, request: Request):
    """Sync plans from business_config to Razorpay (admin only)."""
    user = await _require_admin(request)
    await _check_business_access(user, business_id)

    result = await sync_razorpay_plans(db, business_id)
    return result


@router.post("/payment/initiate")
async def initiate_payment(request: Request):
    """Initiate Razorpay payment for Prime subscription."""
    user = await _require_auth(request)

    data = await request.json()
    business_id = data.get("business_id")
    plan_id = data.get("plan_id")

    if not business_id or not plan_id:
        raise HTTPException(status_code=400, detail="business_id and plan_id required")

    try:
        result = await initiate_subscription_payment(db, user["user_id"], business_id, plan_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/payment/verify")
async def verify_payment(request: Request):
    """Verify Razorpay payment and activate membership."""
    user = await _require_auth(request)

    data = await request.json()
    membership_id = data.get("membership_id")
    razorpay_order_id = data.get("razorpay_order_id")
    razorpay_payment_id = data.get("razorpay_payment_id")
    razorpay_signature = data.get("razorpay_signature")

    if not all([membership_id, razorpay_order_id, razorpay_payment_id, razorpay_signature]):
        raise HTTPException(status_code=400, detail="All payment verification fields required")

    try:
        result = await verify_and_activate_payment(
            db, membership_id, razorpay_order_id, razorpay_payment_id, razorpay_signature
        )
        return {"message": "Payment verified and membership activated", "membership": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Webhook Routes ───────────────────────────────────────────────────────────

@router.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request):
    """Handle Razorpay payment webhooks."""
    # Get webhook signature for verification
    signature = request.headers.get("x-razorpay-signature")
    
    # Get webhook body
    body = await request.body()
    
    # Verify signature (if Razorpay is configured)
    if razorpay_client.is_configured():
        # TODO: Implement proper signature verification
        # For now, we'll skip verification in development
        pass
    
    # Parse webhook data
    import json
    try:
        webhook_data = json.loads(body)
    except json.JSONDecodeError:
        logger.error("Invalid webhook JSON")
        raise HTTPException(status_code=400, detail="Invalid webhook data")
    
    # Handle webhook event
    result = await handle_razorpay_webhook(db, webhook_data, signature)
    
    if result.get("success"):
        return {"status": "success", "message": result.get("message")}
    else:
        logger.error(f"Webhook processing failed: {result.get('error')}")
        # Still return 200 to acknowledge receipt, but log error
        return {"status": "error", "error": result.get("error")}


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe payment webhooks."""
    # TODO: Implement signature validation and event processing
    # For MVP, return 200 to acknowledge receipt
    logger.info("Stripe webhook received (MVP placeholder)")
    return {"status": "received"}
