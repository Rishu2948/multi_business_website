"""
ai-chatbot/services/catalog_query.py

Catalog Query Engine — translates parsed intent + filters into MongoDB queries,
manages two complementary TTLCache layers, implements ranking/personalisation
for ``recommend`` intent, product comparison, and cache eviction.

Requirements: 3.2, 3.3, 3.4, 4.2, 4.3, 4.4, 7.2, 7.3, 9.2, 9.5
"""

from __future__ import annotations

import hashlib
import json
import threading
from typing import Any, Optional

from cachetools import TTLCache
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

# ---------------------------------------------------------------------------
# Module-level caches (initialised once at import time)
# ---------------------------------------------------------------------------

# Full active product list per business_id.
# 50 slots — one per business; 10-minute TTL (Requirement 3.3 / caching strategy).
catalog_cache: TTLCache = TTLCache(maxsize=50, ttl=600)

# Ranked result sets, keyed by "{business_id}:{filter_hash}".
# 500 slots; 60-second TTL (caching strategy).
query_cache: TTLCache = TTLCache(maxsize=500, ttl=60)

# cachetools.TTLCache is NOT thread-safe — guard every read/write with this lock.
_cache_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_COMPARISON_FIELDS = {
    "product_id": 1,
    "product_name": 1,
    "base_price": 1,
    "description": 1,
    "images": 1,
    "category_id": 1,
    "avg_rating": 1,
    "review_count": 1,
    "total_ordered": 1,
    "attributes": 1,
    "_id": 0,
}

_PRODUCT_PROJECTION = {
    "product_id": 1,
    "product_name": 1,
    "base_price": 1,
    "description": 1,
    "images": 1,
    "category_id": 1,
    "avg_rating": 1,
    "total_ordered": 1,
    "attributes": 1,
    "status": 1,
    "_id": 0,  # Requirement 9.5 — never expose raw MongoDB _id
}


def _filter_hash(filters: dict) -> str:
    """Return a stable SHA-256 hex digest for *filters*.

    The dict is serialised with ``sort_keys=True`` so that
    ``{"a": 1, "b": 2}`` and ``{"b": 2, "a": 1}`` produce the same hash.
    """
    serialised = json.dumps(filters, sort_keys=True, default=str)
    return hashlib.sha256(serialised.encode()).hexdigest()


def _strip_id(doc: dict) -> dict:
    """Return a copy of *doc* with ``_id`` removed (Requirement 9.5)."""
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# Query construction
# ---------------------------------------------------------------------------


def build_query(business_id: str, filters: dict) -> dict:
    """Translate *filters* into a MongoDB query document for *business_id*.

    Only uses MongoDB driver query objects — no string interpolation of user
    input (Requirement 9.2).

    Supported filter keys
    ---------------------
    keyword    → ``$text: {"$search": kw}``
    category   → ``$or`` with case-insensitive ``$regex`` on
                  ``category_id`` and ``attributes.category``
    flavor     → ``$or`` with case-insensitive ``$regex`` on
                  ``product_name``, ``description``, ``attributes.flavor``
    price_min  → ``base_price: {"$gte": max(0, price_min)}``
    price_max  → ``base_price: {"$lte": min(price_max, 999_999)}``

    Raises
    ------
    HTTPException(400)
        When ``price_min > price_max`` (Requirement 3.3).
    """
    pmin = filters.get("price_min")
    pmax = filters.get("price_max")
    if pmin is not None and pmax is not None and pmin > pmax:
        raise HTTPException(
            status_code=400,
            detail="price_min must not be greater than price_max",
        )

    q: dict[str, Any] = {"business_id": business_id, "status": "active"}

    if kw := filters.get("keyword"):
        q["$text"] = {"$search": kw}

    or_clauses: list[dict] = []

    if cat := filters.get("category"):
        or_clauses += [
            {"category_id": {"$regex": cat, "$options": "i"}},
            {"attributes.category": {"$regex": cat, "$options": "i"}},
        ]

    if flv := filters.get("flavor"):
        or_clauses += [
            {"product_name": {"$regex": flv, "$options": "i"}},
            {"description": {"$regex": flv, "$options": "i"}},
            {"attributes.flavor": {"$regex": flv, "$options": "i"}},
        ]

    if or_clauses:
        q["$or"] = or_clauses

    price_q: dict[str, Any] = {}
    if pmin is not None:
        price_q["$gte"] = max(0, pmin)
    if pmax is not None:
        price_q["$lte"] = min(pmax, 999_999)
    if price_q:
        q["base_price"] = price_q

    return q


