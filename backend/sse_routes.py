"""
SSE (Server-Sent Events) for real-time order status updates.
Lightweight, one-way push from server to browser.
"""

from fastapi import APIRouter, Request, HTTPException
from starlette.responses import StreamingResponse
import asyncio
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sse")

db = None
# In-memory event bus: { user_id: [asyncio.Queue, ...] }
_subscribers: dict[str, list[asyncio.Queue]] = {}


def set_db(database):
    global db
    db = database


def publish_event(user_id: str, event_type: str, data: dict):
    """Push an event to all active SSE connections for a user."""
    queues = _subscribers.get(user_id, [])
    payload = json.dumps({"type": event_type, "data": data, "timestamp": datetime.now(timezone.utc).isoformat()})
    for q in queues:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass  # drop if client is too slow


async def _get_user_from_request(request: Request):
    """Get user from request using Auth_Module (cookie or Authorization header only)."""
    from backend.auth.dependencies import extract_token
    from backend.auth.tokens import TokenManager
    from backend.auth.sessions import update_last_seen
    
    # Only accept cookie or Authorization header (no query param for security)
    token = request.cookies.get("refresh_token") or request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
    
    if not token:
        return None
    
    # Try as JWT access token first
    try:
        token_manager = TokenManager(db)
        payload = token_manager.verify_access_token(token)
        
        # Load user from DB for authorization
        user = await db.users.find_one(
            {"user_id": payload["sub"]},
            {"_id": 0}
        )
        
        if not user:
            return None
        
        # Update last seen
        await update_last_seen(db, payload["sid"])
        
        return user
    
    except Exception:
        # If JWT fails, try legacy session if enabled
        from backend.auth.tokens import validate_legacy_session
        user = await validate_legacy_session(db, token)
        
        return user


@router.get("/events")
async def sse_events(request: Request):
    """SSE endpoint — clients connect to receive real-time order & notification updates."""
    user = await _get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = user["user_id"]
    queue: asyncio.Queue = asyncio.Queue(maxsize=50)

    if user_id not in _subscribers:
        _subscribers[user_id] = []
    _subscribers[user_id].append(queue)

    async def event_stream():
        try:
            # Send initial heartbeat
            yield f"data: {json.dumps({'type': 'connected', 'data': {'user_id': user_id}})}\n\n"
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield f": heartbeat\n\n"
        finally:
            _subscribers.get(user_id, []).remove(queue) if queue in _subscribers.get(user_id, []) else None
            if not _subscribers.get(user_id):
                _subscribers.pop(user_id, None)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
