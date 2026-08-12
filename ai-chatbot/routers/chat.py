"""
ai-chatbot/routers/chat.py

FastAPI router for the AI Catalog Chatbot service.

Endpoints:
  POST   /chat/message               — main chat endpoint (auth-gated)
  DELETE /chat/session/{session_id}  — clear a session
  DELETE /cache/business/{business_id} — evict catalog cache (internal only)
  GET    /chat/health                — health check

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.8, 10.1, 10.2, 10.6
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from middleware.auth import check_chatbot_access, get_db
from middleware.sanitiser import sanitise
from middleware.rate_limiter import check_rate_limit, _resolve_ip
from models.schemas import (
    CacheEvictResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    HealthResponse,
    ProductResult,
    SessionClearResponse,
)
from services.catalog_query import (
    compare,
    evict_catalog_cache,
    query_products,
    recommend,
)
from services.nl_processor import process_message
from services.session_manager import (
    clear_session,
    create_session,
    get_user_preferences,
    load_session,
    save_session,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helper: convert raw product dicts to ProductResult, stripping _id
# ---------------------------------------------------------------------------


def _to_product_result(doc: dict) -> ProductResult:
    """Convert a raw MongoDB product document to a ProductResult, excluding _id."""
    doc.pop("_id", None)
    # Provide safe defaults for optional / missing fields
    return ProductResult(
        product_id=doc.get("product_id", ""),
        product_name=doc.get("product_name", ""),
        base_price=float(doc.get("base_price", 0.0)),
        description=doc.get("description", ""),
        images=doc.get("images", []),
        category_id=doc.get("category_id", ""),
        avg_rating=float(doc.get("avg_rating", 0.0)),
        rationale=doc.get("rationale"),
    )


# ---------------------------------------------------------------------------
# POST /chat/message
# ---------------------------------------------------------------------------


@router.post(
    "/message",
    response_model=ChatMessageResponse,
    summary="Send a chat message",
    description=(
        "Process a natural-language chat message. "
        "Requires a valid session token (cookie or Bearer header). "
        "Returns the assistant reply, matched products, active filters, and intent."
    ),
)
async def post_message(
    request: Request,
    body: ChatMessageRequest,
    db=Depends(get_db),
    user: dict = Depends(check_chatbot_access),  # 401/403 raised here before any processing
) -> ChatMessageResponse:
    """
    Main chat endpoint.

    Processing order (per spec design):
    1. Auth middleware — `check_chatbot_access` via Depends (runs before this handler).
    2. Validate request fields — 400 for absent business_id / empty message / message > 500 chars.
    3. Rate-limit check — 429 if exceeded.
    4. Sanitise message.
    5. Load or create session via Session_Manager.
    6. Call NL_Processor.
    7. Call Catalog_Query_Engine based on intent.
    8. Persist updated session.
    9. Return ChatMessageResponse (no _id fields).
    """
    # ------------------------------------------------------------------
    # Step 2: Request validation
    # These are belt-and-suspenders checks; Pydantic already enforces max_length=500
    # and the required `business_id` field, but we provide explicit 400 responses
    # as required by the spec (Req 6.2, 6.3).
    # ------------------------------------------------------------------
    if not body.business_id:
        raise HTTPException(status_code=400, detail="business_id is required")

    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="message must not be empty")

    if len(body.message) > 500:
        raise HTTPException(
            status_code=400,
            detail="message must not exceed 500 characters",
        )

    # ------------------------------------------------------------------
    # Step 3: Rate-limit check (Req 9.4)
    # The RateLimiterMiddleware in main.py handles all routes globally, but
    # we check explicitly here too so the 429 fires after auth but before
    # heavier processing, matching the spec's stated order.
    # ------------------------------------------------------------------
    client_ip = _resolve_ip(request)
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait before sending more messages.",
        )

    # ------------------------------------------------------------------
    # Step 4: Sanitise message (Req 9.1)
    # The SanitiserMiddleware in main.py has already sanitised the body on
    # the wire-level, but we re-sanitise here using the pure function so
    # that route-level logic is self-contained and testable.
    # ------------------------------------------------------------------
    clean_message = sanitise(body.message)
    if not clean_message:
        raise HTTPException(
            status_code=400,
            detail="message field is empty after sanitisation",
        )

    # ------------------------------------------------------------------
    # Step 5: Load or create session (Req 5.1, 5.5, 5.6)
    # ------------------------------------------------------------------
    session: Optional[dict] = None

    if body.session_id:
        session = await load_session(db, body.session_id)

    if session is None:
        # New session (or expired / unknown session_id)
        session = await create_session(db, body.business_id, body.user_id)

    # Attach user_preferences preference_vector for personalisation (Req 4.4)
    user_context: dict = {}
    if body.user_id:
        user_context["user_id"] = body.user_id
        prefs = await get_user_preferences(db, body.user_id)
        if prefs:
            user_context["preference_vector"] = prefs.get("preference_vector")
        if body.preference_summary:
            user_context["preference_summary"] = body.preference_summary.model_dump()

    # ------------------------------------------------------------------
    # Step 6: NL_Processor — parse intent from message (Req 2.1, 2.2)
    # ------------------------------------------------------------------
    turns: list = session.get("turns", [])
    active_filters: dict = session.get("active_filters", {})

    # Build conversation context list (role/content dicts)
    conversation_context: list = [
        {"role": t.get("role", "user"), "content": t.get("content", "")}
        for t in turns
    ]

    nl_result = await process_message(
        message=clean_message,
        conversation_context=conversation_context,
        active_filters=active_filters,
        business_name=body.business_id,  # business_name not in request; use business_id as label
        client_ip=client_ip,
    )

    intent: str = nl_result.get("intent", "clarify")
    reply: str = nl_result.get("reply", "")
    new_filters: dict = nl_result.get("filters", {})
    updated_active_filters: dict = nl_result.get("active_filters", active_filters)

    # ------------------------------------------------------------------
    # Step 7: Catalog_Query_Engine — fetch products based on intent (Req 2.3, 3.2, 4.1, 7.1)
    # ------------------------------------------------------------------
    products: list[ProductResult] = []
    recommendation_rationales: dict = session.get("recommendation_rationales", {})

    if intent in ("search", "filter"):
        raw_products = await query_products(db, body.business_id, updated_active_filters)
        products = [_to_product_result(p) for p in raw_products[:6]]

    elif intent == "recommend":
        raw_products = await recommend(
            db,
            body.business_id,
            updated_active_filters,
            user_context=user_context or None,
        )
        products = []
        for p in raw_products[:6]:
            prod = _to_product_result(p)
            # Attach rationale if present (from NL response or existing session rationales)
            if not prod.rationale:
                prod.rationale = recommendation_rationales.get(prod.product_id)
            products.append(prod)
        # Persist new rationales so "why did you suggest this?" works (Req 4.6)
        for p in products:
            if p.rationale:
                recommendation_rationales[p.product_id] = p.rationale

    elif intent == "compare":
        # Extract product IDs from conversation context (prior results)
        compare_ids = _extract_product_ids_from_context(turns, max_ids=4)
        if len(compare_ids) >= 2:
            compare_result = await compare(db, body.business_id, compare_ids)
            if compare_result.get("intent") != "compare_failed":
                products = [_to_product_result(p) for p in compare_result.get("products", [])]
            else:
                # Partial failure handled by the NL reply; products stays empty
                pass
        # If <2 identifiable products, products stays empty and LLM reply asks for clarification

    elif intent == "out_of_scope":
        # Declined — products stays empty, reply from NL_Processor explains why
        pass

    elif intent == "clarify":
        # Low-confidence or clarification request — products stays empty
        pass

    elif intent == "clear_filters":
        # Filters cleared — return empty products, reply confirms the reset
        updated_active_filters = {}
        pass

    # Handle "reset" / "clear filters" intent implied by NL
    if intent in ("search", "filter") and not new_filters and not updated_active_filters:
        # All filters cleared
        updated_active_filters = {}

    # ------------------------------------------------------------------
    # Step 8: Append turns and persist session (Req 5.1, 5.3)
    # ------------------------------------------------------------------
    now_iso = datetime.now(timezone.utc).isoformat()

    turns.append({"role": "user", "content": clean_message, "ts": now_iso})
    turns.append({"role": "assistant", "content": reply, "ts": now_iso})

    session["turns"] = turns
    session["active_filters"] = updated_active_filters
    session["recommendation_rationales"] = recommendation_rationales

    await save_session(db, session)

    # ------------------------------------------------------------------
    # Step 9: Return response (no _id fields — Req 9.5, 6.4)
    # ------------------------------------------------------------------
    return ChatMessageResponse(
        session_id=session["session_id"],
        reply=reply,
        products=products,
        active_filters=updated_active_filters,
        intent=intent,
    )


# ---------------------------------------------------------------------------
# DELETE /chat/session/{session_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/session/{session_id}",
    response_model=SessionClearResponse,
    summary="Clear a chat session",
    description="Delete the stored conversation context for the given session_id. Requires privileged authentication.",
)
async def delete_session(
    session_id: str,
    db=Depends(get_db),
    user: dict = Depends(check_chatbot_access),
) -> SessionClearResponse:
    """
    Clear an existing chat session.

    Returns 200 {"message": "Session cleared"} on success.
    Raises 400 if session_id is missing from the path or not found (Req 6.5).
    Requires privileged authentication (admin/staff roles).
    """
    # Check user has privileged role
    if user.get("role") not in ["super_admin", "business_admin", "staff"]:
        raise HTTPException(status_code=403, detail="Access forbidden. Privileged role required")
    
    if not session_id or not session_id.strip():
        raise HTTPException(status_code=400, detail="session_id is required")

    # clear_session raises HTTPException(400) if not found (see session_manager.py)
    await clear_session(db, session_id)

    return SessionClearResponse(message="Session cleared")


# ---------------------------------------------------------------------------
# DELETE /cache/business/{business_id}   (internal only)
# ---------------------------------------------------------------------------


@router.delete(
    "/cache/business/{business_id}",
    response_model=CacheEvictResponse,
    summary="Evict catalog cache for a business",
    description=(
        "**Internal endpoint** — evicts the in-process TTLCache for the given "
        "business_id. Called by the existing backend after product updates/deletions. "
        "Requires privileged authentication for security."
    ),
    include_in_schema=True,  # visible in docs but documented as internal
    tags=["internal"],
)
async def evict_cache(
    business_id: str,
    db=Depends(get_db),
    user: dict = Depends(check_chatbot_access),
) -> CacheEvictResponse:
    """
    Evict the catalog cache for a specific business.

    Idempotent — returns {"evicted": true} whether or not an entry was present.
    Requires privileged authentication (admin/staff roles) for security.
    """
    # Check user has privileged role
    if user.get("role") not in ["super_admin", "business_admin", "staff"]:
        raise HTTPException(status_code=403, detail="Access forbidden. Privileged role required")
    
    evict_catalog_cache(business_id)
    return CacheEvictResponse(evicted=True)


# ---------------------------------------------------------------------------
# GET /chat/health
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns HTTP 200 with {\"status\": \"ok\"} for load-balancer health checks.",
)
async def health_check() -> HealthResponse:
    """Simple health check endpoint (Req 6.6)."""
    return HealthResponse(status="ok")


# ---------------------------------------------------------------------------
# Internal helper: extract product IDs from prior assistant turns
# ---------------------------------------------------------------------------


def _extract_product_ids_from_context(turns: list, max_ids: int = 4) -> list[str]:
    """
    Scan prior session turns for product_id values that were returned in
    assistant responses.

    This is a best-effort extraction: in practice the caller should pass
    explicit product IDs resolved from the conversation, but when the NL
    Processor has identified a compare intent and we need concrete IDs we
    look backward through the session turns looking for UUIDs / product_id
    strings stored in turn metadata.

    The current implementation returns an empty list as a safe default —
    full product ID extraction from structured turn payloads would require
    the turns to carry the product list, which is an enhancement tracked
    separately.  The NL_Processor's ``compare`` intent handling ensures the
    reply asks for clarification when IDs cannot be resolved.
    """
    # Turns may carry a "products" key if we extend the session schema in
    # a future task.  For now we return [] and let the compare branch fall
    # through to the clarify path.
    product_ids: list[str] = []
    for turn in reversed(turns):
        if turn.get("role") == "assistant":
            for pid in turn.get("product_ids", []):
                if pid not in product_ids:
                    product_ids.append(pid)
            if len(product_ids) >= max_ids:
                break
    return product_ids[:max_ids]