# ---------------------------------------------------------------------------
# In-memory filter application (used when catalog_cache is warm)
# ---------------------------------------------------------------------------


def _matches_filters(product: dict, filters: dict) -> bool:
    """Return ``True`` when *product* satisfies all non-None *filters*.

    This mirrors the MongoDB query logic so the in-memory path and the DB
    path produce equivalent result sets.
    """
    pmin = filters.get("price_min")
    pmax = filters.get("price_max")
    price = product.get("base_price", 0)
    if pmin is not None and price < max(0, pmin):
        return False
    if pmax is not None and price > min(pmax, 999_999):
        return False

    cat = filters.get("category")
    if cat:
        cat_lower = cat.lower()
        cat_id = (product.get("category_id") or "").lower()
        attr_cat = (
            (product.get("attributes") or {}).get("category") or ""
        ).lower()
        if cat_lower not in cat_id and cat_lower not in attr_cat:
            return False

    flv = filters.get("flavor")
    if flv:
        flv_lower = flv.lower()
        name = (product.get("product_name") or "").lower()
        desc = (product.get("description") or "").lower()
        attr_flv = (
            (product.get("attributes") or {}).get("flavor") or ""
        ).lower()
        if flv_lower not in name and flv_lower not in desc and flv_lower not in attr_flv:
            return False

    kw = filters.get("keyword")
    if kw:
        kw_lower = kw.lower()
        name = (product.get("product_name") or "").lower()
        desc = (product.get("description") or "").lower()
        if kw_lower not in name and kw_lower not in desc:
            return False

    return True


def _filter_match_score(product: dict, filters: dict) -> int:
    """Count how many filter keys the product explicitly matches (≥ 1 each).

    Used as the tertiary ranking key for ``recommend`` intent.
    """
    score = 0
    if filters.get("category"):
        cat_lower = (filters["category"]).lower()
        cat_id = (product.get("category_id") or "").lower()
        attr_cat = (
            (product.get("attributes") or {}).get("category") or ""
        ).lower()
        if cat_lower in cat_id or cat_lower in attr_cat:
            score += 1
    if filters.get("flavor"):
        flv_lower = (filters["flavor"]).lower()
        name = (product.get("product_name") or "").lower()
        desc = (product.get("description") or "").lower()
        attr_flv = (
            (product.get("attributes") or {}).get("flavor") or ""
        ).lower()
        if flv_lower in name or flv_lower in desc or flv_lower in attr_flv:
            score += 1
    if filters.get("keyword"):
        kw_lower = (filters["keyword"]).lower()
        name = (product.get("product_name") or "").lower()
        desc = (product.get("description") or "").lower()
        if kw_lower in name or kw_lower in desc:
            score += 1
    return score


# ---------------------------------------------------------------------------
# TTLCache-aware query execution
# ---------------------------------------------------------------------------


async def query_products(
    db: AsyncIOMotorDatabase,
    business_id: str,
    filters: dict,
) -> list[dict]:
    """Return filtered products using the TTLCache lookup order.

    Lookup order
    ------------
    1. ``query_cache["{business_id}:{hash}"]`` — return immediately on hit.
    2. ``catalog_cache[business_id]`` — apply filters in-memory on hit,
       then populate ``query_cache``.
    3. Both miss — fetch all active products from MongoDB, populate
       ``catalog_cache``, apply filters, populate ``query_cache``.

    All cache reads/writes are wrapped with ``_cache_lock``
    (``cachetools.TTLCache`` is not thread-safe).

    Requirement 9.5: ``_id`` is excluded via projection or ``pop``.
    """
    fhash = _filter_hash(filters)
    cache_key = f"{business_id}:{fhash}"

    # ── Step 1: query_cache hit ──────────────────────────────────────────
    with _cache_lock:
        cached_result = query_cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    # ── Step 2: catalog_cache hit ────────────────────────────────────────
    with _cache_lock:
        full_catalog = catalog_cache.get(business_id)

    if full_catalog is not None:
        result = [p for p in full_catalog if _matches_filters(p, filters)]
        with _cache_lock:
            query_cache[cache_key] = result
        return result

    # ── Step 3: both miss — fetch from MongoDB ───────────────────────────
    cursor = db["products"].find(
        {"business_id": business_id, "status": "active"},
        _PRODUCT_PROJECTION,
    )
    all_products: list[dict] = []
    async for doc in cursor:
        _strip_id(doc)
        all_products.append(doc)

    with _cache_lock:
        catalog_cache[business_id] = all_products

    result = [p for p in all_products if _matches_filters(p, filters)]

    with _cache_lock:
        query_cache[cache_key] = result

    return result


