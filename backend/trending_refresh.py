"""
backend/trending_refresh.py

Background job: pre-compute trending scores for all active products.

Replaces the N+1 query pattern in get_trending_products() with two
batch aggregations + one bulk_write. DB operations: 3 total, regardless
of how many products exist.

Scoring formula (same weights as the original endpoint):
    trending_score = (total_ordered * 10) + (avg_rating * 5) + (review_count * 2)

Called by the asyncio background loop in server.py every 15 minutes.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from pymongo import UpdateOne
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


async def refresh_trending_scores(db: AsyncIOMotorDatabase, business_id: str) -> int:
    """
    Compute and store trending_score, total_ordered, avg_rating, review_count
    on every active product for *business_id*.

    Returns the number of product documents updated.

    Previous approach (N+1):
        for each product:               # O(N)
            aggregate orders            # 1 DB call
            find reviews                # 1 DB call
        → 2N + 1 total DB round-trips

    This approach (batch):
        aggregate orders once           # 1 DB call  (all products, all orders)
        aggregate reviews once          # 1 DB call  (all products)
        fetch product_ids once          # 1 DB call
        bulk_write all updates          # 1 DB call
        → 4 total DB round-trips, independent of product count
    """

    # ── 1. Order quantities for ALL products in this business ─────────────
    # Unwind order items, group by product_id, sum quantities.
    # Scoped to business_id so we don't scan the entire orders collection.
    order_pipeline = [
        {"$match": {"business_id": business_id}},
        {"$unwind": "$items"},
        {"$group": {
            "_id": "$items.product_id",
            "total_ordered": {"$sum": "$items.quantity"}
        }}
    ]
    order_counts: dict[str, int] = {}
    async for row in db.orders.aggregate(order_pipeline):
        order_counts[row["_id"]] = row["total_ordered"]

    # ── 2. Review stats for ALL products ──────────────────────────────────
    # Not scoped by business_id — reviews only carry product_id.
    # This is fine: the subsequent bulk_write only touches products
    # belonging to the target business.
    review_pipeline = [
        {"$group": {
            "_id": "$product_id",
            "avg_rating":   {"$avg": "$rating"},
            "review_count": {"$sum": 1}
        }}
    ]
    review_stats: dict[str, dict] = {}
    async for row in db.reviews.aggregate(review_pipeline):
        review_stats[row["_id"]] = {
            "avg_rating":   row["avg_rating"] or 0.0,
            "review_count": row["review_count"],
        }

    # ── 3. Build bulk update ops for all active products ──────────────────
    bulk_ops: list[UpdateOne] = []
    async for product in db.products.find(
        {"business_id": business_id, "status": "active"},
        {"_id": 0, "product_id": 1}
    ):
        pid = product["product_id"]
        total_ordered = order_counts.get(pid, 0)
        stats         = review_stats.get(pid, {"avg_rating": 0.0, "review_count": 0})
        avg_rating    = float(stats["avg_rating"])
        review_count  = int(stats["review_count"])

        trending_score = (total_ordered * 10) + (avg_rating * 5) + (review_count * 2)

        bulk_ops.append(UpdateOne(
            {"product_id": pid},
            {"$set": {
                "trending_score":    round(trending_score, 1),
                "total_ordered":     total_ordered,
                "avg_rating":        round(avg_rating, 1),
                "review_count":      review_count,
                "scores_updated_at": datetime.now(timezone.utc),
            }}
        ))

    if not bulk_ops:
        logger.info("trending_refresh: business=%s — no active products found", business_id)
        return 0

    # ordered=False lets MongoDB execute writes in parallel (no sequential dependency)
    result = await db.products.bulk_write(bulk_ops, ordered=False)
    logger.info(
        "trending_refresh: business=%s  products=%d  modified=%d",
        business_id, len(bulk_ops), result.modified_count
    )
    return result.modified_count
