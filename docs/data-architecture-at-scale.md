# Data Architecture at Scale
### Multi-Business E-Commerce Platform — Interview Reference

> This document covers the current database design, its limitations at scale, and the migration path to a production-grade data architecture. Written as a reference for technical interviews.

---

## 1. Current Stack

| Component | Technology | Why |
|---|---|---|
| Primary Database | MongoDB (via Motor async) | Flexible schemas for multi-business product attributes |
| Backend API | FastAPI + Python | Async I/O, clean REST surface |
| In-process Cache | cachetools TTLCache | Fast catalog reads without Redis overhead |
| AI Chatbot | FastAPI + MongoDB | Shared DB, session storage with TTL indexes |

The platform manages the following collections:

- `users` — authentication, roles, business access
- `businesses` — multi-tenant business entities
- `products` — catalog with flexible `attributes` dict per business type
- `orders` — line items, delivery info, payment status
- `inventory` — per-variant stock with movement history
- `product_views` — event log for recommendation engine
- `reviews` — ratings attached to products
- `user_preferences` — pre-computed recommendation vectors (12h TTL)
- `chat_sessions` — AI chatbot state (30-min TTL)
- `user_sessions` — auth session tokens (7-day TTL)

---

## 2. Why MongoDB Was the Right Starting Choice

**Schema flexibility is genuinely needed here.** Each business type has different product attributes — a bakery product has `flavor`, `weight`, `occasion`; a different business might have `size`, `material`, `color`. Storing these in a relational DB would require either an EAV (Entity-Attribute-Value) anti-pattern or a separate table per business type, both of which are painful to query. MongoDB's document model handles this cleanly.

**TTL indexes eliminate cron jobs.** Both `chat_sessions` and `user_preferences` have natural expiry. MongoDB's TTL index feature auto-deletes expired documents without any application-level scheduling. This is genuinely elegant.

**Motor gives true async I/O.** The entire backend is `async/await`. Motor is the async MongoDB driver for Python — every DB call is non-blocking, which pairs well with FastAPI's event loop model.

---

## 3. Where MongoDB Breaks Down at Scale

### 3.1 The Trending Endpoint Problem

The current `/products/trending/{business_id}` implementation is the most critical scalability issue in the codebase:

```python
# server.py — get_trending_products()
for product in products:  # could be hundreds of products
    order_pipeline = [...]
    order_agg = await db.orders.aggregate(order_pipeline).to_list(1)  # DB call per product
    reviews = await db.reviews.find({"product_id": pid}, ...).to_list(500)  # DB call per product
```

This is an **N+1 query pattern** — it runs two database calls per product. At 100 products, that's 200 sequential DB round-trips per request. At 1,000 products, it becomes unusable. MongoDB aggregations are powerful, but no database can save you from this pattern.

**The fix** is to pre-compute the trending score on a schedule and store it on the product document. See Section 5.1.

### 3.2 Recommendation Logic — Multiple Round-Trips

The recommendation endpoint (`/products/recommended/{business_id}`) does:
1. Fetch all active products (up to 200)
2. Fetch user's viewed products
3. Fetch user's orders
4. Join everything in Python memory

This works fine up to a few thousand users. Once `product_views` and `orders` collections grow into the millions, queries like `{"user_id": user_id, "business_id": business_id}` without careful compound indexing will do collection scans.

### 3.3 Analytics Is Impossible at Scale in MongoDB

MongoDB is an **OLTP** database — it's designed for transactional read/write operations on individual documents. It is not designed for:

- "What was our revenue by business and category for the last 6 months?"
- "What's the average time from order placement to delivery, by city?"
- "Which products have the highest cart abandonment rate?"
- "Build a cohort analysis of users who joined in Q1 vs Q2"

These are **OLAP** queries. Running them against MongoDB means full collection scans, expensive aggregation pipelines, and they will compete with your live traffic for resources.

### 3.4 No Cross-Collection Transactions (by default)

MongoDB supports multi-document transactions since v4.0, but Motor's async usage requires explicit session handling. The current code does not use transactions. This means operations like:

```
create order → deduct inventory → create payment record
```

...are not atomic. If the server crashes between step 2 and step 3, you get inconsistent state. This is acceptable at early stage but is a correctness problem at scale.

### 3.5 In-Process Cache Doesn't Survive Horizontal Scaling

The chatbot uses `cachetools.TTLCache` — a Python dict with TTL eviction. This lives in the process's memory. When you run 3 ECS container instances:

```
Container 1: catalog_cache = {whisked_words: [200 products]}
Container 2: catalog_cache = {}   ← cold, will hit MongoDB
Container 3: catalog_cache = {}   ← cold, will hit MongoDB
```