# ---------------------------------------------------------------------------
# Recommend
# ---------------------------------------------------------------------------


async def recommend(
    db: AsyncIOMotorDatabase,
    business_id: str,
    filters: dict,
    user_context: Optional[dict] = None,
) -> list[dict]:
    """Return up to 6 products ranked for ``recommend`` intent.

    Ranking (deterministic 3-key sort, Requirement 4.2)
    ---------------------------------------------------
    1. ``avg_rating``         descending
    2. ``total_ordered``      descending
    3. filter_match_score     descending

    Personalisation priority (Requirement 4.4)
    ------------------------------------------
    1. ``user_preferences`` MongoDB document — attached by Session_Manager as
       ``user_context["preference_vector"]`` before this call.
    2. ``preference_summary`` from the request body — ``user_context["preference_summary"]``.
    3. Live lookup of ``product_views`` (≤ 20) and ``orders`` (≤ 10).

    Fallback (Requirement 4.2)
    --------------------------
    When 0 products match the filters, return the top-rated products for the
    business (sorted by ``avg_rating`` desc, ``total_ordered`` desc, capped at 6).

    Parameters
    ----------
    db:           Motor async database.
    business_id:  Scoping business.
    filters:      Active filter dict (may be empty).
    user_context: Optional dict with keys:
                  ``user_id``          — authenticated user identifier
                  ``preference_vector``— pre-computed vector from user_preferences
                  ``preference_summary``— dict from request body
    """
    user_context = user_context or {}
    user_id = user_context.get("user_id")

    # ── Resolve personalisation signal ────────────────────────────────────
    pref_vector: Optional[dict] = None

    # Priority 1: user_preferences document (attached by Session_Manager)
    if user_context.get("preference_vector"):
        pref_vector = user_context["preference_vector"]

    # Priority 2: preference_summary from request body
    elif user_context.get("preference_summary"):
        pref_vector = user_context["preference_summary"]

    # Priority 3: live lookup when user_id is available but no pre-computed vector
    elif user_id:
        pref_vector = await _live_preference_lookup(db, user_id)

    # ── Merge preference-derived filters with explicit filters ─────────────
    effective_filters = _merge_preference_filters(filters, pref_vector)

    # ── Fetch candidate products ──────────────────────────────────────────
    candidates = await query_products(db, business_id, effective_filters)

    # ── Sort by ranking keys ──────────────────────────────────────────────
    candidates = sorted(
        candidates,
        key=lambda p: (
            -(p.get("avg_rating") or 0.0),
            -(p.get("total_ordered") or 0),
            -_filter_match_score(p, effective_filters),
        ),
    )

    # ── Fallback: top-rated if 0 results ─────────────────────────────────
    if not candidates:
        all_products = await _fetch_all_active(db, business_id)
        candidates = sorted(
            all_products,
            key=lambda p: (
                -(p.get("avg_rating") or 0.0),
                -(p.get("total_ordered") or 0),
            ),
        )

    return candidates[:6]


async def _fetch_all_active(db: AsyncIOMotorDatabase, business_id: str) -> list[dict]:
    """Return all active products for *business_id*, using catalog_cache when warm."""
    with _cache_lock:
        cached = catalog_cache.get(business_id)
    if cached is not None:
        return cached

    cursor = db["products"].find(
        {"business_id": business_id, "status": "active"},
        _PRODUCT_PROJECTION,
    )
    products: list[dict] = []
    async for doc in cursor:
        _strip_id(doc)
        products.append(doc)

    with _cache_lock:
        catalog_cache[business_id] = products

    return products


async def _live_preference_lookup(db: AsyncIOMotorDatabase, user_id: str) -> Optional[dict]:
    """Fallback live lookup: read ≤20 recent views and ≤10 recent orders.

    Returns a lightweight preference dict compatible with ``preference_summary``
    shape, or ``None`` if no history exists.
    """
    views_cursor = (
        db["product_views"]
        .find({"user_id": user_id}, {"_id": 0, "product_id": 1})
        .sort("viewed_at", -1)
        .limit(20)
    )
    viewed_ids: list[str] = []
    async for v in views_cursor:
        viewed_ids.append(v["product_id"])

    orders_cursor = (
        db["orders"]
        .find({"user_id": user_id}, {"_id": 0, "items": 1})
        .sort("created_at", -1)
        .limit(10)
    )
    ordered_ids: list[str] = []
    async for o in orders_cursor:
        for item in o.get("items", []):
            pid = item.get("product_id")
            if pid:
                ordered_ids.append(pid)

    if not viewed_ids and not ordered_ids:
        return None

    return {"viewed_product_ids": viewed_ids, "ordered_product_ids": ordered_ids}


