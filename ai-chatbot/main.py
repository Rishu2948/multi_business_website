"""
ai-chatbot/main.py
Entry point for the AI Catalog Chatbot microservice.

Start with:
    uvicorn main:app --reload --port 8001
"""

import os
from contextlib import asynccontextmanager

import motor.motor_asyncio
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import ASCENDING, TEXT
from pymongo.errors import OperationFailure

from routers.chat import router as chat_router

# ---------------------------------------------------------------------------
# Load environment variables from .env (if present)
# ---------------------------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------------------------
# CORS configuration
# ---------------------------------------------------------------------------
_raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
CORS_ORIGINS: list[str] = [origin.strip() for origin in _raw_origins.split(",") if origin.strip()]


# ---------------------------------------------------------------------------
# Startup / shutdown lifecycle
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup tasks:
      - Ensure MongoDB indexes exist on the `products`, `chat_sessions`,
        and `user_preferences` collections (idempotent; runs in the background).
    """
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.getenv("DB_NAME", "multi_business_db")
    client = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    async def _safe_create_index(collection, keys, **kwargs):
        """Create an index, silently ignoring IndexOptionsConflict (code 85).
        This handles the case where the backend service already created the same
        index under a different name."""
        try:
            await collection.create_index(keys, **kwargs)
        except OperationFailure as exc:
            if exc.code == 85:  # IndexOptionsConflict — index already exists, skip
                pass
            else:
                raise

    # --- products: compound text index for full-text search scoped by business ---
    # Requirements: 2.3, 3.3
    await _safe_create_index(
        db.products,
        [("business_id", ASCENDING), ("product_name", TEXT), ("description", TEXT)],
        background=True,
        name="products_business_text_search",
    )

    # --- chat_sessions: unique session lookup + TTL expiry after 30 min ---
    # Requirements: 5.6
    await _safe_create_index(
        db.chat_sessions,
        [("session_id", ASCENDING)],
        unique=True,
        background=True,
        name="chat_sessions_unique_session_id",
    )
    await _safe_create_index(
        db.chat_sessions,
        [("last_active", ASCENDING)],
        expireAfterSeconds=1800,
        background=True,
        name="chat_sessions_ttl_last_active",
    )

    # --- user_preferences: reuse the indexes the backend already created ---
    # The backend created these under the names below; we skip creation if they exist.
    # Requirements: 4.4
    await _safe_create_index(
        db.user_preferences,
        [("user_id", ASCENDING)],
        unique=True,
        background=True,
        name="user_preferences_unique_user_id",
    )
    await _safe_create_index(
        db.user_preferences,
        [("expires_at", ASCENDING)],
        expireAfterSeconds=0,
        background=True,
        name="user_preferences_ttl_expires_at",
    )

    yield

    # Shutdown: close the Motor client
    client.close()


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AI Catalog Chatbot",
    description=(
        "Conversational product-discovery service for the multi-business website. "
        "Processes natural-language queries against the MongoDB product catalog "
        "using an LLM backend."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Middleware registration order (innermost first, outermost last)
# Execution order on a request: rate_limiter → sanitiser → route handler
#
# NOTE: The sanitiser and rate-limiter middleware implementations live in
#       middleware/sanitiser.py and middleware/rate_limiter.py respectively.
#       They are registered here once those modules are implemented
#       (Tasks 3 and 4 in the spec).  The stubs below keep the import from
#       failing at startup before those tasks are complete.
# ---------------------------------------------------------------------------
try:
    from middleware.sanitiser import SanitiserMiddleware  # type: ignore
    app.add_middleware(SanitiserMiddleware)
except ImportError:
    pass  # middleware not yet implemented — safe to skip during scaffolding

try:
    from middleware.rate_limiter import RateLimiterMiddleware  # type: ignore
    app.add_middleware(RateLimiterMiddleware)
except ImportError:
    pass  # middleware not yet implemented — safe to skip during scaffolding

# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------
app.include_router(chat_router, prefix="/chat", tags=["chat"])