Each container has an independent cache. A cache bust (product update) only evicts the cache in the container that received the HTTP request. The other containers serve stale data until their TTL expires.

---

## 4. The Target Architecture

The goal is **polyglot persistence** — different databases optimized for different workloads, connected by an event streaming layer.

```
┌─────────────────────────────────────────────────────────────────┐
│                        APPLICATION LAYER                        │
│              FastAPI Backend    |    AI Chatbot                 │
└──────────────────┬──────────────────────────┬───────────────────┘
                   │                          │
          OLTP reads/writes          Session + catalog
                   │                          │
┌──────────────────▼──────────────────────────▼───────────────────┐
│                     OPERATIONAL LAYER                           │
│                                                                 │
│   MongoDB Atlas (M10+)          Redis Cluster                   │
│   ─ products, orders            ─ catalog cache (shared)        │
│   ─ users, inventory            ─ session store                 │
│   ─ reviews                     ─ rate limiting counters        │
└──────────────────┬──────────────────────────────────────────────┘
                   │
         Change Streams / Events
                   │
┌──────────────────▼──────────────────────────────────────────────┐
│                      STREAMING LAYER                            │
│                                                                 │
│              AWS Kinesis Data Streams                           │
│   ─ order.placed    ─ product.updated                           │
│   ─ product.viewed  ─ user.registered                           │
└──────────────────┬──────────────────────────────────────────────┘
                   │
         Stream consumers
         (Lambda / Flink)
                   │
┌──────────────────▼──────────────────────────────────────────────┐
│                      ANALYTICS LAYER                            │
│                                                                 │
│   Amazon Redshift (or ClickHouse)                               │
│   ─ fact_orders        ─ dim_products                           │
│   ─ fact_product_views ─ dim_users                              │
│   ─ fact_payments      ─ dim_businesses                         │
│                                                                 │
│   Amazon S3 (raw event archive)                                 │
│   ─ immutable event log, Parquet format                         │
│   ─ queryable via Athena for ad-hoc analysis                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Migration Plan — Phase by Phase

### Phase 1: Fix Hot Queries (Zero Infrastructure Change)

**Timeline: 1–2 weeks. No new services.**

#### 5.1 Pre-compute Trending Scores

Replace the N+1 trending query with a background job:

```python
# New: background_jobs/compute_trending.py
async def refresh_trending_scores(business_id: str):
    """
    Runs every 15 minutes via APScheduler or a cron Lambda.
    Computes trending_score once and writes it to the product document.
    """
    pipeline = [
        {"$match": {"business_id": business_id}},
        {"$unwind": "$items"},
        {"$group": {
            "_id": "$items.product_id",
            "total_ordered": {"$sum": "$items.quantity"}
        }}
    ]
    order_counts = {r["_id"]: r["total_ordered"] 
                    async for r in db.orders.aggregate(pipeline)}
    
    review_pipeline = [
        {"$group": {
            "_id": "$product_id",
            "avg_rating": {"$avg": "$rating"},
            "review_count": {"$sum": 1}
        }}
    ]
    review_stats = {r["_id"]: r 
                    async for r in db.reviews.aggregate(review_pipeline)}
    
    # Single bulk write to update all products at once
    bulk_ops = []
    async for product in db.products.find({"business_id": business_id}):
        pid = product["product_id"]
        total_ordered = order_counts.get(pid, 0)
        stats = review_stats.get(pid, {"avg_rating": 0, "review_count": 0})
        score = (total_ordered * 10) + (stats["avg_rating"] * 5) + (stats["review_count"] * 2)
        bulk_ops.append(UpdateOne(
            {"product_id": pid},
            {"$set": {
                "trending_score": round(score, 1),
                "total_ordered": total_ordered,
                "avg_rating": round(stats["avg_rating"], 1),
                "review_count": stats["review_count"]
            }}
        ))
    
    if bulk_ops:
        await db.products.bulk_write(bulk_ops)
```

The trending endpoint then becomes a simple sorted query — milliseconds instead of seconds.

#### 5.2 Add Compound Indexes

Critical indexes that don't exist yet:

```python
# Run once at startup
await db.products.create_index([("business_id", 1), ("status", 1), ("trending_score", -1)])
await db.product_views.create_index([("user_id", 1), ("business_id", 1), ("last_viewed", -1)])
await db.orders.create_index([("user_id", 1), ("created_at", -1)])
await db.orders.create_index([("business_id", 1), ("created_at", -1)])
await db.reviews.create_index([("product_id", 1)])
```

Without the compound index on products, every catalog query does a collection scan. MongoDB uses only one index per query — `(business_id, status)` alone isn't enough if you're also sorting by `trending_score`.

---

### Phase 2: Shared Cache with Redis

**Timeline: 1 week. One new service (ElastiCache Redis).**

Replace the in-process `TTLCache` with Redis. This solves the multi-container stale cache problem.

```python
# ai-chatbot/services/catalog_query.py — after Redis migration

