"""
ai-chatbot/models/schemas.py
Pydantic v2 request/response models for the AI Catalog Chatbot service.

Requirements: 6.1, 6.4, 9.5
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Shared sub-models
# ---------------------------------------------------------------------------


class PreferenceSummary(BaseModel):
    """
    Lightweight personalisation signal forwarded from the frontend React Context
    (populated at login from the backend's auth response).

    Sent as part of every POST /chat/message request body so the Chat_Service
    can personalise recommendations on the first request, before the
    ``user_preferences`` MongoDB document is available.
    """

    top_flavors: List[str] = []
    top_occasions: List[str] = []
    # e.g. {"min": 200.0, "max": 800.0}
    price_range: Optional[Dict[str, float]] = None


class ProductResult(BaseModel):
    """
    A single product returned in chat responses.

    Requirement 9.5: raw MongoDB ``_id`` MUST NOT appear in API responses.
    ``model_config`` uses ``populate_by_name=True`` so that when documents are
    fetched from MongoDB, the field can be explicitly mapped via aliases if
    needed — while the ``_id`` field is simply never declared here and is
    therefore excluded from serialisation automatically.
    """

    model_config = ConfigDict(populate_by_name=True)

    product_id: str
    product_name: str
    base_price: float
    description: str
    images: List[dict]
    category_id: Optional[str] = None
    avg_rating: float
    # Present only for ``recommend`` intent (Requirement 4.3 / 4.6)
    rationale: Optional[str] = None


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class ChatMessageRequest(BaseModel):
    """
    Body for POST /chat/message.

    Requirement 6.1:
    - ``session_id``          optional (absent on first turn)
    - ``business_id``         required; 400 returned if absent
    - ``message``             required string, max 500 characters
    - ``user_id``             optional; enables personalisation
    - ``preference_summary``  optional; lightweight personalisation signal
                              forwarded from React Context
    """

    session_id: Optional[str] = None
    business_id: str
    message: str = Field(..., max_length=500)
    user_id: Optional[str] = None
    preference_summary: Optional[PreferenceSummary] = None


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ChatMessageResponse(BaseModel):
    """
    Body returned by POST /chat/message on success (HTTP 200).

    Requirement 6.4:
    - ``session_id``      UUID v4 identifying the session
    - ``reply``           natural-language assistant reply
    - ``products``        array of Product_Result (may be empty)
    - ``active_filters``  dict of currently-active filter constraints
    - ``intent``          extracted intent label (e.g. "search", "filter", …)
    """

    session_id: str
    reply: str
    products: List[ProductResult] = []
    active_filters: Dict[str, Any] = {}
    intent: str


class ComparisonResult(BaseModel):
    """
    Structured payload for compare intent (Requirement 7.3).

    - ``products``              full product details for each compared item
    - ``attributes``            row labels for the side-by-side table
    - ``missing_product_names`` names that could not be resolved (partial success)
    """

    products: List[ProductResult]
    attributes: List[str]
    missing_product_names: List[str]


class SessionClearResponse(BaseModel):
    """
    Body returned by DELETE /chat/session/:session_id (HTTP 200).
    """

    message: str


class CacheEvictResponse(BaseModel):
    """
    Body returned by DELETE /cache/business/:business_id (HTTP 200).
    Always ``{"evicted": true}`` — endpoint is idempotent.
    """

    evicted: bool


class HealthResponse(BaseModel):
    """
    Body returned by GET /chat/health (HTTP 200).
    e.g. ``{"status": "ok"}``
    """

    status: str
