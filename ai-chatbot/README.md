# AI Catalog Chatbot — `ai-chatbot/`

An independently deployable Python/FastAPI microservice that powers the AI-assisted product-discovery chatbot on the multi-business website. It accepts natural-language queries from the React `Chat_Widget`, calls an LLM to extract intent and filters, and returns ranked product results from the shared MongoDB catalog.

---

## What It Is

The `ai-chatbot/` service is a standalone FastAPI application that:

- Exposes a `POST /chat/message` endpoint consumed by the frontend `Chat_Widget`.
- Uses OpenAI or Anthropic to parse user intent and extract structured filters.
- Queries the existing MongoDB `products` collection (read-only access to shared data).
- Maintains per-session conversation context in the `chat_sessions` collection.
- Enforces role-based access control (admins, staff, and prime customers only).
- Applies input sanitisation and per-IP rate limiting (30 req / 60 s).

It runs entirely independently — no dependency on the `backend/` server at runtime.

---

## Setup

### 1. Install dependencies

```bash
cd ai-chatbot
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Then edit `.env` and fill in your values (see the table below).

### 3. Run the service

```bash
uvicorn main:app --reload --port 8001
```

The service will be available at `http://localhost:8001`.

---

## Required Environment Variables

| Variable | Description | Example |
|---|---|---|
| `MONGO_URL` | MongoDB connection string (same as `backend/`) | `mongodb://localhost:27017` |
| `DB_NAME` | MongoDB database name (same as `backend/`) | `multi_business_db` |
| `LLM_PROVIDER` | LLM provider to use: `openai` or `anthropic` | `openai` |
| `LLM_API_KEY` | API key for the chosen LLM provider | `sk-...` |
| `LLM_MODEL` | Model name to call | `gpt-4o-mini` |
| `LLM_TIMEOUT_SECONDS` | HTTP timeout (seconds) for LLM calls | `8` |
| `CORS_ORIGINS` | Comma-separated list of allowed CORS origins | `http://localhost:3000` |
| `PORT` | Port the service listens on | `8001` |
| `CHATBOT_SERVICE_URL` | Public URL of this service (used by `backend/` for cache-bust calls) | `http://localhost:8001` |

---

## API Contract

### `POST /chat/message`

Processes a user message and returns a structured chatbot response.

**Request body** (`application/json`):

```json
{
  "session_id": "uuid-v4-or-null",
  "business_id": "biz_abc123",
  "message": "show me chocolate cakes under ₹500",
  "user_id": "user_xyz",
  "preference_summary": {
    "top_flavors": ["chocolate"],
    "top_occasions": ["birthday"],
    "price_range": { "min": 200, "max": 800 }
  }
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `session_id` | `string` (UUID v4) | No | Omit or `null` to start a new session |
| `business_id` | `string` | **Yes** | Scopes catalog queries to a single business |
| `message` | `string` | **Yes** | Max 500 characters |
| `user_id` | `string` | No | Enables personalised recommendations |
| `preference_summary` | `object` | No | Pre-computed at login; forwarded by `useChatSession` |

**Response `200 OK`** (`application/json`):

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "reply": "Here are some chocolate cakes under ₹500…",
  "products": [
    {
      "product_id": "prod_abc",
      "product_name": "Classic Chocolate Cake",
      "base_price": 449.0,
      "description": "Rich moist chocolate sponge with ganache.",
      "images": [{ "url": "https://..." }],
      "category_id": "cat_cakes",
      "avg_rating": 4.7,
      "rationale": null
    }
  ],
  "active_filters": { "price_max": 500, "keyword": "chocolate cake" },
  "intent": "filter"
}
```

**Error responses**:

| Status | Condition |
|---|---|
| `400` | `business_id` absent, `message` absent or empty, `message` > 500 chars, `price_min > price_max`, message empty after sanitisation |
| `401` | Missing, invalid, or expired access token |
| `403` | Authenticated but not an authorised role (non-prime customer) |
| `429` | Rate limit exceeded (30 req / 60 s per IP) |

---

### `DELETE /chat/session/{session_id}`

Clears the stored conversation context for the given session.

- **`200 OK`** — `{"message": "Session cleared"}`
- **`400 Bad Request`** — session not found or `session_id` missing

---

### `DELETE /cache/business/{business_id}` *(internal — not for frontend use)*

Evicts the in-process catalog cache for a specific business. Called by `backend/server.py` after a product update or deletion.

- **`200 OK`** — `{"evicted": true}` (idempotent)
- Should be network-restricted to localhost/VPC in production.

---

### `GET /chat/health`

Load-balancer health check.

- **`200 OK`** — `{"status": "ok"}`

---

## Running Tests

```bash
cd ai-chatbot
pytest tests/ -v
```

Property-based tests (Hypothesis):

```bash
pytest tests/test_properties.py -v
```
