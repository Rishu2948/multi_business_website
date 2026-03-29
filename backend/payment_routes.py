from fastapi import APIRouter, HTTPException, Request
from datetime import datetime, timezone
import uuid
import os
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest

router = APIRouter(prefix="/api/payments")

# Database will be set from main server
db = None

def set_db(database):
    global db
    db = database

@router.post("/create-checkout-session")
async def create_checkout_session(request: Request):
    """Create payment checkout session for Stripe or Razorpay"""
    body = await request.json()
    
    order_id = body.get("order_id")
    payment_method = body.get("payment_method", "stripe")
    origin_url = body.get("origin_url")
    
    if not order_id or not origin_url:
        raise HTTPException(status_code=400, detail="order_id and origin_url required")
    
    # Get order details
    order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Create transaction record
    transaction_id = f"txn_{uuid.uuid4().hex[:12]}"
    transaction = {
        "transaction_id": transaction_id,
        "order_id": order_id,
        "user_id": order.get("user_id"),
        "payment_method": payment_method,
        "amount": float(order["total"]),
        "currency": "INR",
        "payment_status": "initiated",
        "session_id": None,
        "payment_id": None,
        "metadata": {
            "order_id": order_id,
            "business_id": "whisked_words"
        },
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    await db.payment_transactions.insert_one(transaction)
    
    if payment_method == "stripe":
        # Initialize Stripe
        stripe_api_key = os.environ.get("STRIPE_API_KEY")
        if not stripe_api_key:
            raise HTTPException(status_code=500, detail="Stripe API key not configured")
        
        webhook_url = f"{origin_url}/api/webhook/stripe"
        stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
        
        # Create checkout session
        success_url = f"{origin_url}/order-success?session_id={{{{CHECKOUT_SESSION_ID}}}}"
        cancel_url = f"{origin_url}/checkout"
        
        checkout_request = CheckoutSessionRequest(
            amount=float(order["total"]),
            currency="inr",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "order_id": order_id,
                "transaction_id": transaction_id
            }
        )
        
        session = await stripe_checkout.create_checkout_session(checkout_request)
        
        # Update transaction with session ID
        await db.payment_transactions.update_one(
            {"transaction_id": transaction_id},
            {"$set": {"session_id": session.session_id, "payment_status": "pending"}}
        )
        
        return {"url": session.url, "session_id": session.session_id, "payment_method": "stripe"}
    
    elif payment_method == "razorpay":
        # Razorpay implementation
        # For now, return error asking for keys
        raise HTTPException(
            status_code=501,
            detail="Razorpay integration requires API keys. Please provide RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in backend .env file."
        )
    
    else:
        raise HTTPException(status_code=400, detail="Invalid payment method")

@router.get("/checkout-status/{session_id}")
async def get_checkout_status(session_id: str):
    """Get payment checkout status"""
    # Find transaction
    transaction = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    if transaction["payment_method"] == "stripe":
        stripe_api_key = os.environ.get("STRIPE_API_KEY")
        stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url="")
        
        status = await stripe_checkout.get_checkout_status(session_id)
        
        # Update transaction
        if status.payment_status == "paid" and transaction["payment_status"] != "paid":
            await db.payment_transactions.update_one(
                {"transaction_id": transaction["transaction_id"]},
                {"$set": {
                    "payment_status": "paid",
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
            
            # Update order
            await db.orders.update_one(
                {"order_id": transaction["order_id"]},
                {"$set": {
                    "payment_status": "paid",
                    "payment_id": session_id,
                    "order_status": "confirmed",
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
            
            # Award loyalty points (10% of order value)
            order = await db.orders.find_one({"order_id": transaction["order_id"]}, {"_id": 0})
            if order and order.get("user_id"):
                points_earned = int(order["total"] * 0.1)  # 10% as points
                
                # Update loyalty points
                await db.loyalty_points.update_one(
                    {"user_id": order["user_id"]},
                    {
                        "$inc": {"points": points_earned, "total_earned": points_earned},
                        "$setOnInsert": {"user_id": order["user_id"], "tier": "bronze", "total_redeemed": 0}
                    },
                    upsert=True
                )
                
                # Create points transaction
                points_txn = {
                    "transaction_id": f"pts_{uuid.uuid4().hex[:12]}",
                    "user_id": order["user_id"],
                    "points": points_earned,
                    "type": "earned",
                    "reason": f"Order #{order['order_id']}",
                    "order_id": order["order_id"],
                    "created_at": datetime.now(timezone.utc)
                }
                await db.points_transactions.insert_one(points_txn)
        
        return {
            "status": status.status,
            "payment_status": status.payment_status,
            "amount": status.amount_total / 100,
            "currency": status.currency
        }
    
    return {"payment_status": transaction["payment_status"]}

@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events"""
    body = await request.body()
    signature = request.headers.get("stripe-signature")
    
    stripe_api_key = os.environ.get("STRIPE_API_KEY")
    stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url="")
    
    try:
        webhook_response = await stripe_checkout.handle_webhook(body, signature)
        
        # Handle webhook event
        if webhook_response.event_type == "checkout.session.completed":
            # Payment successful
            await db.payment_transactions.update_one(
                {"session_id": webhook_response.session_id},
                {"$set": {"payment_status": "paid", "updated_at": datetime.now(timezone.utc)}}
            )
            
            # Update order
            transaction = await db.payment_transactions.find_one(
                {"session_id": webhook_response.session_id},
                {"_id": 0}
            )
            if transaction:
                await db.orders.update_one(
                    {"order_id": transaction["order_id"]},
                    {"$set": {"payment_status": "paid", "order_status": "confirmed"}}
                )
        
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
