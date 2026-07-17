"""
Webhook Handlers for Prime Subscription Payment Events

Handles Razorpay webhook events for subscription lifecycle management.
"""

import logging
from typing import Dict, Any
from datetime import datetime, timezone, timedelta

from .payment import razorpay_client
from .service import activate_membership, expire_membership

logger = logging.getLogger(__name__)


async def handle_razorpay_webhook(
    db,
    webhook_data: Dict[str, Any],
    signature: str,
) -> Dict[str, Any]:
    """
    Handle Razorpay webhook events.
    
    Events handled:
    - payment.captured: Successful payment, activate membership
    - subscription.cancelled: Subscription cancelled
    - subscription.completed: Subscription ended
    - payment.failed: Payment failed
    """
    if not razorpay_client.is_configured():
        logger.error("Razorpay not configured, cannot process webhook")
        return {"success": False, "error": "Razorpay not configured"}

    event_type = webhook_data.get("event")
    payload = webhook_data.get("payload", {})
    entity = payload.get("entity", {})

    logger.info(f"Processing Razorpay webhook: {event_type}")

    try:
        if event_type == "payment.captured":
            return await handle_payment_captured(db, entity)
        elif event_type == "subscription.cancelled":
            return await handle_subscription_cancelled(db, entity)
        elif event_type == "subscription.completed":
            return await handle_subscription_completed(db, entity)
        elif event_type == "payment.failed":
            return await handle_payment_failed(db, entity)
        else:
            logger.info(f"Unhandled webhook event: {event_type}")
            return {"success": True, "message": "Event acknowledged (no action needed)"}
    except Exception as e:
        logger.error(f"Error processing webhook {event_type}: {e}")
        return {"success": False, "error": str(e)}


async def handle_payment_captured(db, entity: Dict[str, Any]) -> Dict[str, Any]:
    """Handle successful payment - activate membership."""
    notes = entity.get("notes", {})
    membership_id = notes.get("membership_id")
    user_id = notes.get("user_id")
    business_id = notes.get("business_id")
    plan_id = notes.get("plan_id")

    if not membership_id:
        logger.error("Payment captured but no membership_id in notes")
        return {"success": False, "error": "Missing membership_id"}

    # Check if membership already active
    membership = await db.prime_memberships.find_one({"membership_id": membership_id})
    if not membership:
        logger.error(f"Membership {membership_id} not found")
        return {"success": False, "error": "Membership not found"}

    if membership["status"] == "active":
        logger.info(f"Membership {membership_id} already active")
        return {"success": True, "message": "Membership already active"}

    # Activate membership
    payment_details = {
        "gateway": "razorpay",
        "transaction_id": entity.get("id"),
        "order_id": entity.get("order_id"),
        "amount": entity.get("amount") / 100,  # Convert paise to rupees
        "currency": entity.get("currency"),
    }

    activated = await activate_membership(db, membership_id, payment_details)
    logger.info(f"Activated membership {membership_id} via payment webhook")

    return {"success": True, "membership_id": membership_id}


async def handle_subscription_cancelled(db, entity: Dict[str, Any]) -> Dict[str, Any]:
    """Handle subscription cancellation."""
    notes = entity.get("notes", {})
    user_id = notes.get("user_id")
    business_id = notes.get("business_id")

    if not user_id or not business_id:
        logger.error("Subscription cancelled but missing user_id or business_id in notes")
        return {"success": False, "error": "Missing user_id or business_id"}

    # Update membership to cancel auto-renew
    now = datetime.now(timezone.utc)
    result = await db.prime_memberships.update_one(
        {"user_id": user_id, "business_id": business_id, "status": "active"},
        {
            "$set": {
                "auto_renew": False,
                "cancelled_at": now,
                "updated_at": now,
            }
        }
    )

    if result.modified_count > 0:
        logger.info(f"Cancelled auto-renew for membership {user_id}/{business_id}")
        return {"success": True, "message": "Auto-renew cancelled"}
    else:
        logger.warning(f"No active membership found for {user_id}/{business_id}")
        return {"success": True, "message": "No active membership to cancel"}


async def handle_subscription_completed(db, entity: Dict[str, Any]) -> Dict[str, Any]:
    """Handle subscription completion (all cycles completed)."""
    notes = entity.get("notes", {})
    user_id = notes.get("user_id")
    business_id = notes.get("business_id")

    if not user_id or not business_id:
        logger.error("Subscription completed but missing user_id or business_id in notes")
        return {"success": False, "error": "Missing user_id or business_id"}

    # Expire membership
    membership = await db.prime_memberships.find_one({
        "user_id": user_id,
        "business_id": business_id,
        "status": "active",
    })

    if membership:
        await expire_membership(db, membership["membership_id"])
        logger.info(f"Expired membership {membership['membership_id']} via subscription completion")
        return {"success": True, "message": "Membership expired"}
    else:
        logger.warning(f"No active membership found for {user_id}/{business_id}")
        return {"success": True, "message": "No active membership to expire"}


async def handle_payment_failed(db, entity: Dict[str, Any]) -> Dict[str, Any]:
    """Handle payment failure - log and potentially enter grace period."""
    notes = entity.get("notes", {})
    membership_id = notes.get("membership_id")
    user_id = notes.get("user_id")
    business_id = notes.get("business_id")

    if not membership_id:
        logger.error("Payment failed but no membership_id in notes")
        return {"success": False, "error": "Missing membership_id"}

    # Get membership
    membership = await db.prime_memberships.find_one({"membership_id": membership_id})
    if not membership:
        logger.error(f"Membership {membership_id} not found")
        return {"success": False, "error": "Membership not found"}

    # Add failed payment to history
    now = datetime.now(timezone.utc)
    failed_payment = {
        "attempt_at": now,
        "status": "failed",
        "amount": entity.get("amount") / 100,
        "currency": entity.get("currency"),
        "gateway": "razorpay",
        "gateway_transaction_id": entity.get("id"),
        "error_code": entity.get("error_code"),
        "error_description": entity.get("error_description"),
    }

    await db.prime_memberships.update_one(
        {"membership_id": membership_id},
        {
            "$push": {"payment_history": failed_payment},
            "$set": {"updated_at": now}
        }
    )

    logger.warning(f"Payment failed for membership {membership_id}: {entity.get('error_description')}")

    # TODO: Implement grace period logic
    # If this is a recurring payment failure, enter grace period
    # For now, just log the failure

    return {"success": True, "message": "Payment failure logged"}
