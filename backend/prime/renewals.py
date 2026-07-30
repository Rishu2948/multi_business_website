"""
Automatic Subscription Renewal Service

Handles automatic renewal of Prime subscriptions that are about to expire.
This should be run as a scheduled task (e.g., daily cron job).
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from .models import MembershipStatus
from .payment import razorpay_client
from .service import activate_membership, expire_membership

logger = logging.getLogger(__name__)

RENEWAL_WINDOW_DAYS = 7  # Renew memberships expiring within 7 days
GRACE_PERIOD_DAYS = 3  # Grace period after expiry before final cancellation


async def get_memberships_due_for_renewal(db) -> List[Dict[str, Any]]:
    """Get memberships that are due for renewal."""
    now = datetime.now(timezone.utc)
    renewal_threshold = now + timedelta(days=RENEWAL_WINDOW_DAYS)
    
    # Find active memberships with auto_renew enabled, expiring soon
    cursor = db.prime_memberships.find({
        "status": MembershipStatus.ACTIVE,
        "auto_renew": True,
        "expires_at": {
            "$lte": renewal_threshold,
            "$gt": now,  # Not yet expired
        }
    }, {"_id": 0})
    
    return await cursor.to_list(length=None)


async def get_expired_memberships_in_grace(db) -> List[Dict[str, Any]]:
    """Get memberships that have expired but are still in grace period."""
    now = datetime.now(timezone.utc)
    grace_threshold = now - timedelta(days=GRACE_PERIOD_DAYS)
    
    # Find expired or in_grace_period memberships within grace period
    cursor = db.prime_memberships.find({
        "status": {"$in": [MembershipStatus.EXPIRED, MembershipStatus.IN_GRACE_PERIOD]},
        "auto_renew": True,
        "expires_at": {
            "$gte": grace_threshold,
            "$lte": now,
        }
    }, {"_id": 0})
    
    return await cursor.to_list(length=None)


async def process_renewal(db, membership: Dict[str, Any]) -> Dict[str, Any]:
    """Process renewal for a single membership."""
    membership_id = membership["membership_id"]
    user_id = membership["user_id"]
    business_id = membership["business_id"]
    plan_id = membership["plan_id"]
    
    logger.info(f"Processing renewal for membership {membership_id}")
    
    # Get plan details
    business_config = await db.business_config.find_one(
        {"business_id": business_id},
        {"_id": 0, "prime.plans": 1}
    )
    
    if not business_config:
        logger.error(f"Business config not found for {business_id}")
        return {"success": False, "error": "Business config not found"}
    
    plans = business_config.get("prime", {}).get("plans", [])
    plan = next((p for p in plans if p["plan_id"] == plan_id), None)
    
    if not plan:
        logger.error(f"Plan {plan_id} not found")
        return {"success": False, "error": "Plan not found"}
    
    # Check if Razorpay is configured
    if not razorpay_client.is_configured():
        logger.warning("Razorpay not configured, skipping automatic renewal")
        return {"success": False, "error": "Payment gateway not configured"}
    
    # For MVP: We'll use manual renewal via admin grant
    # In production, this would create a Razorpay subscription charge
    # For now, we'll log that renewal is needed and require manual intervention
    
    logger.warning(f"Automatic renewal requires manual intervention for {membership_id}")
    logger.info(f"To renew manually, call admin_grant for user {user_id}, business {business_id}, plan {plan_id}")
    
    # TODO: Implement actual Razorpay subscription renewal
    # This would involve:
    # 1. Creating a Razorpay order for the plan amount
    # 2. Charging the customer's saved payment method
    # 3. On success, extending the membership expiry
    # 4. On failure, entering grace period
    
    return {
        "success": False,
        "error": "Manual intervention required",
        "membership_id": membership_id,
        "user_id": user_id,
        "business_id": business_id,
        "plan_id": plan_id,
    }


async def process_grace_period_renewal(db, membership: Dict[str, Any]) -> Dict[str, Any]:
    """Attempt to renew a membership that's in grace period."""
    membership_id = membership["membership_id"]
    
    logger.info(f"Processing grace period renewal for membership {membership_id}")
    
    # Update status to in_grace_period if not already
    now = datetime.now(timezone.utc)
    await db.prime_memberships.update_one(
        {"membership_id": membership_id},
        {
            "$set": {
                "status": MembershipStatus.IN_GRACE_PERIOD,
                "updated_at": now,
            }
        }
    )
    
    # Attempt renewal with urgency
    result = await process_renewal(db, membership)
    
    if result.get("success"):
        # Renewal successful, update status back to active
        await db.prime_memberships.update_one(
            {"membership_id": membership_id},
            {
                "$set": {
                    "status": MembershipStatus.ACTIVE,
                    "updated_at": now,
                }
            }
        )
    else:
        logger.warning(f"Grace period renewal failed for {membership_id}")
    
    return result


