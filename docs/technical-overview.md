# Jain Industries Multi-Business Platform — Technical Overview
### Interview Reference & In-Depth Discussion Guide

> A comprehensive technical breakdown of every major system, design decision, and engineering tradeoff in this project.

---

## Table of Contents

1. [Project Summary](#1-project-summary)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack — Every Choice Justified](#3-technology-stack--every-choice-justified)
4. [Backend Deep Dive](#4-backend-deep-dive)
5. [Frontend Deep Dive](#5-frontend-deep-dive)
6. [Database Design](#6-database-design)
7. [Authentication & Authorization](#7-authentication--authorization)
8. [Real-Time System (SSE)](#8-real-time-system-sse)
9. [AI Catalog Chatbot Microservice](#9-ai-catalog-chatbot-microservice)
10. [SRE Copilot Agent](#10-sre-copilot-agent)
11. [Payment Integration](#11-payment-integration)
12. [Email Service](#12-email-service)
13. [Recommendation Engine](#13-recommendation-engine)
14. [AWS Infrastructure & CI/CD](#14-aws-infrastructure--cicd)
15. [Testing Strategy](#15-testing-strategy)
16. [Data Architecture at Scale](#16-data-architecture-at-scale)
17. [Interview Q&A — All Topics](#17-interview-qa--all-topics)

---

## 1. Project Summary

**What it is:** A production-grade multi-tenant e-commerce and business management platform for Jain Industries, an umbrella organization operating four distinct businesses:

| Business | Domain | E-Commerce |
|---|---|---|
| Whisked Words | Bakery | Full (cart, checkout, payments, delivery, AI chatbot) |
| Rishabh Garments | Kid's Wear | Catalog + inventory management |
| Jain Jewellers | Jewellery | Catalog + inquiry system |
| Jain Sarees | Saree | Catalog + inventory management |

**What makes it non-trivial:**
- Multi-tenant architecture with isolated data per business under one database
- 5 user roles with granular per-business access control
- Full e-commerce pipeline: cart → checkout → Stripe payment → inventory deduction → delivery assignment → real-time tracking → email notification
- Personalized product recommendations with 3 fallback strategies
- AI chatbot microservice with in-process caching, NLP intent parsing, and session state
- SRE observability agent using AWS Bedrock + Databricks Delta Lake medallion architecture
- 4 separate CI/CD pipelines deploying to AWS ECS + S3/CloudFront

**Scale of the codebase:**
- Backend: ~2,500 lines across 12 route modules
- Frontend: 25+ pages, 3 context providers, custom hooks
- AI Chatbot: separate FastAPI microservice with middleware, caching, session management
- SRE Copilot: ETL pipeline (Splunk → Bronze → Silver → Gold), Bedrock Agent, Slack bot
- Tests: 6 iterations covering 100% of major features

---

## 2. System Architecture

### High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLIENT LAYER                               │
│   React 19 SPA (CRA + Tailwind + Shadcn/UI + Framer Motion)       │
│   Served via S3 + CloudFront (CDN)                                  │
└──────────────────────┬──────────────────────────────────────────────┘
                       │ HTTPS
          ┌────────────┴──────────────┐
          │                           │
   ┌──────▼──────┐             ┌──────▼──────┐
   │  ALB (443)  │             │  ALB (8001) │
   │  Backend    │             │  AI Chatbot │
   └──────┬──────┘             └──────┬──────┘
          │                           │
   ┌──────▼──────┐             ┌──────▼──────┐
   │  ECS Fargate│             │  ECS Fargate│
   │  FastAPI    │             │  FastAPI    │
   │  (port 8001)│             │  (port 8001)│
   └──────┬──────┘             └──────┬──────┘
          │                           │
          └─────────┬─────────────────┘
                    │
           ┌────────▼────────┐
           │  MongoDB Atlas  │
           │  (shared DB)    │
           └─────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                        SRE COPILOT (separate system)                │
│  Splunk → Kinesis → Lambda → Databricks Delta Lake                 │
│  (Bronze → Silver → Gold) → AWS Bedrock Agent → Slack Bot          │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Architectural Decisions

**1. Two separate FastAPI services, one shared MongoDB database.**
The main backend handles all business logic. The AI chatbot is a separate service so it can be scaled, deployed, and versioned independently. They share the same MongoDB because the chatbot reads from `products`, `orders`, `product_views`, and `user_preferences` — all owned by the backend. This avoids data duplication while keeping the services independently deployable.

**2. MongoDB for operational data, no separate caching tier (yet).**
An in-process TTLCache in the chatbot service handles hot catalog reads. This works well for a single container but doesn't survive horizontal scaling — addressed in the data architecture document.

**3. SSE over WebSockets for real-time updates.**
Server-Sent Events are one-directional (server → client), simpler than WebSockets, and supported natively by ALB without protocol negotiation. Given that order tracking only needs server-to-client push, SSE is the right fit.

---

## 3. Technology Stack — Every Choice Justified

### Backend
| Technology | Why |
|---|---|
| **FastAPI** | Native async/await, automatic OpenAPI docs, Pydantic validation, fastest Python web framework in benchmarks |
| **Motor (async MongoDB driver)** | Non-blocking DB calls that work with FastAPI's event loop; no thread blocking |
| **Pydantic v2** | Request/response validation, serialization, enforces schema at the boundary |
| **Python 3.11** | Pattern matching, faster runtime, asyncio improvements |
| **httpx** | Async HTTP client for inter-service calls (chatbot cache-bust, etc.) |
| **Stripe SDK** | PCI-compliant payment sessions without handling raw card data |

### Frontend
| Technology | Why |
|---|---|
| **React 19 (CRA)** | Concurrent features, stable for production, well-supported ecosystem |
| **Tailwind CSS** | Utility-first, no CSS file bloat, consistent spacing/color system |
| **Shadcn/UI + Radix UI** | Unstyled, accessible primitives — you own the styling, Radix handles a11y |
| **Framer Motion** | Declarative animation API, handles mount/unmount transitions cleanly |
| **React Hook Form + Zod** | Schema-driven form validation, minimal re-renders, type-safe |
| **SWR** | Stale-while-revalidate for data fetching — instant loads on navigation |
| **Recharts** | Composable chart library built on D3, integrates cleanly with React |
| **Leaflet + React-Leaflet** | Delivery location map on checkout page |
| **Axios** | HTTP client with interceptor support for auth token injection |

### AI Chatbot Service
| Technology | Why |
|---|---|
| **cachetools TTLCache** | Two-tier in-process cache (catalog cache + query result cache) — eliminates MongoDB reads on hot paths |
| **threading.Lock** | TTLCache is not thread-safe; explicit mutex on every read/write |
| **SHA-256 filter hashing** | Stable cache key for arbitrary filter dicts regardless of key order |
| **OpenAI / LLM backend** | NL intent parsing — converts "I want a chocolate cake under 500" into structured filters |

### Infrastructure
| Technology | Why |
|---|---|
| **AWS ECS Fargate** | Serverless containers — no EC2 management, scales to zero, per-second billing |
| **S3 + CloudFront** | Global CDN for the React SPA, sub-100ms TTFB globally |
| **ALB** | Layer-7 load balancing with health checks, SSE-compatible (unlike API Gateway) |
| **MongoDB Atlas** | Managed MongoDB with automated backups, global clusters, Atlas Search |
| **GitHub Actions** | CI/CD: 4 pipelines (backend, frontend, AI chatbot, SRE copilot), OIDC auth (no stored keys) |

### SRE Copilot
| Technology | Why |
|---|---|
| **Databricks Delta Lake** | ACID transactions on data lake, time-travel, unified batch+streaming |
| **Medallion Architecture** | Bronze (raw) → Silver (cleaned) → Gold (aggregated) separation of concerns |
| **AWS Bedrock (Claude 3.5 Sonnet)** | Managed LLM inference, no GPU management, native AWS IAM integration |
| **Bedrock Knowledge Base + OpenSearch** | RAG over runbooks and postmortems, semantic chunking |
| **Kinesis Data Streams** | Event streaming from app to analytics pipeline |

---

## 4. Backend Deep Dive

### Route Module Structure

The backend is a single FastAPI app with routes split across 8 files:

```
server.py                  — Core: auth, businesses, products, inventory (~1200 lines)
ecommerce_routes.py        — Cart: add/update/remove, checkout flow
order_routes.py            — Order CRUD, my orders
order_management_routes.py — Admin: confirm/cancel/assign delivery agent
custom_order_routes.py     — Custom cake order workflow
payment_routes.py          — Stripe session creation, webhook, status
additional_routes.py       — Reviews, loyalty points, subscriptions, categories
location_routes.py         — Delivery location lookup (geocoding)
sse_routes.py              — SSE event stream + publish_event helper
email_service.py           — Plug-and-play email provider abstraction
```

### Request Lifecycle

```
Request arrives
    → CORS middleware (validates Origin header)
    → Route handler
        → get_current_user() dependency (if protected)
            → reads session_token from cookie or Authorization header
            → db.user_sessions.find_one()
            → checks expiry
            → db.users.find_one()
        → require_role() dependency (if role-restricted)
            → checks user["role"] against allowed_roles list
        → check_business_access() (if business-scoped)
            → super_admin bypasses, others checked against business_access array
        → business logic
        → MongoDB operation
    → Pydantic response serialization
    → JSON response
```

### Idiomatic Patterns Used

**Dependency injection for auth:**
```python
# Every protected route takes a dependency — clean separation of concerns
@api_router.post("/orders/create")
async def create_order(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
```

**Soft deletes everywhere:**
Products, orders, and inventory are never hard-deleted. Status is set to `inactive`. This preserves referential integrity — if an order references a product, that product document still exists and historical data remains queryable.

**Upsert pattern for idempotent writes:**
The `product_views`, `user_preferences`, and `cart` collections all use `update_one(..., upsert=True)`. A second `track_product_view` call for the same user+product increments `view_count` instead of creating a duplicate document.

**Best-effort cache invalidation:**
When a product is updated, the backend fires a `DELETE /cache/business/{business_id}` to the AI chatbot service. It uses `httpx` with a 2-second timeout and swallows all exceptions. This is intentional — a product update should never fail because the chatbot is unreachable.

```python
try:
    async with httpx.AsyncClient(timeout=2.0) as client_http:
        await client_http.delete(f"{chatbot_url}/cache/business/{business_id}")
except Exception:
    pass  # best-effort, fire and forget
```

---

## 5. Frontend Deep Dive

### State Management Philosophy

No Redux. The app uses **three React Context providers**:

```
AuthContext     — current user, login/logout, session hydration
BusinessContext — currently selected business (URL-driven)
CartContext     — cart items, totals, add/update/remove actions
```

This is intentional. Redux adds overhead for a problem these three contexts solve cleanly. The cart context syncs with the backend on every mutation — there's no local-only cart state that could diverge from the server.

### Page Architecture

Every protected page follows the same pattern:
1. `useAuth()` to get `currentUser` and redirect if unauthenticated
2. `require_role` check — if wrong role, redirect to appropriate dashboard
3. Initial data fetch on mount via `useEffect` + `axios`
4. Optimistic UI updates (change local state immediately, sync to backend asynchronously)

### Component Hierarchy

```
App.js
  ├── AuthProvider
  │     └── BusinessProvider
  │           └── CartProvider
  │                 └── Router
  │                       ├── Public routes (no auth required)
  │                       │     ├── Landing
  │                       │     ├── BusinessHome (product catalog per business)
  │                       │     └── ProductCatalog
  │                       │
  │                       ├── Customer routes (auth required)
  │                       │     ├── CartPage
  │                       │     ├── CheckoutPage
  │                       │     ├── MyOrdersPage
  │                       │     ├── OrderTrackingPage (SSE consumer)
  │                       │     ├── LoyaltyPage
  │                       │     ├── SubscriptionsPage
  │                       │     └── CustomCakeOrderPage
  │                       │
  │                       ├── Admin routes (business_admin + super_admin)
  │                       │     ├── AdminOrdersDashboard
  │                       │     ├── BusinessAdminDashboard
  │                       │     └── StaffDashboard
  │                       │
  │                       └── Delivery routes
  │                             └── DeliveryDashboard
```

### Key Frontend Patterns

**Real-time notification bell:**
`BakeryNavbar` opens an SSE connection (`/api/sse/events`) on mount. When the server pushes a `notification` event, the bell icon increments its unread count. The connection is managed in a custom hook and torn down on unmount.

**Order tracking timeline:**
`OrderTrackingPage` displays a vertical timeline of order status changes. It subscribes to SSE and re-renders the timeline whenever an `order_update` event arrives for that order ID — no polling required.

**Multi-step checkout:**
The checkout form is implemented as a local state machine: step 1 (delivery info) → step 2 (payment selection) → step 3 (confirm). Each step validates before advancing. The Stripe redirect happens at the payment step — success returns to `/order-success?order_id=xxx`.

**Framer Motion usage:**
Page transitions use `AnimatePresence` with `key={location.pathname}`. Product cards use `whileHover` and `whileTap` for tactile feedback. The cart drawer slides in from the right using `x` transform animation.

---

## 6. Database Design

### Collections and Their Purpose

```
users              — All user accounts: roles, business_access array, Google OAuth data
user_sessions      — Auth session tokens with 7-day TTL index
businesses         — 4 business documents, static after seeding
products           — Product catalog with flexible 'attributes' dict per business type
categories         — Product categories scoped to each business
inventory          — Per-variant stock levels with movement history
orders             — Full order lifecycle: items, delivery_info, payment status, order status
cart               — Temporary cart documents (no TTL — cleaned on checkout/logout)
custom_orders      — Custom cake order workflow: pending_quote → quoted → confirmed
reviews            — Product reviews, 1-5 rating, linked to product_id and user_id
loyalty_points     — Per-user points balance, tier, and transaction history
subscriptions      — Recurring delivery schedules (daily/weekly/monthly)
product_views      — User-product view events (upserted, tracks view_count and last_viewed)
user_preferences   — Pre-computed recommendation vector with 12-hour TTL
chat_sessions      — AI chatbot conversation state with 30-minute TTL
notifications      — In-app notification documents per user
payment_transactions — Stripe/Razorpay transaction audit trail
```

### Schema Design Principles

**Custom string IDs, not MongoDB ObjectIds:**
Every document uses a `{type}_{uuid_hex_12}` ID pattern (e.g., `prod_a3f2c1b4d5e6`). MongoDB's `_id` is never returned in API responses. This makes IDs predictable, URL-safe, and independent of MongoDB's internal format.

**Flexible attributes dict on products:**
Rather than separate collections per business type, all products share one collection. Business-specific properties live in an `attributes` dict:
```python
# Bakery product
"attributes": {"flavor": "chocolate", "weight": "500g", "allergens": ["gluten"]}

# Jewellery product
"attributes": {"metal_type": "Gold", "purity": "22K", "weight": "25.5g"}
```
This is the defining reason MongoDB was chosen. An RDBMS would require either EAV tables or separate tables per business type.

**TTL indexes instead of cron jobs:**
Three collections use MongoDB TTL indexes for automatic cleanup:
- `user_sessions` — expires 7 days after `expires_at`
- `user_preferences` — expires when `expires_at` is reached (expireAfterSeconds=0 means "delete when the field time arrives")
- `chat_sessions` — expires 30 minutes after `last_active`

**Compound indexes on query patterns:**
The most important indexes in the system:
```python
# Catalog queries — the most frequent read
(business_id, status)       # on products
(business_id, category_id)  # on products

# Recommendation engine
(user_id, business_id, last_viewed DESC)  # on product_views
(user_id, created_at DESC)               # on orders

# Admin dashboard
(business_id, created_at DESC)           # on orders
(business_id, order_status)              # on orders

# TTL cleanup
(expires_at, 1) expireAfterSeconds=0     # on user_preferences
(last_active, 1) expireAfterSeconds=1800 # on chat_sessions
```

---

## 7. Authentication & Authorization

### Auth Flow

The platform uses **Google OAuth** with a custom session layer. It is not a third-party auth-as-a-service — the backend owns the session.

```
User clicks "Login with Google"
    → Frontend redirects to Google OAuth
    → Google redirects back with ID token
    → Frontend sends ID token to POST /api/auth/google
    → Backend: id_token.verify_oauth2_token(token, Request(), client_id)
        → Verifies signature against Google's public keys
        → Extracts email, name, picture from JWT claims
    → Backend: find or create user document
    → Backend: create session document with 7-day expiry
    → Backend: set httpOnly session cookie
    → Backend: compute preference_vector (background, on login)
    → Return user object + recommendations
```

**Why verify the ID token on the backend?**
The frontend cannot verify the signature — it doesn't have Google's public keys. If the frontend trusted the token without backend verification, any crafted JWT would work. Backend verification using `google-auth` library is the correct pattern.

**Cookie vs. Bearer token:**
Both are supported. The backend reads `session_token` from the cookie first, then falls back to `Authorization: Bearer` header. The cookie path handles browser-based requests. The header path handles mobile clients and API testing tools.

**Cookie security settings:**
```python
response.set_cookie(
    key="session_token",
    httponly=True,      # not accessible via JS — prevents XSS token theft
    secure=_is_production(),   # HTTPS only in prod, allows HTTP in dev
    samesite="none" if _is_production() else "lax",  # cross-origin in prod
    max_age=7 * 24 * 60 * 60
)
```
`SameSite=None` with `Secure=True` is required for cross-origin cookies (frontend on CloudFront, backend on ECS behind ALB have different domains).

### RBAC Implementation

Five roles with hierarchical access:

```
super_admin      — full access to everything
business_admin   — full access within assigned businesses
staff            — limited write access within assigned businesses
delivery_agent   — can update delivery status on their assigned orders
customer         — can place orders, view own data
```

Two levels of authorization:
1. **Role check** — `require_role(["super_admin", "business_admin"])` applied as a FastAPI dependency
2. **Business scope check** — `check_business_access(user, business_id)` inside the route handler

Super admin bypasses the scope check entirely. This means adding a new business doesn't require any permission updates for the super admin account.

---

## 8. Real-Time System (SSE)

### Architecture

```
Order status changes (admin action or payment webhook)
    → backend: publish_event(user_id, "order_update", data)
        → finds all asyncio.Queue objects for that user_id
        → puts JSON payload on each queue
    → SSE event stream handler
        → reads from queue with 30-second timeout
        → yields "data: {payload}\n\n" to the HTTP response
    → Browser EventSource API
        → fires message event
        → React component re-renders (order timeline updates)
```

### In-Memory Event Bus

```python
# In-memory subscriber registry
_subscribers: dict[str, list[asyncio.Queue]] = {}
```

Each user can have multiple SSE connections (e.g., different browser tabs). Each connection gets its own `asyncio.Queue`. When an event is published for a user, it's pushed to all their queues.

**Heartbeat mechanism:**
Every 30 seconds with no events, the server sends a comment-only line (`: heartbeat\n\n`). This keeps the TCP connection alive through proxies and load balancers that have idle timeouts.

**ALB configuration for SSE:**
ALB idle timeout must be increased to 300 seconds (`modify-load-balancer-attributes idle_timeout=300`). Default is 60 seconds, which would kill live tracking connections.

**Known limitation — multi-worker deployment:**
The subscriber registry lives in Python process memory. With 2 ECS tasks, a user's order update published in Task 1 won't reach SSE connections in Task 2. The fix is Redis Pub/Sub — each task subscribes to a Redis channel and forwards events to its local subscribers. This is listed as a P1 item.

---

## 9. AI Catalog Chatbot Microservice

### Architecture

```
POST /chat/message
    → RateLimiterMiddleware (per-IP, sliding window)
    → SanitiserMiddleware (input sanitization, length limits)
    → chat router
        → load_session() or create_session()
        → get_user_preferences() (personalization signal)
        → NLProcessor.parse_intent(message)
            → LLM call → structured intent + filters
        → dispatch by intent:
            "search"    → query_products(db, business_id, filters)
            "recommend" → recommend(db, business_id, filters, user_context)
            "compare"   → compare(db, business_id, product_ids)
            "price"     → query_products with price filters
        → format response
        → save_session() (with turn truncation)
        → return JSON
```

### Two-Tier Cache System

The chatbot implements a two-tier in-process cache that reduces MongoDB reads by ~90% on warm paths:

**Tier 1: `catalog_cache`** — full active product list per business
- 50 slots (one per business), 10-minute TTL
- Populated on first cache miss for a business
- All in-memory filter matching runs against this

**Tier 2: `query_cache`** — filtered result sets
- 500 slots, 60-second TTL
- Key: `"{business_id}:{sha256_of_filters}"`
- Filter dict is serialized with `sort_keys=True` before hashing — ensures `{"a":1, "b":2}` and `{"b":2, "a":1}` produce the same cache key

**Lookup order:**
```
query_cache hit? → return immediately
catalog_cache hit? → apply filters in Python → store in query_cache → return
both miss → fetch from MongoDB → store in catalog_cache → apply filters → store in query_cache → return
```

**Cache invalidation:**
When the backend updates a product, it calls `DELETE /cache/business/{business_id}` on the chatbot. This triggers `evict_catalog_cache()` which removes the business from `catalog_cache` AND scans `query_cache` for all keys with that business prefix.

**Thread safety:**
`cachetools.TTLCache` is explicitly not thread-safe. Every read and write is wrapped in `threading.Lock`. This is critical because FastAPI uses an async event loop but Motor callbacks can run across threads in some configurations.

### Session Management

Each conversation is a `chat_sessions` document with:
- `turns` — conversation history (user + assistant messages)
- `active_filters` — filters currently active from previous turns (stateful filtering)
- `recommendation_rationales` — why each product was recommended (for explainability)

**Turn truncation rule:**
When `len(turns) > 20`, the session keeps `turns[0]` (system prompt) + `turns[-10:]` (10 most recent). This prevents unbounded context growth while preserving conversation continuity.

### Personalization Priority

When generating recommendations, the chatbot resolves personalization signals in this order:
1. `user_preferences` document in MongoDB (pre-computed on login, 12h TTL)
2. `preference_summary` sent in the request body
3. Live lookup of `product_views` (≤20) and `orders` (≤10) — fallback when no cached vector

The preference vector contains `top_flavors`, `top_occasions`, and `price_range` derived from weighted view+order history (orders weighted 2x over views).

---

## 10. SRE Copilot Agent

This is a completely separate system — an intelligent Site Reliability Engineering assistant. It lives in `sre-copilot/` and has its own deployment pipeline.

### Architecture Overview

```
Splunk (log source)
    → Kinesis Data Streams (event ingestion)
    → Lambda consumer / Databricks notebook
        → Bronze Layer (raw logs, Delta table)
        → Silver Layer (parsed, PII-redacted, categorized)
        → Gold Layer (hourly aggregates, health scores, pattern clusters)
    → AWS Bedrock Agent (Claude 3.5 Sonnet)
        → Lambda Action Group (queries Gold tables via Databricks SQL)
        → Bedrock Knowledge Base (runbooks + postmortems via OpenSearch RAG)
    → Slack Bot (Lambda event handler)
        → SRE engineer asks: "@SRE-Copilot why is checkout-service failing?"
        → Agent responds with structured analysis
```

### Medallion Architecture (Data Quality Layers)

**Bronze — Raw Ingestion:**
Raw Splunk log records, no transformation. Partitioned by `date(_time)`. Only deduplicated by batch ID. The goal is to never lose data at this layer.

**Silver — Cleaned and Structured:**
- PII redacted (IPs → `[IP]`, account numbers → `[ACCOUNT]`, tokens → `[REDACTED]`)
- Fields extracted via regex (service name, region, log level, error type, trace ID)
- Error categorized into: `timeout`, `connection_refused`, `out_of_memory`, `null_pointer`, `auth_failure`, `circuit_breaker`, `internal_error`, `other`
- Deduplicated by SHA-256 of `(service, timestamp, raw_message)`

**Gold — Aggregated and Queryable:**
Two key tables:
- `gold.error_summaries` — hourly error counts per service/region, baseline comparison (vs. 7-day average), anomaly flag, natural language summary
- `gold.service_health` — composite health score (0-100), status: healthy/degraded/critical

The anomaly detection is a simple but effective signal: `error_rate_vs_normal > 2.0` flags an hour as anomalous. The `nl_summary` column is a pre-generated string like `"checkout-service: 143 errors (285% above normal), top: TimeoutException"` — the LLM can include this directly in its response without needing to reason about the numbers.

### Agent Tool Priority

The Bedrock Agent is instructed to follow this tool priority:
1. `query_service_health` — overall status first
2. `query_error_summary` — what's wrong if degraded
3. `query_error_patterns` — clustered view of repeated errors
4. `query_dynamic_knowledge` — has this been seen before? known fix?
5. Bedrock KB — runbook lookup
6. `search_splunk_logs` — emergency fallback ONLY (slow, rate-limited)

This ordering is intentional. Gold tables answer 90% of questions in milliseconds. Splunk queries can take 30-60 seconds. The agent's system prompt explicitly tells it when to use each tool.

---

## 11. Payment Integration

### Stripe Flow

```
Customer clicks "Pay with Stripe"
    → POST /api/payments/stripe/create-session
        → Stripe API: create checkout.session with line items
        → Return session_id + redirect URL
    → Frontend redirects to Stripe hosted checkout
    → Customer enters card details on Stripe's domain (PCI scope outside our app)
    → Stripe redirects to /order-success?order_id=xxx
    → Frontend: POST /api/payments/stripe/verify-payment
        → Stripe API: retrieve session by session_id
        → Check payment_status == "paid"
        → Update order.payment_status = "paid"
        → Deduct inventory (atomic-ish — single MongoDB write)
        → Trigger SSE notification to user
        → Send order confirmation email
```

**Why Stripe Checkout (hosted page) vs. Stripe Elements (embedded form)?**
Hosted checkout keeps PCI scope minimal. Stripe handles card data entirely — our servers never see card numbers, CVVs, or expiry dates. Stripe Elements would require SAQ A-EP compliance; hosted checkout is SAQ A.

**Razorpay:**
Integrated at the route level (`payment_routes.py`) but requires live API keys to activate. The structure mirrors the Stripe flow — create order → redirect → verify webhook.

**COD (Cash on Delivery):**
No payment gateway call. Order is created with `payment_status: "pending"` and `payment_method: "cod"`. The admin confirms payment on delivery via the admin dashboard.

---

## 12. Email Service

### Plug-and-Play Architecture

The email service uses a strategy pattern — a common `BaseEmailProvider` interface implemented by 5 concrete providers:

```python
class BaseEmailProvider(ABC):
    @abstractmethod
    async def send(self, to: str, subject: str, html: str, sender: str) -> bool: ...
```

Implemented by: `ResendProvider`, `SendGridProvider`, `BrevoProvider`, `MailgunProvider`, `SMTPProvider`

**Zero-config activation:** Set `EMAIL_PROVIDER=resend` and `EMAIL_API_KEY=re_xxx` in `.env`. No code changes required. The factory function `get_email_provider()` reads these at runtime and instantiates the correct class.

**Graceful no-op when unconfigured:** If `EMAIL_PROVIDER` is empty, `send_email()` logs a skip message and returns `False`. Orders complete normally — email is a side effect, not part of the transaction.

**All providers are async:** Even SMTP (which is synchronous by nature) runs in `asyncio.to_thread()` — it never blocks the FastAPI event loop.

This design means you can swap from Resend to SendGrid in production without deploying code — just update the environment variable.

---

## 13. Recommendation Engine

The platform has a layered recommendation system operating at two levels: the main backend and the AI chatbot.

### Backend Recommendation System

The `/products/recommended/{business_id}` endpoint implements 3 strategies in order:

**Strategy 1 — Category Match (first choice):**
Finds products in the same categories the user has viewed or ordered, excluding products they've already bought. This is the most relevant signal — if you viewed chocolate cakes, show other chocolate products.

**Strategy 2 — Collaborative Filtering (second choice):**
"What did other users who bought the same things also buy?" Implemented as a MongoDB aggregation pipeline:
```python
[
    {"$match": {"items.product_id": {"$in": list(ordered_ids)}}},
    {"$match": {"user_id": {"$ne": user_id}}},     # other users
    {"$unwind": "$items"},
    {"$match": {"items.product_id": {"$nin": list(ordered_ids)}}},  # products you don't have
    {"$group": {"_id": "$items.product_id", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}},
    {"$limit": limit}
]
```

**Strategy 3 — Discovery (third choice):**
Products the user hasn't interacted with yet. Good for new catalog exploration.

**Fallback — Top Rated:**
When the user has no history, return products sorted by `avg_rating` desc then `review_count` desc.

### Preference Vector (Login-Time Pre-Computation)

On every login, the backend computes a `preference_vector`:
```python
{
    "top_flavors": ["chocolate", "vanilla"],    # from views + orders
    "top_occasions": ["birthday", "wedding"],
    "price_range": {"min": 400, "max": 1200}
}
```
Orders are weighted 2x over views (an actual purchase is a stronger signal than a browse). The vector is stored in `user_preferences` with a 12-hour TTL. On next login, it's recomputed. The AI chatbot reads this vector to enrich recommendation filters automatically.

### Trending Products — The Known Problem

The current trending implementation runs an aggregation pipeline per product:
```python
for product in products:  # O(n) DB calls
    order_agg = await db.orders.aggregate(pipeline).to_list(1)
    reviews = await db.reviews.find(...).to_list(500)
```

This is N+1 queries. At 100 products, that's 200 DB round-trips per request. The correct fix is to pre-compute `trending_score`, `total_ordered`, `avg_rating`, and `review_count` on the product document via a background job running every 15 minutes. See `docs/data-architecture-at-scale.md` for the implementation.

---

## 14. AWS Infrastructure & CI/CD

### Deployment Architecture

```
Route 53
    → CloudFront (CDN + SSL termination)
        → S3 (React SPA — static files)
        → ALB (API traffic — /api/* bypasses CloudFront cache)
            → ECS Fargate (FastAPI backend)
            → ECS Fargate (AI Chatbot service)
                → MongoDB Atlas (external, VPC peering optional)
```

### Four CI/CD Pipelines

Each major component has an independent GitHub Actions workflow:

| Workflow | Trigger | Steps |
|---|---|---|
| `deploy-backend.yml` | Push to `backend/**` or `Dockerfile` | Test → ECR push → ECS deploy → wait for stable |
| `deploy-frontend.yml` | Push to `frontend/**` | Install → build → S3 sync → CloudFront invalidation |
| `deploy-ai-chatbot.yml` | Push to `ai-chatbot/**` | Test → ECR push → ECS deploy |
| `deploy-sre-copilot.yml` | Push to `sre-copilot/**` | Deploy Databricks notebooks + Lambda functions |

**OIDC authentication (no stored AWS keys):**
All pipelines use `aws-actions/configure-aws-credentials@v4` with `role-to-assume`. GitHub's OIDC provider issues a short-lived token at runtime. No `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` is stored in GitHub Secrets. This is the current AWS best practice.

**Deploy with wait:**
```yaml
aws ecs update-service --force-new-deployment
aws ecs wait services-stable  # blocks until health checks pass
```
If the new container fails health checks, the pipeline stays in `waiting` state and the old tasks continue serving traffic. The deploy only completes when the new tasks are healthy.

### Cost Profile

| Service | Config | Monthly |
|---|---|---|
| S3 | Frontend hosting | ~$1 |
| CloudFront | 100 GB transfer | ~$12 |
| ECS Fargate | 2x (0.5 vCPU, 1 GB) | ~$30 |
| ALB | Application LB | ~$22 |
| MongoDB Atlas | M10 dedicated | ~$57 |
| Route 53 | Hosted zone | ~$1 |
| CloudWatch | Logs + metrics | ~$5 |
| **Total** | | **~$128/month** |

Dev/staging can run with Atlas M0 (free), 1 Fargate task, and share the ALB for ~$25/month.

---

## 15. Testing Strategy

### Test Coverage by Iteration

| Iteration | Feature | Backend | Frontend |
|---|---|---|---|
| 1 | Core e-commerce, auth, RBAC | 96.5% | 100% |
| 2 | Trending products | 100% | 100% |
| 3 | Recently Viewed + Recommendations | 100% | 100% |
| 4 | Bakery UI redesign | 100% | 95% |
| 5 | Order Tracking & Delivery | 100% (20/20) | 100% |
| 6 | Email/SSE/Auto-assign delivery | 100% (13/13) | 100% |

### Test Files

```
backend/tests/
  test_api_comprehensive.py          — Auth, RBAC, product CRUD, inventory
  test_trending_feature.py           — Trending score computation
  test_recently_viewed_recommended.py — Recommendation strategies
  test_order_management.py           — Order lifecycle, status transitions
  test_iter6_sse_email_autoassign.py — SSE events, email triggers, delivery assignment

ai-chatbot/tests/
  test_properties.py                 — Property-based tests: cache correctness, filter consistency
  test_rate_limiter.py               — Rate limiter sliding window behavior
```

### Property-Based Testing in the Chatbot

The chatbot uses property-based testing (`test_properties.py`) to verify:
- **Cache correctness**: if `query_products(filters)` returns result X from MongoDB, `query_products(same_filters)` from cache must also return X
- **Filter consistency**: in-memory filter matching in `_matches_filters()` must be equivalent to the MongoDB query for the same filters
- **Filter hash stability**: `_filter_hash({"a":1,"b":2}) == _filter_hash({"b":2,"a":1})`

These properties catch bugs that unit tests with fixed inputs would miss.

---

## 16. Data Architecture at Scale

See `docs/data-architecture-at-scale.md` for the full migration plan. Summary:

**Current state:** MongoDB for all OLTP operations. In-process TTLCache for hot reads. Functional, but has clear ceilings.

**Phase 1 (no new infra):** Pre-compute trending scores via background job. Add compound indexes. Fixes the N+1 problem.

**Phase 2 (Redis):** Replace in-process TTLCache with ElastiCache Redis. Shared cache across all container instances. Also handles rate limiting and session storage.

**Phase 3 (Kinesis):** Event streaming. Every order, view, and user action becomes a Kinesis event. Enables analytics decoupled from OLTP.

**Phase 4 (Redshift):** Star schema analytical warehouse. `fact_order_items`, `fact_product_views`, `dim_products`, `dim_users`. Revenue reports, conversion funnels, cohort analysis — all become simple SQL.

---

## 17. Interview Q&A — All Topics

### System Design

**"Walk me through the overall architecture."**
> It's a multi-tenant e-commerce platform with two FastAPI services sharing one MongoDB instance. The main backend handles all business logic and transactions. The AI chatbot is a separate service — same database, independent deployment — because it has different scaling characteristics and its own caching layer. The frontend is a React SPA served from S3+CloudFront. Everything runs on AWS ECS Fargate with four independent CI/CD pipelines. The SRE component is a completely separate observability system built on Databricks and Bedrock.

**"How does multi-tenancy work?"**
> Logical isolation. Every document in every collection carries a `business_id` field. Every query filters by it. Super admin queries see all businesses; everyone else gets data filtered to their business access list, which is an array on their user document. This is the right tradeoff for this scale — database-per-tenant would add operational overhead with no real benefit at single-digit tenants.

**"What happens when a user places an order?"**
> The frontend POSTs to `/api/orders/create`. The backend validates inventory availability, creates the order with `payment_status: "pending"`, and reserves the inventory (`quantity.reserved += quantity`). Then it creates a Stripe checkout session and returns the redirect URL. The user completes payment on Stripe's hosted page. Stripe redirects back. The frontend calls `/api/payments/stripe/verify-payment`, the backend retrieves the Stripe session, confirms it's paid, sets `payment_status: "paid"`, deducts the reserved inventory, publishes an SSE event, and sends the confirmation email. Then the admin confirms the order from their dashboard, which triggers automated delivery agent assignment.

**"How does automated delivery assignment work?"**
> On order confirmation, the system finds available delivery agents who have a `base_pincode` set. It scores each agent by pincode proximity — exact 6-digit match scores highest, then 4-digit prefix match, then 2-digit prefix match. Ties are broken by fewest active orders. The nearest available agent gets assigned. Admin can manually reassign at any time.

---

### Database

**"Why MongoDB over PostgreSQL?"**
> The product catalog has fundamentally different structures across business types. A bakery product has flavor, weight, and allergens. A jewellery product has purity, stone type, and hallmark. In PostgreSQL you'd either use a generic EAV table (painful to query) or separate tables per business type (schema migrations every time you add a business). MongoDB's document model handles this naturally. If the data were uniform, PostgreSQL would be better.

**"What indexes do you have?"**
> The most critical ones: `(business_id, status)` on products for catalog queries, `(user_id, business_id, last_viewed DESC)` on product_views for recommendations, `(business_id, created_at DESC)` on orders for the admin dashboard. TTL indexes on `user_preferences`, `user_sessions`, and `chat_sessions` for automatic expiry. The key principle: index should support the query's filter, then its sort, then cover the projected fields.

**"Is your data consistent? What about transactions?"**
> The order + inventory update isn't wrapped in a MongoDB transaction currently. It's two sequential writes — create order, then update inventory. If the server dies between them, you get an order without inventory deduction. At this scale it's an acceptable risk, and the fix is straightforward: wrap both writes in a Motor session with `start_transaction()`. This is on the backlog. Payment verification is idempotent — verifying the same Stripe session twice won't create a duplicate record because we check for an existing `payment_id` first.

---

### Backend

**"How do you handle auth in FastAPI?"**
> It's dependency injection. `get_current_user` is an async function that reads the session token from the cookie or Authorization header, looks it up in `user_sessions`, checks expiry, then returns the user document. Routes that need auth declare it as a dependency via `Depends(get_current_user)`. Routes that need role restriction use `Depends(require_role(["super_admin"]))`. FastAPI resolves these before calling the route handler.

**"How does the chatbot cache invalidation work?"**
> When the backend updates a product, it sends a `DELETE /cache/business/{business_id}` to the chatbot service. The chatbot removes that business from both `catalog_cache` and all matching `query_cache` entries (scanned by key prefix). The call is fire-and-forget with a 2-second timeout and swallowed exceptions — a product update shouldn't fail because the chatbot is unreachable.

**"What's the email service pattern?"**
> Strategy pattern. There's a `BaseEmailProvider` abstract class with a single `send()` method. Five concrete implementations: Resend, SendGrid, Brevo, Mailgun, SMTP. A factory reads `EMAIL_PROVIDER` at runtime and instantiates the right class. All providers are async — SMTP runs in `asyncio.to_thread()` to avoid blocking. If `EMAIL_PROVIDER` is empty, the factory returns `None` and email sending is silently skipped. You can swap providers by changing one environment variable.

---

### Frontend

**"Why no Redux?"**
> Redux solves a distribution problem — sharing state between components that don't have a parent-child relationship. In this app, three contexts solve that cleanly: AuthContext for user state, BusinessContext for selected business, CartContext for cart items. Adding Redux would mean action types, reducers, and selectors for problems that a single Context + useReducer handles in 50 lines. The complexity ceiling for this app doesn't require it.

**"How does the real-time order tracking work?"**
> The `OrderTrackingPage` opens an `EventSource` connection to `/api/sse/events`. The server keeps that HTTP connection open. When an admin updates order status, the backend calls `publish_event(user_id, "order_update", {...})` which finds the user's active queue and pushes the event. The SSE stream delivers it to the browser, where React re-renders the timeline. No polling, no WebSocket handshake overhead.

---

### Infrastructure

**"How do your CI/CD pipelines work?"**
> Four independent GitHub Actions workflows. Each one tests, builds, and deploys its own service. Backend: run pytest → build Docker → push to ECR → `ecs update-service` → `ecs wait services-stable`. Frontend: `yarn build` → `s3 sync` → CloudFront invalidation. Auth is OIDC — no stored AWS keys, GitHub gets a short-lived token at runtime. The `wait services-stable` step means the pipeline only succeeds when the new task passes health checks — if it fails, the old task keeps running.

**"What would you change about the infrastructure?"**
> Two things. First, move secrets from ECS environment variables to Secrets Manager with IAM-based access — right now they're plaintext in the task definition. Second, add a Redis ElastiCache cluster to replace the in-process TTLCache in the chatbot. Right now every container has an independent cache, which means a product update might leave stale data in non-bust containers for up to 10 minutes.

---

### SRE Copilot

**"Explain the medallion architecture."**
> Bronze is raw ingestion — Splunk logs land here unmodified, partitioned by date. Silver is where we clean and structure the data: extract fields via regex, redact PII, categorize error types. Gold is pre-aggregated for the agent — hourly error counts per service, baseline comparison against the 7-day average, anomaly flags, health scores. The agent queries Gold first because it's fast and pre-computed. Raw Splunk queries are a last resort — they're slow and have rate limits.

**"How does the Bedrock agent decide which tool to use?"**
> It follows an explicit investigation protocol in its system prompt: start with `query_service_health`, if degraded check `query_error_summary`, then `query_error_patterns`, check dynamic knowledge and runbooks, only fall back to Splunk if Gold data contradicts the user's report. The system prompt also tells it to always disclose data freshness ("based on data from X minutes ago") and confidence level. This makes the agent's behavior predictable and debuggable.

---

*Last updated: July 2026*