import redis.asyncio as redis

redis_client = redis.Redis.from_url(os.environ["REDIS_URL"])

async def query_products(db, business_id, filters):
    cache_key = f"catalog:{business_id}:{_filter_hash(filters)}"
    
    # Check Redis first
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Fetch from MongoDB
    result = await _fetch_from_mongo(db, business_id, filters)
    
    # Store in Redis with TTL
    await redis_client.setex(cache_key, 600, json.dumps(result))
    return result

async def evict_catalog_cache(business_id: str):
    # Redis SCAN to find and delete all keys for this business
    async for key in redis_client.scan_iter(f"catalog:{business_id}:*"):
        await redis_client.delete(key)
```

Redis also replaces MongoDB for session storage — it's significantly faster for the high-frequency session lookups that happen on every authenticated request.

---

### Phase 3: Event Streaming

**Timeline: 2–3 weeks. Introduces Kinesis.**

Every significant state change becomes an event. The application emits events; consumers handle downstream effects asynchronously.

```python
# backend/events/emitter.py

import boto3
import json

kinesis = boto3.client("kinesis", region_name="ap-south-1")

async def emit_order_placed(order: dict):
    kinesis.put_record(
        StreamName="multi-business-events",
        Data=json.dumps({
            "event_type": "order.placed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "business_id": order["business_id"],
            "user_id": order["user_id"],
            "order_id": order["order_id"],
            "total": order["total"],
            "items": order["items"]
        }),
        PartitionKey=order["business_id"]  # shard by business
    )

async def emit_product_viewed(user_id: str, product_id: str, business_id: str):
    kinesis.put_record(
        StreamName="multi-business-events",
        Data=json.dumps({
            "event_type": "product.viewed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "product_id": product_id,
            "business_id": business_id
        }),
        PartitionKey=business_id
    )
```

**Why partition by `business_id`?** All events for a business go to the same shard, which preserves ordering within a business — important for analytics that reason about sequences of events.

---

### Phase 4: Analytics Data Warehouse

**Timeline: 3–4 weeks. Introduces Redshift.**

A Kinesis consumer (Lambda or Kinesis Data Firehose) writes events to:
1. **S3** — raw Parquet files, immutable archive, queryable via Athena
2. **Redshift** — star schema for fast analytical queries

**Star Schema Design:**

```sql
-- Fact table: one row per order line item
CREATE TABLE fact_order_items (
    order_item_id   VARCHAR PRIMARY KEY,
    order_id        VARCHAR NOT NULL,
    business_id     VARCHAR NOT NULL,
    user_id         VARCHAR,
    product_id      VARCHAR NOT NULL,
    variant_id      VARCHAR,
    quantity        INT,
    unit_price      DECIMAL(10,2),
    subtotal        DECIMAL(10,2),
    order_date      DATE NOT NULL,        -- partition key
    created_at      TIMESTAMP NOT NULL
)
DISTKEY(business_id)
SORTKEY(order_date, business_id);

-- Fact table: product views (for funnel analysis)
CREATE TABLE fact_product_views (
    view_id         VARCHAR PRIMARY KEY,
    user_id         VARCHAR,
    product_id      VARCHAR NOT NULL,
    business_id     VARCHAR NOT NULL,
    view_date       DATE NOT NULL,
    viewed_at       TIMESTAMP NOT NULL
)
DISTKEY(business_id)
SORTKEY(view_date);

-- Dimension tables
CREATE TABLE dim_products (
    product_id      VARCHAR PRIMARY KEY,
    business_id     VARCHAR,
    product_name    VARCHAR,
    category_id     VARCHAR,
    base_price      DECIMAL(10,2),
    valid_from      TIMESTAMP,
    valid_to        TIMESTAMP          -- SCD Type 2 for price history
);

CREATE TABLE dim_users (
    user_id         VARCHAR PRIMARY KEY,
    email           VARCHAR,
    role            VARCHAR,
    registered_date DATE,
    tier            VARCHAR            -- loyalty tier
);
```

With this schema, previously impossible queries become trivial:

```sql
-- Revenue by business, last 90 days
SELECT 
    d.business_id,
    DATE_TRUNC('week', f.order_date) AS week,
    SUM(f.subtotal) AS revenue,
    COUNT(DISTINCT f.order_id) AS orders,
    COUNT(DISTINCT f.user_id) AS unique_customers
