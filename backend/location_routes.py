"""
Location routes: saved addresses, delivery agent GPS tracking, reverse geocoding.
"""
from fastapi import APIRouter, HTTPException, Request
from datetime import datetime, timezone
import uuid
import math
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/locations")

db = None

def set_db(database):
    global db
    db = database


# ============= AUTH HELPER =============
async def get_user(request: Request):
    token = request.cookies.get("session_token") or request.headers.get("authorization", "").replace("Bearer ", "")
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# ============= HAVERSINE DISTANCE =============
def haversine_km(lat1, lon1, lat2, lon2):
    """Calculate distance between two GPS coordinates in km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ============= SAVED ADDRESSES =============
@router.get("/addresses")
async def get_saved_addresses(request: Request):
    """Get user's saved delivery addresses."""
    user = await get_user(request)
    addresses = await db.saved_addresses.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).sort("is_default", -1).to_list(20)
    return {"addresses": addresses}


@router.post("/addresses")
async def save_address(request: Request):
    """Save a new delivery address."""
    user = await get_user(request)
    body = await request.json()

    address = {
        "address_id": f"addr_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "label": body.get("label", "Home"),
        "name": body.get("name", user.get("name", "")),
        "phone": body.get("phone", ""),
        "email": body.get("email", user.get("email", "")),
        "address": body["address"],
        "city": body["city"],
        "state": body["state"],
        "pincode": body["pincode"],
        "lat": body.get("lat"),
        "lng": body.get("lng"),
        "is_default": body.get("is_default", False),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    # If this is default, unset other defaults
    if address["is_default"]:
        await db.saved_addresses.update_many(
            {"user_id": user["user_id"]},
            {"$set": {"is_default": False}}
        )

    await db.saved_addresses.insert_one(address)
    return {"address_id": address["address_id"], "message": "Address saved"}


@router.put("/addresses/{address_id}")
async def update_address(address_id: str, request: Request):
    """Update a saved address."""
    user = await get_user(request)
    body = await request.json()

    existing = await db.saved_addresses.find_one(
        {"address_id": address_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Address not found")

    update = {k: v for k, v in body.items() if k in [
        "label", "name", "phone", "email", "address", "city", "state", "pincode", "lat", "lng", "is_default"
    ]}
    update["updated_at"] = datetime.now(timezone.utc).isoformat()

    if update.get("is_default"):
        await db.saved_addresses.update_many(
            {"user_id": user["user_id"]},
            {"$set": {"is_default": False}}
        )

    await db.saved_addresses.update_one(
        {"address_id": address_id, "user_id": user["user_id"]},
        {"$set": update}
    )
    return {"message": "Address updated"}


@router.delete("/addresses/{address_id}")
async def delete_address(address_id: str, request: Request):
    """Delete a saved address."""
    user = await get_user(request)
    result = await db.saved_addresses.delete_one(
        {"address_id": address_id, "user_id": user["user_id"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Address not found")
    return {"message": "Address deleted"}


# ============= DELIVERY AGENT GPS TRACKING =============
@router.put("/agent/update-location")
async def agent_update_location(request: Request):
    """Delivery agent sends GPS coordinates (called every ~10s during active delivery)."""
    user = await get_user(request)
    if user["role"] != "delivery_agent":
        raise HTTPException(status_code=403, detail="Delivery agent access required")

    body = await request.json()
    lat = body.get("lat")
    lng = body.get("lng")
    if lat is None or lng is None:
        raise HTTPException(status_code=400, detail="lat and lng required")

    await db.agent_locations.update_one(
        {"user_id": user["user_id"]},
        {"$set": {
            "user_id": user["user_id"],
            "lat": float(lat),
            "lng": float(lng),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "is_active": True
        }},
        upsert=True
    )

    # Also push SSE event for customers tracking this agent's deliveries
    try:
        from sse_routes import publish_event
        # Find orders assigned to this agent that are in transit
        active_orders = await db.orders.find(
            {"delivery_agent_id": user["user_id"], "order_status": {"$in": ["on_the_way", "reached_doorstep"]}},
            {"_id": 0, "user_id": 1, "order_id": 1}
        ).to_list(20)
        for order in active_orders:
            if order.get("user_id"):
                publish_event(order["user_id"], "agent_location", {
                    "order_id": order["order_id"],
                    "lat": float(lat),
                    "lng": float(lng)
                })
    except Exception:
        pass

    return {"message": "Location updated"}


@router.put("/agent/stop-sharing")
async def agent_stop_sharing(request: Request):
    """Delivery agent stops sharing location."""
    user = await get_user(request)
    if user["role"] != "delivery_agent":
        raise HTTPException(status_code=403, detail="Delivery agent access required")

    await db.agent_locations.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": "Location sharing stopped"}


@router.get("/agent/{order_id}/location")
async def get_agent_location(order_id: str, request: Request):
    """Customer/Admin: get delivery agent's live location for an order."""
    user = await get_user(request)
    order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Authorization: customer (order owner), admin, or assigned agent
    if (order.get("user_id") != user["user_id"]
        and user["role"] not in ["super_admin", "business_admin"]
        and order.get("delivery_agent_id") != user["user_id"]):
        raise HTTPException(status_code=403, detail="Access denied")

    if not order.get("delivery_agent_id"):
        return {"location": None, "message": "No delivery agent assigned"}

    location = await db.agent_locations.find_one(
        {"user_id": order["delivery_agent_id"]},
        {"_id": 0}
    )
    if not location or not location.get("is_active"):
        return {"location": None, "message": "Agent location not available"}

    # Calculate ETA if customer has coordinates
    eta_minutes = None
    delivery_lat = order.get("delivery_info", {}).get("lat")
    delivery_lng = order.get("delivery_info", {}).get("lng")
    if delivery_lat and delivery_lng and location.get("lat") and location.get("lng"):
        distance_km = haversine_km(location["lat"], location["lng"], float(delivery_lat), float(delivery_lng))
        eta_minutes = max(1, round(distance_km / 0.5))  # Assume ~30 km/h average speed in city

    return {
        "location": {
            "lat": location["lat"],
            "lng": location["lng"],
            "updated_at": location["updated_at"]
        },
        "eta_minutes": eta_minutes
    }


# ============= DISTANCE-BASED AUTO-ASSIGN HELPER =============
async def find_nearest_agent(order_lat, order_lng):
    """Find the nearest available delivery agent by GPS distance."""
    agents = await db.users.find({"role": "delivery_agent"}, {"_id": 0}).to_list(100)
    if not agents:
        return None

    scored = []
    for agent in agents:
        loc = await db.agent_locations.find_one({"user_id": agent["user_id"]}, {"_id": 0})
        active_count = await db.orders.count_documents({
            "delivery_agent_id": agent["user_id"],
            "order_status": {"$in": ["confirmed", "preparing", "on_the_way", "reached_doorstep"]}
        })
        if loc and loc.get("lat") and loc.get("lng"):
            dist = haversine_km(loc["lat"], loc["lng"], order_lat, order_lng)
        else:
            # Fallback: check base_pincode location from profile
            dist = 999
        scored.append({"agent": agent, "distance_km": dist, "active_orders": active_count})

    scored.sort(key=lambda x: (x["distance_km"], x["active_orders"]))
    return scored[0] if scored else None
