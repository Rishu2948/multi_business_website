from fastapi import APIRouter, HTTPException, Request
from datetime import datetime, timezone
import uuid
import os

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
        
        raise HTTPException(
            status_code=501,
            detail="Stripe integration is not yet fully implemented. Please use the official stripe python package."
        )
    
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
        raise HTTPException(
            status_code=501,
            detail="Stripe integration is not yet fully implemented."
        )
    
    return {"payment_status": transaction["payment_status"]}

@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events"""
    body = await request.body()
    signature = request.headers.get("stripe-signature")
    
    raise HTTPException(
        status_code=501,
        detail="Stripe integration is not yet fully implemented."
    )