FROM fact_order_items f
JOIN dim_products d ON f.product_id = d.product_id
WHERE f.order_date >= CURRENT_DATE - 90
GROUP BY 1, 2
ORDER BY 1, 2;

-- Conversion funnel: views → orders per product
SELECT
    v.product_id,
    p.product_name,
    COUNT(DISTINCT v.user_id) AS viewers,
    COUNT(DISTINCT o.user_id) AS buyers,
    ROUND(COUNT(DISTINCT o.user_id)::DECIMAL / 
          NULLIF(COUNT(DISTINCT v.user_id), 0) * 100, 2) AS conversion_pct
FROM fact_product_views v
JOIN dim_products p ON v.product_id = p.product_id
LEFT JOIN fact_order_items o 
    ON v.product_id = o.product_id 
    AND v.user_id = o.user_id
    AND o.order_date >= v.view_date
WHERE v.view_date >= CURRENT_DATE - 30
GROUP BY 1, 2
ORDER BY viewers DESC;
```

---

## 6. Interview Talking Points

These are the questions you're likely to get and how to answer them given this system.

---

**"Why did you choose MongoDB over PostgreSQL?"**

> The product catalog is the core data model, and it has genuinely variable structure per business type. A bakery product has flavor, weight, occasion. A different business type might have entirely different attributes. MongoDB lets each product carry its own attribute dict without any schema migration. If the data were more uniform — e.g., a single-category e-commerce store — I'd have chosen PostgreSQL for its stronger consistency guarantees and JOIN support.

---

**"What would break first if you got 10x traffic?"**

> Two things. First, the trending endpoint — it runs N database calls per request, one per product. That's the first thing I'd fix with a pre-computation job. Second, the in-process TTL cache in the AI chatbot — it's per-container, so horizontal scaling defeats it. That gets replaced with a shared Redis cluster.

---

**"How would you handle analytics at scale?"**

> MongoDB is an OLTP store — it's designed for transactional reads and writes on individual documents, not for aggregating millions of rows across collections. I'd introduce an event streaming layer with Kinesis, have consumers write to a columnar store like Redshift in a star schema, and run all analytical queries there. MongoDB stays as the source of truth for live operations; Redshift handles the historical analysis. The migration is purely additive — no downtime, no data loss.

---

**"How do you keep the analytics store in sync with MongoDB?"**

> Two options. The cleaner one is application-level event emission — every significant write (order placed, product updated) emits an event to Kinesis. The event stream is the source of truth for analytics. The other option is MongoDB Change Streams — you can tail the oplog and react to every document change. I'd prefer application-level events because they're intentional and typed; Change Streams are powerful but require more careful filtering to avoid reacting to internal updates.

---

**"What's your indexing strategy?"**

> The most important compound indexes are `(business_id, status)` on products for catalog queries, `(user_id, business_id, last_viewed)` on product_views for the recommendation engine, and `(business_id, created_at)` on orders for dashboard queries. The general rule is: your index should support the query's filter, then its sort, then cover the fields you project — in that order.

---

**"How would you handle the multi-tenancy at DB level?"**

> Currently it's logical isolation — every collection has a `business_id` field and every query filters by it. The next level would be collection-per-tenant (fast but management overhead) or cluster-per-tenant (for large enterprise clients with data residency requirements). For this scale, logical isolation with proper indexing on `business_id` is the right tradeoff.

---

**"What's the consistency model?"**

> Currently eventual consistency, with some gaps. The order + inventory update isn't atomic — there's no MongoDB transaction wrapping them. At this scale it's acceptable, but the fix is straightforward: wrap the order creation, inventory deduction, and payment record creation in a MongoDB multi-document transaction using a session. The event streaming architecture actually makes this cleaner — you emit an `order.placed` event, and consumers handle inventory and payment idempotently.

---

## 7. What "Done" Looks Like

A fully scaled version of this platform would look like:

- **MongoDB Atlas M30+** with replica set — handles all operational reads/writes
- **Redis ElastiCache** — shared catalog cache, session store, rate limiting
- **Kinesis Data Streams** — event bus connecting all services
- **Redshift ra3.xlplus** — analytical warehouse with star schema
- **S3 + Athena** — raw event archive for ad-hoc queries and ML feature stores
- **SageMaker** — ML-based recommendation engine replacing the heuristic scoring

The application code changes are minimal and additive at each phase. No big-bang rewrite.

---

*Last updated: July 2026*
