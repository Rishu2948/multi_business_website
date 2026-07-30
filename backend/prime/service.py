"""
Prime membership service layer.

Handles membership lifecycle, plan management, and admin operations.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from .models import (
    MembershipStatus,
    PrimePlanConfig,
    PrimeMembership,
    SubscribeRequest,
)
from .notifications import (
    send_subscription_welcome_email,
    send_subscription_renewal_email,
    send_subscription_expiry_warning_email,
    send_subscription_expired_email,
    send_subscription_cancelled_email,
    send_payment_failed_email,
    send_grace_period_email,
)
from .payment import razorpay_client

logger = logging.getLogger(__name__)

GRACE_PERIOD_HOURS = 72
RENEWAL_WINDOW_HOURS = 24


async def get_plans(db, business_id: str) -> dict:
    """Read active plans from business_config."""
    try:
        business_config = await db.business_config.find_one(
            {"business_id": business_id},
            {"_id": 0, "prime.enabled": 1, "prime.plans": 1, "prime.features": 1}
        )
        
        if not business_config:
            return {"enabled": False, "plans": [], "enabled_features": []}
        
        prime = business_config.get("prime", {})
        if not prime.get("enabled", False):
            return {"enabled": False, "plans": [], "enabled_features": []}
        
        plans = prime.get("plans", [])
        active_plans = [p for p in plans if p.get("is_active", False)]
        
        features = prime.get("features", {})
        enabled_features = [k for k, v in features.items() if v.get("enabled", False)]
        
        return {
            "enabled": True,
            "display_name": prime.get("display_name", ""),
            "tagline": prime.get("tagline", ""),
            "plans": active_plans,
            "enabled_features": enabled_features,
        }
    except Exception as e:
        logger.error(f"Error getting plans for {business_id}: {e}")
        return {"enabled": False, "plans": [], "enabled_features": []}


async def create_pending_membership(
    db,
    user_id: str,
    business_id: str,
    plan_id: str,
) -> dict:
    """Create a pending membership record."""
    # Check for existing active membership
    existing = await db.prime_memberships.find_one({
        "user_id": user_id,
        "business_id": business_id,
        "status": "active",
        "expires_at": {"$gt": datetime.now(timezone.utc)}
    })
    if existing:
        raise ValueError("Active Prime membership already exists")

    # Check for any existing membership (expired/cancelled) and delete it
    existing_any = await db.prime_memberships.find_one({
        "user_id": user_id,
        "business_id": business_id
    })
    if existing_any:
        logger.info(f"Deleting existing membership {existing_any['membership_id']} to create new one")
        await db.prime_memberships.delete_one({
            "user_id": user_id,
            "business_id": business_id
        })
    
    # Validate plan exists in business config
    business_config = await db.business_config.find_one(
        {"business_id": business_id},
        {"_id": 0, "prime.plans": 1}
    )
    if not business_config:
        raise ValueError("Business config not found")
    
    plans = business_config.get("prime", {}).get("plans", [])
    plan = next((p for p in plans if p["plan_id"] == plan_id), None)
    if not plan:
        raise ValueError("Invalid plan_id")
    if not plan.get("is_active", False):
        raise ValueError("Plan is not active")
    
    # Create pending membership
    membership_id = f"pm_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    
    membership = {
        "membership_id": membership_id,
        "user_id": user_id,
        "business_id": business_id,
        "plan_id": plan_id,
        "status": MembershipStatus.PENDING_PAYMENT,
        "started_at": now,
        "expires_at": now,  # Will be set on activation
        "cancelled_at": None,
        "auto_renew": True,
        "granted_by_admin": False,
        "payment_history": [],
        "notifications_sent": [],
        "created_at": now,
        "updated_at": now,
    }
    
    await db.prime_memberships.insert_one(membership)
    logger.info(f"Created pending membership {membership_id} for {user_id}/{business_id}")
    
    return membership


async def activate_membership(
    db,
    membership_id: str,
    payment_details: dict,
) -> dict:
    """Activate a pending membership after successful payment."""
    membership = await db.prime_memberships.find_one({"membership_id": membership_id})
    if not membership:
        raise ValueError("Membership not found")
    
    if membership["status"] != MembershipStatus.PENDING_PAYMENT:
        raise ValueError("Membership is not in pending_payment state")
    
    # Get plan details for billing cycle
    business_config = await db.business_config.find_one(
        {"business_id": membership["business_id"]},
        {"_id": 0, "prime.plans": 1}
    )
    plans = business_config.get("prime", {}).get("plans", [])
    plan = next((p for p in plans if p["plan_id"] == membership["plan_id"]), None)
    
    if not plan:
        raise ValueError("Plan not found")
    
    # Calculate expiry based on billing cycle and trial period
    now = datetime.now(timezone.utc)
    trial_days = plan.get("trial_days", 0)

    if trial_days > 0:
        # Trial period: membership active for trial days, then billing starts
        expires_at = now + timedelta(days=trial_days)
        trial_end_at = expires_at
    else:
        # No trial: full billing cycle
        if plan["billing_cycle"] == "monthly":
            expires_at = now + timedelta(days=30)
        else:  # annual
            expires_at = now + timedelta(days=365)
        trial_end_at = None
    
    # Update membership
    updates = {
        "status": MembershipStatus.ACTIVE,
        "started_at": now,
        "expires_at": expires_at,
        "auto_renew": True,
        "updated_at": now,
    }

    if trial_end_at:
        updates["trial_end_at"] = trial_end_at
        updates["is_trial"] = True

    # Add payment to history
    payment_entry = {
        "attempt_at": now,
        "status": "success",
        "amount": 0 if trial_days > 0 else plan["price"],  # Free during trial
        "currency": plan["currency"],
        "gateway": payment_details.get("gateway", "unknown"),
        "gateway_transaction_id": payment_details.get("transaction_id"),
    }
    updates["payment_history"] = [payment_entry]

    # Add activation notification
    updates["notifications_sent"] = [{
        "type": "activation",
        "sent_at": now,
    }]

    result = await db.prime_memberships.update_one(
        {"membership_id": membership_id},
        {"$set": updates}
    )

    # Send welcome email
    try:
        user = await db.users.find_one({"user_id": membership["user_id"]}, {"_id": 0, "email": 1, "name": 1})
        if user:
            await send_subscription_welcome_email(
                user.get("email"),
                user.get("name", "Customer"),
                membership["business_id"],
                plan["name"],
                expires_at.strftime("%B %d, %Y"),
            )
    except Exception as e:
        logger.error(f"Failed to send welcome email: {e}")
    
    # Sync is_prime shim
    from .access import sync_is_prime_shim
    await sync_is_prime_shim(db, membership["user_id"])
    
    logger.info(f"Activated membership {membership_id} for {membership['user_id']}")
    return await db.prime_memberships.find_one({"membership_id": membership_id})


async def cancel_membership(db, user_id: str, business_id: str) -> dict:
    """Cancel auto-renew for a membership."""
    membership = await db.prime_memberships.find_one({
        "user_id": user_id,
        "business_id": business_id,
        "status": MembershipStatus.ACTIVE,
    })
    
    if not membership:
        raise ValueError("Active membership not found")
    
    now = datetime.now(timezone.utc)
    await db.prime_memberships.update_one(
        {"user_id": user_id, "business_id": business_id},
        {
            "$set": {
                "auto_renew": False,
                "cancelled_at": now,
                "updated_at": now,
            }
        }
    )
    
    logger.info(f"Cancelled membership for {user_id}/{business_id}")
    return await db.prime_memberships.find_one({
        "user_id": user_id,
        "business_id": business_id
    })


async def reactivate_membership(db, user_id: str, business_id: str) -> dict:
    """Re-enable auto-renew for a membership."""
    membership = await db.prime_memberships.find_one({
        "user_id": user_id,
        "business_id": business_id,
    })
    
    if not membership:
        raise ValueError("Membership not found")
    
    if membership["status"] == MembershipStatus.EXPIRED:
        raise ValueError("Cannot reactivate expired membership. Please subscribe again.")
    
    now = datetime.now(timezone.utc)
    await db.prime_memberships.update_one(
        {"user_id": user_id, "business_id": business_id},
        {
            "$set": {
                "auto_renew": True,
                "cancelled_at": None,
                "updated_at": now,
            }
        }
    )
    
    logger.info(f"Reactivated membership for {user_id}/{business_id}")
    return await db.prime_memberships.find_one({
        "user_id": user_id,
        "business_id": business_id
    })


async def get_membership(db, user_id: str, business_id: str) -> Optional[dict]:
    """Get single membership for a user and business."""
    return await db.prime_memberships.find_one({
        "user_id": user_id,
        "business_id": business_id
    }, {"_id": 0})


async def get_all_memberships(db, user_id: str) -> List[dict]:
    """Get all memberships for a user across businesses."""
    cursor = db.prime_memberships.find(
        {"user_id": user_id},
        {"_id": 0}
    )
    return await cursor.to_list(length=None)


async def expire_membership(db, membership_id: str) -> dict:
    """Expire a membership."""
    membership = await db.prime_memberships.find_one({"membership_id": membership_id})
    if not membership:
        raise ValueError("Membership not found")
    
    now = datetime.now(timezone.utc)
    await db.prime_memberships.update_one(
        {"membership_id": membership_id},
        {
            "$set": {
                "status": MembershipStatus.EXPIRED,
                "updated_at": now,
            }
        }
    )
    
    # Sync is_prime shim
    from .access import sync_is_prime_shim
    await sync_is_prime_shim(db, membership["user_id"])
    
    logger.info(f"Expired membership {membership_id}")
    return await db.prime_memberships.find_one({"membership_id": membership_id})


async def admin_grant(
    db,
    admin_id: str,
    user_id: str,
    business_id: str,
    plan_id: str,
) -> dict:
    """Manually grant a membership (admin operation)."""
    # Check for existing active membership
    existing = await db.prime_memberships.find_one({
        "user_id": user_id,
        "business_id": business_id,
        "status": MembershipStatus.ACTIVE,
        "expires_at": {"$gt": datetime.now(timezone.utc)}
    })
    if existing:
        raise ValueError("Active Prime membership already exists")
    
    # Validate plan
    business_config = await db.business_config.find_one(
        {"business_id": business_id},
        {"_id": 0, "prime.plans": 1}
    )
    plans = business_config.get("prime", {}).get("plans", [])
    plan = next((p for p in plans if p["plan_id"] == plan_id), None)
    if not plan:
        raise ValueError("Invalid plan_id")
    
    # Check for existing membership and delete it
    existing = await db.prime_memberships.find_one({
        "user_id": user_id,
        "business_id": business_id
    })
    if existing:
        await db.prime_memberships.delete_one({
            "user_id": user_id,
            "business_id": business_id
        })

    # Create membership
    membership_id = f"pm_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    if plan["billing_cycle"] == "monthly":
        expires_at = now + timedelta(days=30)
    else:
        expires_at = now + timedelta(days=365)

    membership = {
        "membership_id": membership_id,
        "user_id": user_id,
        "business_id": business_id,
        "plan_id": plan_id,
        "status": MembershipStatus.ACTIVE,
        "started_at": now,
        "expires_at": expires_at,
        "cancelled_at": None,
        "auto_renew": True,
        "granted_by_admin": True,
        "payment_history": [],
        "notifications_sent": [],
        "created_at": now,
        "updated_at": now,
    }

    await db.prime_memberships.insert_one(membership)
    
    # Log to admin audit log
    await db.admin_audit_log.insert_one({
        "admin_user_id": admin_id,
        "target_user_id": user_id,
        "business_id": business_id,
        "action": "grant_prime_membership",
        "timestamp": now,
        "details": {"plan_id": plan_id, "membership_id": membership_id},
    })
    
    # Sync is_prime shim
    from .access import sync_is_prime_shim
    await sync_is_prime_shim(db, user_id)
    
    logger.info(f"Admin {admin_id} granted membership {membership_id} to {user_id}")
    return membership


async def admin_revoke(
    db,
    admin_id: str,
    user_id: str,
    business_id: str,
) -> dict:
    """Manually revoke a membership (admin operation)."""
    membership = await db.prime_memberships.find_one({
        "user_id": user_id,
        "business_id": business_id,
    })

    if not membership:
        raise ValueError("Membership not found")

    now = datetime.now(timezone.utc)
    await db.prime_memberships.update_one(
        {"user_id": user_id, "business_id": business_id},
        {
            "$set": {
                "status": MembershipStatus.CANCELLED,
                "auto_renew": False,
                "cancelled_at": now,
                "updated_at": now,
            }
        }
    )

    # Log to admin audit log
    await db.admin_audit_log.insert_one({
        "admin_user_id": admin_id,
        "target_user_id": user_id,
        "business_id": business_id,
        "action": "revoke_prime_membership",
        "timestamp": now,
        "details": {"membership_id": membership["membership_id"]},
    })

    # Sync is_prime shim
    from .access import sync_is_prime_shim
    await sync_is_prime_shim(db, user_id)

    logger.info(f"Admin {admin_id} revoked membership for {user_id}/{business_id}")
    return await db.prime_memberships.find_one({
        "user_id": user_id,
        "business_id": business_id
    })


# ── Payment Integration Functions ───────────────────────────────────────────

async def sync_razorpay_plans(db, business_id: str) -> Dict[str, Any]:
    """Sync plans from business_config to Razorpay."""
    if not razorpay_client.is_configured():
        logger.warning("Razorpay not configured, skipping plan sync")
        return {"success": False, "reason": "Razorpay not configured"}

    business_config = await db.business_config.find_one(
        {"business_id": business_id},
        {"_id": 0, "prime.plans": 1}
    )

    if not business_config:
        return {"success": False, "reason": "Business config not found"}

    plans = business_config.get("prime", {}).get("plans", [])
    synced = []

    for plan in plans:
        if not plan.get("is_active", False):
            continue

        # Check if plan already has gateway_product_id
        if plan.get("gateway_product_id"):
            synced.append({"plan_id": plan["plan_id"], "status": "exists"})
            continue

        # Create plan in Razorpay
        razorpay_plan = razorpay_client.create_plan({
            "plan_id": plan["plan_id"],
            "name": plan["name"],
            "billing_cycle": plan["billing_cycle"],
            "price": plan["price"],
            "currency": plan.get("currency", "INR"),
            "business_id": business_id,
        })

        if razorpay_plan:
            # Update business_config with gateway_product_id
            await db.business_config.update_one(
                {"business_id": business_id, "prime.plans.plan_id": plan["plan_id"]},
                {"$set": {"prime.plans.$.gateway_product_id": razorpay_plan["id"]}}
            )
            synced.append({"plan_id": plan["plan_id"], "status": "created", "razorpay_id": razorpay_plan["id"]})
        else:
            synced.append({"plan_id": plan["plan_id"], "status": "failed"})

    return {"success": True, "synced": synced}


async def create_razorpay_customer(db, user_id: str) -> Optional[str]:
    """Create or get Razorpay customer ID for a user."""
    if not razorpay_client.is_configured():
        return None

    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        return None

    # Check if user already has razorpay_customer_id
    if user.get("razorpay_customer_id"):
        return user["razorpay_customer_id"]

    # Create customer in Razorpay
    razorpay_customer = razorpay_client.create_customer(
        name=user.get("name", ""),
        email=user.get("email", ""),
        phone=user.get("phone"),
    )

    if razorpay_customer:
        # Update user with razorpay_customer_id
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"razorpay_customer_id": razorpay_customer["id"]}}
        )
        return razorpay_customer["id"]

    return None


async def initiate_subscription_payment(
    db,
    user_id: str,
    business_id: str,
    plan_id: str,
) -> Dict[str, Any]:
    """Initiate subscription payment with Razorpay."""
    if not razorpay_client.is_configured():
        raise ValueError("Payment gateway not configured")

    # Get plan details
    business_config = await db.business_config.find_one(
        {"business_id": business_id},
        {"_id": 0, "prime.plans": 1}
    )
    plans = business_config.get("prime", {}).get("plans", [])
    plan = next((p for p in plans if p["plan_id"] == plan_id), None)

    if not plan:
        raise ValueError("Plan not found")

    # Create pending membership
    membership = await create_pending_membership(db, user_id, business_id, plan_id)

    # Create Razorpay customer
    customer_id = await create_razorpay_customer(db, user_id)
    if not customer_id:
        raise ValueError("Failed to create payment customer")

    # Create Razorpay order (one-time payment for MVP)
    razorpay_order = razorpay_client.create_checkout_session(
        plan_id=plan.get("gateway_product_id", ""),
        customer_id=customer_id,
        amount=plan["price"],
        currency=plan.get("currency", "INR"),
        notes={
            "membership_id": membership["membership_id"],
            "user_id": user_id,
            "business_id": business_id,
            "plan_id": plan_id,
        }
    )

    if not razorpay_order:
        raise ValueError("Failed to create payment order")

    # Update membership with order details
    await db.prime_memberships.update_one(
        {"membership_id": membership["membership_id"]},
        {
            "$set": {
                "razorpay_order_id": razorpay_order["id"],
                "updated_at": datetime.now(timezone.utc),
            }
        }
    )

    return {
        "membership_id": membership["membership_id"],
        "razorpay_order_id": razorpay_order["id"],
        "razorpay_key_id": razorpay_client.key_id,
        "amount": plan["price"],
        "currency": plan.get("currency", "INR"),
    }


async def verify_and_activate_payment(
    db,
    membership_id: str,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> Dict[str, Any]:
    """Verify Razorpay payment and activate membership."""
    if not razorpay_client.is_configured():
        raise ValueError("Payment gateway not configured")

    # Verify signature
    is_valid = razorpay_client.verify_payment_signature(
        order_id=razorpay_order_id,
        payment_id=razorpay_payment_id,
        signature=razorpay_signature,
    )

    if not is_valid:
        raise ValueError("Invalid payment signature")

    # Get membership
    membership = await db.prime_memberships.find_one({"membership_id": membership_id})
    if not membership:
        raise ValueError("Membership not found")

    if membership.get("razorpay_order_id") != razorpay_order_id:
        raise ValueError("Order ID mismatch")

    # Activate membership
    payment_details = {
        "gateway": "razorpay",
        "transaction_id": razorpay_payment_id,
        "order_id": razorpay_order_id,
    }

    activated = await activate_membership(db, membership_id, payment_details)

    return activated