async def cancel_membership_after_grace(db, membership: Dict[str, Any]) -> Dict[str, Any]:
    """Cancel membership after grace period expires."""
    membership_id = membership["membership_id"]
    
    logger.info(f"Cancelling membership {membership_id} after grace period")
    
    now = datetime.now(timezone.utc)
    await db.prime_memberships.update_one(
        {"membership_id": membership_id},
        {
            "$set": {
                "status": MembershipStatus.CANCELLED,
                "auto_renew": False,
                "updated_at": now,
            }
        }
    )
    
    # Sync is_prime shim
    from .access import sync_is_prime_shim
    await sync_is_prime_shim(db, membership["user_id"])
    
    return {"success": True, "message": "Membership cancelled after grace period"}


async def run_renewal_job(db) -> Dict[str, Any]:
    """
    Run the renewal job.
    
    This should be called periodically (e.g., daily) to:
    1. Find memberships due for renewal
    2. Attempt to renew them
    3. Handle grace period renewals
    4. Cancel memberships past grace period
    """
    logger.info("Starting renewal job")
    
    results = {
        "processed": 0,
        "renewed": 0,
        "failed": 0,
        "grace_renewed": 0,
        "cancelled": 0,
        "errors": [],
    }
    
    try:
        # Process memberships due for renewal
        due_for_renewal = await get_memberships_due_for_renewal(db)
        logger.info(f"Found {len(due_for_renewal)} memberships due for renewal")
        
        for membership in due_for_renewal:
            results["processed"] += 1
            try:
                result = await process_renewal(db, membership)
                if result.get("success"):
                    results["renewed"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "membership_id": membership["membership_id"],
                        "error": result.get("error"),
                    })
            except Exception as e:
                logger.error(f"Error renewing membership {membership['membership_id']}: {e}")
                results["failed"] += 1
                results["errors"].append({
                    "membership_id": membership["membership_id"],
                    "error": str(e),
                })
        
        # Process grace period renewals
        grace_memberships = await get_expired_memberships_in_grace(db)
        logger.info(f"Found {len(grace_memberships)} memberships in grace period")
        
        for membership in grace_memberships:
            results["processed"] += 1
            try:
                result = await process_grace_period_renewal(db, membership)
                if result.get("success"):
                    results["grace_renewed"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "membership_id": membership["membership_id"],
                        "error": result.get("error"),
                    })
            except Exception as e:
                logger.error(f"Error renewing grace membership {membership['membership_id']}: {e}")
                results["failed"] += 1
                results["errors"].append({
                    "membership_id": membership["membership_id"],
                    "error": str(e),
                })
        
        # Cancel memberships past grace period
        now = datetime.now(timezone.utc)
        grace_threshold = now - timedelta(days=GRACE_PERIOD_DAYS)
        
        expired_past_grace = await db.prime_memberships.find({
            "status": MembershipStatus.EXPIRED,
            "auto_renew": True,
            "expires_at": {"$lt": grace_threshold},
        }).to_list(length=None)
        
        logger.info(f"Found {len(expired_past_grace)} memberships past grace period")
        
        for membership in expired_past_grace:
            results["processed"] += 1
            try:
                await cancel_membership_after_grace(db, membership)
                results["cancelled"] += 1
            except Exception as e:
                logger.error(f"Error cancelling membership {membership['membership_id']}: {e}")
                results["errors"].append({
                    "membership_id": membership["membership_id"],
                    "error": str(e),
                })
        
        logger.info(f"Renewal job completed: {results}")
        return results
        
    except Exception as e:
        logger.error(f"Renewal job failed: {e}")
        results["errors"].append({"error": str(e)})
        return results