def _merge_preference_filters(filters: dict, pref_vector: Optional[dict]) -> dict:
    """Merge preference signal into filters without overriding explicit user filters.

    Explicit filters always win; preference vector only fills in absent keys.
    """
    if not pref_vector:
        return filters

    merged = dict(filters)

    # Enrich flavor from preference if not already set
    if not merged.get("flavor"):
        top_flavors = pref_vector.get("top_flavors", [])
        if top_flavors:
            merged["flavor"] = top_flavors[0]

    # Enrich price range from preference if not already set
    if not merged.get("price_max"):
        pr = pref_vector.get("price_range")
        if pr and pr.get("max"):
            merged["price_max"] = pr["max"]
    if not merged.get("price_min"):
        pr = pref_vector.get("price_range")
        if pr and pr.get("min"):
            merged["price_min"] = pr["min"]

    return merged


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------


async def compare(
    db: AsyncIOMotorDatabase,
    business_id: str,
    product_ids: list[str],
) -> dict:
    """Fetch full product details for comparison.

    Resolution rules (Requirement 7.2 / 7.3)
    -----------------------------------------
    - ≥ 2 IDs resolve → return up to 4 products + ``missing_product_names`` list.
    - < 2 IDs resolve → return ``{"intent": "compare_failed", "products": [],
      "missing_product_names": [...]}``.
    - Maximum 4 products (max 4 column headers in comparison table).

    Requirement 9.5: ``_id`` excluded via projection.

    Parameters
    ----------
    db:          Motor async database.
    business_id: Scoping business.
    product_ids: List of product IDs to compare (resolved from conversation context).
    """
    # Cap at 4 IDs to query (extra are ignored for the table max-4 constraint)
    ids_to_fetch = product_ids[:4]

    cursor = db["products"].find(
        {"business_id": business_id, "product_id": {"$in": ids_to_fetch}},
        _COMPARISON_FIELDS,
    )
    resolved: list[dict] = []
    async for doc in cursor:
        _strip_id(doc)
        resolved.append(doc)

    resolved_ids = {p["product_id"] for p in resolved}
    missing_ids = [pid for pid in ids_to_fetch if pid not in resolved_ids]

    # Attempt to get human-readable names for missing IDs from catalog_cache
    missing_names = _resolve_missing_names(missing_ids, business_id)

    if len(resolved) < 2:
        return {
            "intent": "compare_failed",
            "products": [],
            "missing_product_names": missing_names if missing_names else missing_ids,
        }

    return {
        "intent": "compare",
        "products": resolved[:4],
        "missing_product_names": missing_names if missing_names else missing_ids,
    }


def _resolve_missing_names(missing_ids: list[str], business_id: str) -> list[str]:
    """Try to look up product names for *missing_ids* from the in-memory cache."""
    if not missing_ids:
        return []

    with _cache_lock:
        catalog = catalog_cache.get(business_id)

    if not catalog:
        return missing_ids

    id_to_name = {p["product_id"]: p.get("product_name", p["product_id"]) for p in catalog}
    return [id_to_name.get(pid, pid) for pid in missing_ids]


# ---------------------------------------------------------------------------
# Cache eviction
# ---------------------------------------------------------------------------


def evict_catalog_cache(business_id: str) -> dict:
    """Remove *business_id* from ``catalog_cache`` and all matching
    ``query_cache`` entries idempotently.

    When a product is updated or deleted the cache-bust endpoint calls this
    function.  Evicting only ``catalog_cache`` would leave stale per-filter
    result sets in ``query_cache`` for up to 60 seconds, so both caches must
    be purged together.

    Returns ``{"evicted": True}`` whether or not any entry was present
    (Requirement 3.3 / cache-bust endpoint contract).

    Thread-safe: all cache mutations are guarded by ``_cache_lock``.
    """
    prefix = f"{business_id}:"
    with _cache_lock:
        catalog_cache.pop(business_id, None)
        # Remove all query_cache entries that belong to this business_id.
        # TTLCache supports key iteration; collect keys first to avoid
        # mutating the dict during iteration.
        stale_keys = [k for k in list(query_cache.keys()) if k.startswith(prefix)]
        for k in stale_keys:
            query_cache.pop(k, None)
    return {"evicted": True}
