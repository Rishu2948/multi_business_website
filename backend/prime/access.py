"""
Access helper for Prime feature checks.

Provides centralized access control for Prime-gated features.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from .feature_registry import get_feature

logger = logging.getLogger(__name__)

ADMIN_ROLES = {"super_admin", "business_admin", "staff"}


async def has_prime_feature(
    db,
    user_id: str,
    business_id: str,
    feature_key: str,
    *,
    role: Optional[str] = None,
) -> bool:
    """
    Returns True iff:
      1. feature_key is registered
      2. prime.enabled and prime.features[feature_key].enabled in business_config
      3. user is admin/staff OR has active prime_membership for business_id
    Falls back to users.is_prime for whisked_words during migration.
    Reads live from MongoDB (no caching) to ensure immediate revocation.
    """
    # 1. Validate feature key
    if not get_feature(feature_key):
        logger.warning(f"Unknown feature key requested: {feature_key}")
        return False

    # 2. Check business config
    try:
        business_config = await db.business_config.find_one(
            {"business_id": business_id},
            {"_id": 0, "prime.enabled": 1, "prime.features": 1}
        )
    except Exception as e:
        logger.error(f"Error reading business_config for {business_id}: {e}")
        return False

    if not business_config:
        logger.warning(f"business_config not found for {business_id}")
        return False

    prime_config = business_config.get("prime", {})
    if not prime_config.get("enabled", False):
        return False

    feature_config = prime_config.get("features", {}).get(feature_key, {})
    if not feature_config.get("enabled", False):
        return False

    # 3. Admin bypass
    if role in ADMIN_ROLES:
        return True

    # 4. Check active membership
    try:
        membership = await db.prime_memberships.find_one({
            "user_id": user_id,
            "business_id": business_id,
            "status": "active",
            "expires_at": {"$gt": datetime.now(timezone.utc)}
        })
        if membership:
            return True
    except Exception as e:
        logger.error(f"Error checking prime_memberships for {user_id}/{business_id}: {e}")

    # 5. Migration fallback: check global is_prime for whisked_words
    if business_id == "whisked_words":
        try:
            user = await db.users.find_one(
                {"user_id": user_id},
                {"_id": 0, "is_prime": 1}
            )
            if user and user.get("is_prime", False):
                logger.info(f"Using migration fallback for {user_id} on whisked_words")
                return True
        except Exception as e:
            logger.error(f"Error checking migration fallback for {user_id}: {e}")

    return False


async def get_enabled_features(db, business_id: str) -> list[str]:
    """Get list of enabled feature keys for a business."""
    try:
        business_config = await db.business_config.find_one(
            {"business_id": business_id},
            {"_id": 0, "prime.features": 1}
        )
        if not business_config:
            return []

        features = business_config.get("prime", {}).get("features", {})
        return [key for key, config in features.items() if config.get("enabled", False)]
    except Exception as e:
        logger.error(f"Error getting enabled features for {business_id}: {e}")
        return []


async def sync_is_prime_shim(db, user_id: str):
    """
    Set users.is_prime based on any active membership.
    Called after membership state changes.
    """
    try:
        count = await db.prime_memberships.count_documents({
            "user_id": user_id,
            "status": "active",
            "expires_at": {"$gt": datetime.now(timezone.utc)},
        })
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"is_prime": count > 0}},
        )
        logger.debug(f"Synced is_prime for {user_id}: {count > 0}")
    except Exception as e:
        logger.error(f"Error syncing is_prime shim for {user_id}: {e}")
