from fastapi import APIRouter, HTTPException, Request
from datetime import datetime, timezone
import uuid
import asyncio
import os
import logging
from email_service import send_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/order-management")

db = None

def set_db(database):
    global db
    db = database

# ============= ORDER STATUS PIPELINE =============
VALID_STATUSES = [
    "pending", "confirmed", "preparing", "on_the_way",
    "reached_doorstep", "delivered", "cancelled", "not_delivered"
]

# Who can set which status
ADMIN_STATUSES = ["confirmed", "preparing", "cancelled"]
DELIVERY_STATUSES = ["on_the_way", "reached_doorstep", "delivered", "not_delivered"]

NOT_DELIVERED_REASONS = [
    "Customer unavailable",
    "Wrong address",
    "Customer refused delivery",
    "Address not found",
    "Weather/road conditions",
    "Other"
]

# ============= AUTH HELPERS =============
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

async def require_admin_or_super(request: Request):
    user = await get_user(request)
    if user["role"] not in ["super_admin", "business_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

async def require_delivery_agent(request: Request):
    user = await get_user(request)
    if user["role"] != "delivery_agent":
        raise HTTPException(status_code=403, detail="Delivery agent access required")
    return user

# ============= NOTIFICATION HELPERS =============
async def create_notification(user_id, title, message, order_id=None, notif_type="order_update"):
    notif = {
        "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "title": title,
        "message": message,
        "type": notif_type,
        "order_id": order_id,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.notifications.insert_one(notif)
    # Push real-time SSE event
    try:
        from sse_routes import publish_event
        publish_event(user_id, "notification", {
            "notification_id": notif["notification_id"],
            "title": title,
            "message": message,
            "order_id": order_id,
            "type": notif_type
        })
    except Exception:
        pass
    return notif["notification_id"]


# ============= SSE ORDER EVENT HELPER =============
def _publish_order_event(order, new_status):
    """Push real-time order status update to relevant users."""
    try:
        from sse_routes import publish_event
        event_data = {
            "order_id": order["order_id"],
            "status": new_status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        # Notify order owner
        if order.get("user_id"):
            publish_event(order["user_id"], "order_status", event_data)
        # Notify assigned delivery agent
        if order.get("delivery_agent_id"):
            publish_event(order["delivery_agent_id"], "order_status", event_data)
    except Exception:
        pass


# ============= AUTO-ASSIGN DELIVERY AGENT =============
async def auto_assign_delivery_agent(order):
    """
    Automatically assign the nearest available delivery agent based on pincode proximity.
    Agents store a base_pincode in user_profiles. The order has delivery_info.pincode.
    Uses prefix-based proximity (6-digit pincode comparison — same district matching).
    Ties broken by fewest active orders.
    """
    try:
        order_pincode = order.get("delivery_info", {}).get("pincode", "")
        if not order_pincode:
            logger.info(f"Auto-assign skipped: no delivery pincode for order {order['order_id']}")
            return None

        # Get all delivery agents
        agents = await db.users.find({"role": "delivery_agent"}, {"_id": 0}).to_list(100)
        if not agents:
            logger.info(f"Auto-assign skipped: no delivery agents available")
            return None

        # Get their profiles (base_pincode) and active order counts
        scored_agents = []
        for agent in agents:
            profile = await db.user_profiles.find_one({"user_id": agent["user_id"]}, {"_id": 0})
            base_pincode = (profile or {}).get("base_pincode", "")
            active_count = await db.orders.count_documents({
                "delivery_agent_id": agent["user_id"],
                "order_status": {"$in": ["confirmed", "preparing", "on_the_way", "reached_doorstep"]}
            })
            # Score: exact pincode match = 0 distance, prefix match = partial, else high
            if base_pincode and order_pincode:
                # Simple prefix-based proximity (first 3 digits = same area)
                common = 0
                for a, b in zip(str(base_pincode), str(order_pincode)):
                    if a == b:
                        common += 1
                    else:
                        break
                distance_score = 6 - common  # 0 = perfect match, 6 = no match
            else:
                distance_score = 10  # no pincode set
            scored_agents.append({
                "agent": agent,
                "distance_score": distance_score,
                "active_orders": active_count
            })

        # Sort by distance first, then by fewest active orders
        scored_agents.sort(key=lambda x: (x["distance_score"], x["active_orders"]))
        best = scored_agents[0]

        # Assign
        agent = best["agent"]
        await db.orders.update_one(
            {"order_id": order["order_id"]},
            {"$set": {"delivery_agent_id": agent["user_id"], "updated_at": datetime.now(timezone.utc)}}
        )
        # Notify the agent
        await create_notification(
            agent["user_id"],
            "New delivery assigned",
            f"Order #{order['order_id']} has been auto-assigned to you",
            order["order_id"],
            "delivery_assignment"
        )
        logger.info(f"Auto-assigned order {order['order_id']} to agent {agent['name']} (distance_score={best['distance_score']}, active={best['active_orders']})")
        return agent
    except Exception as e:
        logger.exception(f"Auto-assign failed for order {order.get('order_id', '?')}: {e}")
        return None

# ============= EMAIL HELPER =============
def _build_order_email_html(order):
    """Build the order confirmation email HTML template."""
    items_html = ""
    for item in order.get("items", []):
        items_html += f"""
        <tr>
            <td style="padding:12px 16px;border-bottom:1px solid #E8E0D5;font-family:sans-serif;font-size:14px;color:#2C2420">{item['product_name']}</td>
            <td style="padding:12px 16px;border-bottom:1px solid #E8E0D5;font-family:sans-serif;font-size:14px;color:#786A60;text-align:center">{item['quantity']}</td>
            <td style="padding:12px 16px;border-bottom:1px solid #E8E0D5;font-family:sans-serif;font-size:14px;color:#2C2420;text-align:right">&#8377;{item['subtotal']}</td>
        </tr>"""

    delivery = order.get("delivery_info", {})
    return f"""
    <div style="max-width:600px;margin:0 auto;background:#FAF8F5;padding:0">
        <div style="background:#2C2420;padding:32px;text-align:center">
            <h1 style="font-family:Georgia,serif;font-size:28px;color:#FAF8F5;margin:0;font-style:italic">Whisked Words</h1>
            <p style="font-family:sans-serif;font-size:11px;letter-spacing:3px;color:#D4A373;margin:4px 0 0;text-transform:uppercase">Artisan Bakery</p>
        </div>
        <div style="padding:32px">
            <h2 style="font-family:Georgia,serif;font-size:24px;color:#2C2420;margin:0 0 8px">Order Confirmed</h2>
            <p style="font-family:sans-serif;font-size:14px;color:#786A60;margin:0 0 24px">Thank you for your order! Here's your bill.</p>
            <div style="background:white;border:1px solid #E8E0D5;margin-bottom:24px">
                <div style="padding:16px;border-bottom:1px solid #E8E0D5">
                    <p style="font-family:sans-serif;font-size:12px;letter-spacing:1px;color:#D4A373;text-transform:uppercase;margin:0;font-weight:600">Order #{order['order_id']}</p>
                </div>
                <table style="width:100%;border-collapse:collapse">
                    <thead>
                        <tr style="background:#FAF8F5">
                            <th style="padding:12px 16px;text-align:left;font-family:sans-serif;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:#786A60">Item</th>
                            <th style="padding:12px 16px;text-align:center;font-family:sans-serif;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:#786A60">Qty</th>
                            <th style="padding:12px 16px;text-align:right;font-family:sans-serif;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:#786A60">Amount</th>
                        </tr>
                    </thead>
                    <tbody>{items_html}</tbody>
                </table>
                <div style="padding:16px">
                    <table style="width:100%;font-family:sans-serif;font-size:14px">
                        <tr><td style="padding:4px 0;color:#786A60">Subtotal</td><td style="text-align:right;color:#2C2420">&#8377;{order.get('subtotal', 0)}</td></tr>
                        <tr><td style="padding:4px 0;color:#786A60">Tax</td><td style="text-align:right;color:#2C2420">&#8377;{order.get('tax', 0)}</td></tr>
                        <tr><td style="padding:4px 0;color:#786A60">Delivery</td><td style="text-align:right;color:#2C2420">&#8377;{order.get('delivery_charge', 0)}</td></tr>
                        <tr><td style="padding:8px 0 0;font-weight:700;color:#2C2420;font-size:16px;border-top:1px solid #E8E0D5">Total</td><td style="text-align:right;font-weight:700;color:#2C2420;font-size:16px;padding:8px 0 0;border-top:1px solid #E8E0D5">&#8377;{order.get('total', 0)}</td></tr>
                    </table>
                </div>
            </div>
            <div style="background:white;border:1px solid #E8E0D5;padding:16px;margin-bottom:24px">
                <p style="font-family:sans-serif;font-size:11px;letter-spacing:1px;color:#D4A373;text-transform:uppercase;margin:0 0 8px;font-weight:600">Delivery Address</p>
                <p style="font-family:sans-serif;font-size:14px;color:#2C2420;margin:0">{delivery.get('name', '')}</p>
                <p style="font-family:sans-serif;font-size:14px;color:#786A60;margin:4px 0">{delivery.get('address', '')}</p>
                <p style="font-family:sans-serif;font-size:14px;color:#786A60;margin:0">{delivery.get('city', '')}, {delivery.get('state', '')} - {delivery.get('pincode', '')}</p>
                <p style="font-family:sans-serif;font-size:14px;color:#786A60;margin:4px 0 0">{delivery.get('phone', '')}</p>
            </div>
            <div style="background:white;border:1px solid #E8E0D5;padding:16px">
                <p style="font-family:sans-serif;font-size:14px;color:#786A60;margin:0">Payment: <strong style="color:#2C2420">{order.get('payment_method', 'N/A').upper()}</strong></p>
            </div>
        </div>
        <div style="background:#2C2420;padding:24px;text-align:center">
            <p style="font-family:sans-serif;font-size:12px;color:#FAF8F5;opacity:0.5;margin:0">&copy; Whisked Words &mdash; A Jain Industries Brand</p>
        </div>
    </div>"""


async def send_order_email(to_email, order):
    """Send order confirmation email via plug-and-play email service."""
    html = _build_order_email_html(order)
    subject = f"Order Confirmed - #{order['order_id']} | Whisked Words"
    await send_email(to_email, subject, html)

# ============= ADMIN: ORDER MANAGEMENT =============
@router.get("/orders")
async def admin_list_orders(request: Request, status: str = None, business_id: str = "whisked_words"):
    """Admin: list all orders with optional status filter"""
    user = await require_admin_or_super(request)
    query = {"business_id": business_id}
    if status:
        query["order_status"] = status
    orders = await db.orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)

    # Enrich with delivery agent info
    for order in orders:
        if order.get("delivery_agent_id"):
            agent = await db.users.find_one({"user_id": order["delivery_agent_id"]}, {"_id": 0, "name": 1, "phone": 1, "email": 1})
            order["delivery_agent"] = agent

    return {"orders": orders, "total": len(orders)}

@router.get("/orders/stats")
async def admin_order_stats(request: Request, business_id: str = "whisked_words"):
    """Admin: get order statistics"""
    user = await require_admin_or_super(request)
    pipeline = [
        {"$match": {"business_id": business_id}},
        {"$group": {"_id": "$order_status", "count": {"$sum": 1}, "revenue": {"$sum": "$total"}}}
    ]
    stats = await db.orders.aggregate(pipeline).to_list(20)
    total_orders = sum(s["count"] for s in stats)
    total_revenue = sum(s["revenue"] for s in stats)
    by_status = {s["_id"]: {"count": s["count"], "revenue": s["revenue"]} for s in stats}
    return {"total_orders": total_orders, "total_revenue": total_revenue, "by_status": by_status}

@router.put("/orders/{order_id}/status")
async def admin_update_order_status(order_id: str, request: Request):
    """Admin: update order status"""
    user = await require_admin_or_super(request)
    body = await request.json()
    new_status = body.get("status")

    if new_status not in ADMIN_STATUSES:
        raise HTTPException(status_code=400, detail=f"Admin can only set: {', '.join(ADMIN_STATUSES)}")

    order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Add to status history
    status_entry = {
        "status": new_status,
        "updated_by": user["user_id"],
        "role": user["role"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    await db.orders.update_one(
        {"order_id": order_id},
        {
            "$set": {"order_status": new_status, "updated_at": datetime.now(timezone.utc)},
            "$push": {"status_history": status_entry}
        }
    )

    # Notify customer
    if order.get("user_id"):
        status_labels = {"confirmed": "has been confirmed", "preparing": "is being prepared", "cancelled": "has been cancelled"}
        await create_notification(
            order["user_id"],
            f"Order {status_labels.get(new_status, 'updated')}",
            f"Your order #{order_id} {status_labels.get(new_status, f'status: {new_status}')}",
            order_id
        )

    # Send email on confirm
    if new_status == "confirmed":
        email = order.get("delivery_info", {}).get("email")
        if email:
            asyncio.create_task(send_order_email(email, order))
        # Auto-assign delivery agent if none assigned
        if not order.get("delivery_agent_id"):
            asyncio.create_task(auto_assign_delivery_agent(order))

    # Push real-time SSE event
    _publish_order_event(order, new_status)

    return {"message": f"Order status updated to {new_status}"}

@router.put("/orders/{order_id}/assign")
async def admin_assign_delivery(order_id: str, request: Request):
    """Admin: assign delivery agent to order"""
    user = await require_admin_or_super(request)
    body = await request.json()
    agent_id = body.get("delivery_agent_id")

    if not agent_id:
        raise HTTPException(status_code=400, detail="delivery_agent_id required")

    # Verify agent exists and has delivery_agent role
    agent = await db.users.find_one({"user_id": agent_id}, {"_id": 0})
    if not agent or agent["role"] != "delivery_agent":
        raise HTTPException(status_code=400, detail="Invalid delivery agent")

    order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    await db.orders.update_one(
        {"order_id": order_id},
        {"$set": {"delivery_agent_id": agent_id, "updated_at": datetime.now(timezone.utc)}}
    )

    # Notify delivery agent
    await create_notification(
        agent_id,
        "New delivery assigned",
        f"Order #{order_id} has been assigned to you",
        order_id,
        "delivery_assignment"
    )

    return {"message": f"Delivery agent {agent['name']} assigned to order {order_id}"}

# ============= ADMIN: DELIVERY AGENT MANAGEMENT =============
@router.get("/delivery-agents")
async def list_delivery_agents(request: Request, business_id: str = "whisked_words"):
    """Admin: list all delivery agents"""
    await require_admin_or_super(request)
    agents = await db.users.find({"role": "delivery_agent"}, {"_id": 0}).to_list(100)
    # Add phone and base_pincode from user profile
    for agent in agents:
        profile = await db.user_profiles.find_one({"user_id": agent["user_id"]}, {"_id": 0})
        if profile:
            agent["phone"] = profile.get("phone", "")
            agent["base_pincode"] = profile.get("base_pincode", "")
        # Count active deliveries
        agent["active_orders"] = await db.orders.count_documents({
            "delivery_agent_id": agent["user_id"],
            "order_status": {"$in": ["confirmed", "preparing", "on_the_way", "reached_doorstep"]}
        })
    return {"agents": agents, "total": len(agents)}

@router.put("/users/{user_id}/make-delivery-agent")
async def make_delivery_agent(user_id: str, request: Request):
    """Admin: promote user to delivery agent role"""
    admin = await require_admin_or_super(request)
    body = await request.json()
    phone = body.get("phone", "")
    base_pincode = body.get("base_pincode", "")

    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "role": "delivery_agent",
                "updated_at": datetime.now(timezone.utc)
            },
            "$addToSet": {
                "business_access": {
                    "business_id": "whisked_words",
                    "role": "delivery_agent",
                    "assigned_at": datetime.now(timezone.utc).isoformat()
                }
            }
        }
    )

    # Store phone and base_pincode
    profile_update = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if phone:
        profile_update["phone"] = phone
    if base_pincode:
        profile_update["base_pincode"] = base_pincode
    await db.user_profiles.update_one(
        {"user_id": user_id},
        {"$set": profile_update},
        upsert=True
    )

    return {"message": f"User {user['name']} is now a delivery agent"}

# ============= DELIVERY AGENT ROUTES =============
@router.get("/delivery/my-orders")
async def delivery_my_orders(request: Request, status: str = None):
    """Delivery agent: get assigned orders"""
    user = await require_delivery_agent(request)
    query = {"delivery_agent_id": user["user_id"]}
    if status:
        query["order_status"] = status
    orders = await db.orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return {"orders": orders, "total": len(orders)}

@router.put("/delivery/orders/{order_id}/status")
async def delivery_update_status(order_id: str, request: Request):
    """Delivery agent: update delivery status"""
    user = await require_delivery_agent(request)
    body = await request.json()
    new_status = body.get("status")
    reason = body.get("reason", "")
    custom_reason = body.get("custom_reason", "")

    if new_status not in DELIVERY_STATUSES:
        raise HTTPException(status_code=400, detail=f"Delivery agent can only set: {', '.join(DELIVERY_STATUSES)}")

    order = await db.orders.find_one({"order_id": order_id, "delivery_agent_id": user["user_id"]}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or not assigned to you")

    # Validate not_delivered requires reason
    if new_status == "not_delivered" and not reason:
        raise HTTPException(status_code=400, detail="Reason is required for not_delivered status")

    status_entry = {
        "status": new_status,
        "updated_by": user["user_id"],
        "role": "delivery_agent",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    if reason:
        status_entry["reason"] = reason
    if custom_reason:
        status_entry["custom_reason"] = custom_reason

    await db.orders.update_one(
        {"order_id": order_id},
        {
            "$set": {"order_status": new_status, "updated_at": datetime.now(timezone.utc)},
            "$push": {"status_history": status_entry}
        }
    )

    # Notify customer
    if order.get("user_id"):
        status_labels = {
            "on_the_way": "is on its way to you",
            "reached_doorstep": "has reached your doorstep",
            "delivered": "has been delivered",
            "not_delivered": "could not be delivered"
        }
        msg = f"Your order #{order_id} {status_labels.get(new_status, '')}"
        if new_status == "not_delivered":
            msg += f". Reason: {reason}" + (f" - {custom_reason}" if custom_reason else "")
        await create_notification(order["user_id"], f"Order {new_status.replace('_', ' ')}", msg, order_id)

    # Push real-time SSE event
    _publish_order_event(order, new_status)

    return {"message": f"Order status updated to {new_status}"}

# ============= NOTIFICATION ROUTES =============
@router.get("/notifications")
async def get_notifications(request: Request, unread_only: bool = False):
    """Get user notifications"""
    user = await get_user(request)
    query = {"user_id": user["user_id"]}
    if unread_only:
        query["read"] = False
    notifications = await db.notifications.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
    unread_count = await db.notifications.count_documents({"user_id": user["user_id"], "read": False})
    return {"notifications": notifications, "unread_count": unread_count}

@router.put("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, request: Request):
    """Mark notification as read"""
    user = await get_user(request)
    await db.notifications.update_one(
        {"notification_id": notification_id, "user_id": user["user_id"]},
        {"$set": {"read": True}}
    )
    return {"message": "Notification marked as read"}

@router.put("/notifications/read-all")
async def mark_all_read(request: Request):
    """Mark all notifications as read"""
    user = await get_user(request)
    await db.notifications.update_many(
        {"user_id": user["user_id"], "read": False},
        {"$set": {"read": True}}
    )
    return {"message": "All notifications marked as read"}

# ============= CUSTOMER: ORDER TRACKING =============
@router.get("/track/{order_id}")
async def track_order(order_id: str, request: Request):
    """Customer: get order tracking details with timeline"""
    user = await get_user(request)
    order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Only order owner, admin, or assigned delivery agent can view
    if order.get("user_id") != user["user_id"] and user["role"] not in ["super_admin", "business_admin"] and order.get("delivery_agent_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    # Build timeline
    created_at = order.get("created_at", "")
    if hasattr(created_at, "isoformat"):
        created_at = created_at.isoformat()
    timeline = [{"status": "pending", "label": "Order Placed", "timestamp": str(created_at), "completed": True}]

    status_order = ["confirmed", "preparing", "on_the_way", "reached_doorstep", "delivered"]
    history = {h["status"]: h for h in order.get("status_history", [])}
    current_idx = status_order.index(order["order_status"]) if order["order_status"] in status_order else -1

    labels = {"confirmed": "Confirmed", "preparing": "Preparing", "on_the_way": "On The Way", "reached_doorstep": "Reached Doorstep", "delivered": "Delivered"}

    for i, s in enumerate(status_order):
        entry = {"status": s, "label": labels[s], "completed": i <= current_idx, "timestamp": history.get(s, {}).get("timestamp")}
        if s in history and history[s].get("reason"):
            entry["reason"] = history[s]["reason"]
        timeline.append(entry)

    # Handle cancelled/not_delivered
    if order["order_status"] in ["cancelled", "not_delivered"]:
        h = history.get(order["order_status"], {})
        timeline.append({
            "status": order["order_status"],
            "label": "Cancelled" if order["order_status"] == "cancelled" else "Not Delivered",
            "completed": True,
            "timestamp": h.get("timestamp"),
            "reason": h.get("reason", ""),
            "custom_reason": h.get("custom_reason", "")
        })

    # Delivery agent info
    agent_info = None
    if order.get("delivery_agent_id"):
        agent = await db.users.find_one({"user_id": order["delivery_agent_id"]}, {"_id": 0, "name": 1})
        profile = await db.user_profiles.find_one({"user_id": order["delivery_agent_id"]}, {"_id": 0, "phone": 1})
        if agent:
            agent_info = {"name": agent["name"], "phone": profile.get("phone", "") if profile else ""}

    return {
        "order": order,
        "timeline": timeline,
        "delivery_agent": agent_info,
        "current_status": order["order_status"]
    }

# ============= NOT DELIVERED REASONS =============
@router.get("/not-delivered-reasons")
async def get_not_delivered_reasons():
    return {"reasons": NOT_DELIVERED_REASONS}
