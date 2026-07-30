"""
Prime Subscription Analytics and Reporting

Provides analytics functions for Prime membership metrics.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from collections import defaultdict

logger = logging.getLogger(__name__)


async def get_prime_analytics(db, business_id: str, days: int = 30) -> Dict[str, Any]:
    """Get Prime membership analytics for a business."""
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days)

    # Get all memberships for the business
    cursor = db.prime_memberships.find({
        "business_id": business_id,
        "created_at": {"$gte": start_date}
    })

    memberships = await cursor.to_list(length=None)

    # Calculate metrics
    total_memberships = len(memberships)
    active_memberships = len([m for m in memberships if m.get("status") == "active"])
    expired_memberships = len([m for m in memberships if m.get("status") == "expired"])
    cancelled_memberships = len([m for m in memberships if m.get("status") == "cancelled"])
    trial_memberships = len([m for m in memberships if m.get("is_trial") == True])

    # Calculate revenue (excluding trials)
    revenue = 0
    for m in memberships:
        if m.get("payment_history"):
            for payment in m["payment_history"]:
                if payment.get("status") == "success":
                    revenue += payment.get("amount", 0)

    # Calculate conversion rate (trials that converted to paid)
    converted_trials = 0
    total_trials = 0
    for m in memberships:
        if m.get("is_trial"):
            total_trials += 1
            if m.get("payment_history") and len(m["payment_history"]) > 1:
                converted_trials += 1

    conversion_rate = (converted_trials / total_trials * 100) if total_trials > 0 else 0

    # Plan distribution
    plan_distribution = defaultdict(int)
    for m in memberships:
        plan_distribution[m.get("plan_name", "Unknown")] += 1

    # Daily signups
    daily_signups = defaultdict(int)
    for m in memberships:
        date_key = m.get("created_at", now).strftime("%Y-%m-%d")
        daily_signups[date_key] += 1

    return {
        "business_id": business_id,
        "period_days": days,
        "total_memberships": total_memberships,
        "active_memberships": active_memberships,
        "expired_memberships": expired_memberships,
        "cancelled_memberships": cancelled_memberships,
        "trial_memberships": trial_memberships,
        "revenue": revenue,
        "conversion_rate": round(conversion_rate, 2),
        "plan_distribution": dict(plan_distribution),
        "daily_signups": dict(daily_signups),
    }


async def get_prime_analytics_all_businesses(db, days: int = 30) -> Dict[str, Any]:
    """Get Prime analytics across all businesses."""
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days)

    # Get all businesses with Prime enabled
    cursor = db.business_config.find({
        "prime.enabled": True
    }, {"_id": 0, "business_id": 1})

    businesses = await cursor.to_list(length=None)

    total_analytics = {
        "total_businesses": len(businesses),
        "period_days": days,
        "total_memberships": 0,
        "active_memberships": 0,
        "total_revenue": 0,
        "business_analytics": [],
    }

    for business in businesses:
        business_id = business["business_id"]
        try:
            analytics = await get_prime_analytics(db, business_id, days)
            total_analytics["business_analytics"].append(analytics)
            total_analytics["total_memberships"] += analytics["total_memberships"]
            total_analytics["active_memberships"] += analytics["active_memberships"]
            total_analytics["total_revenue"] += analytics["revenue"]
        except Exception as e:
            logger.error(f"Error getting analytics for {business_id}: {e}")

    return total_analytics


async def get_membership_churn_rate(db, business_id: str, days: int = 30) -> Dict[str, Any]:
    """Calculate churn rate for Prime memberships."""
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days)

    # Get memberships that were active at start of period
    cursor = db.prime_memberships.find({
        "business_id": business_id,
        "status": "active",
        "started_at": {"$lte": start_date}
    })

    active_at_start = await cursor.to_list(length=None)
    total_active_at_start = len(active_at_start)

    # Get memberships that were cancelled during the period
    cursor = db.prime_memberships.find({
        "business_id": business_id,
        "status": "cancelled",
        "cancelled_at": {"$gte": start_date, "$lte": now}
    })

    cancelled_during_period = await cursor.to_list(length=None)
    total_cancelled = len(cancelled_during_period)

    # Calculate churn rate
    churn_rate = (total_cancelled / total_active_at_start * 100) if total_active_at_start > 0 else 0

    return {
        "business_id": business_id,
        "period_days": days,
        "active_at_start": total_active_at_start,
        "cancelled_during_period": total_cancelled,
        "churn_rate": round(churn_rate, 2),
    }


async def get_revenue_forecast(db, business_id: str, months: int = 6) -> Dict[str, Any]:
    """Forecast recurring revenue for Prime memberships."""
    now = datetime.now(timezone.utc)
    forecast_date = now + timedelta(days=30 * months)

    # Get active memberships with auto-renew enabled
    cursor = db.prime_memberships.find({
        "business_id": business_id,
        "status": "active",
        "auto_renew": True,
        "expires_at": {"$gt": now}
    })

    active_memberships = await cursor.to_list(length=None)

    # Calculate monthly recurring revenue (MRR)
    mrr = 0
    for m in active_memberships:
        # Get plan details to determine monthly value
        business_config = await db.business_config.find_one(
            {"business_id": business_id},
            {"_id": 0, "prime.plans": 1}
        )
        plans = business_config.get("prime", {}).get("plans", [])
        plan = next((p for p in plans if p["plan_id"] == m["plan_id"]), None)

        if plan:
            if plan["billing_cycle"] == "monthly":
                mrr += plan["price"]
            else:  # annual
                mrr += plan["price"] / 12  # Convert to monthly equivalent

    # Projected revenue for the forecast period
    projected_revenue = mrr * months

    return {
        "business_id": business_id,
        "current_mrr": round(mrr, 2),
        "forecast_months": months,
        "projected_revenue": round(projected_revenue, 2),
        "active_auto_renew_memberships": len(active_memberships),
    }
