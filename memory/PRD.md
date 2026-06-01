# Jain Industries Multi-Business Platform - PRD

## Original Problem Statement
Create a multi-business platform for Jain Industries including:
- Rishabh Garments (Kid's Wear)
- Jain Jewellers (Jewellery)
- Jain Sarees (Saree)
- Whisked Words (Bakery)

Requires React frontend + FastAPI backend + MongoDB. Needs Super Admin, Business Admin, Staff, and Delivery Agent roles. Each business needs independent URLs. Specifically for Whisked Words (Bakery): full e-commerce system (cart, inventory, Razorpay/Stripe gateways) and Phase 3 features (Custom Cake Orders, Reviews, Loyalty, Subscriptions). Order Tracking with admin dashboard, delivery agent management, customer timeline. Email billing, real-time notifications, automated delivery assignment.

## Tech Stack
- **Frontend**: React (CRA + Tailwind CSS + Shadcn/UI + Framer Motion)
- **Backend**: FastAPI (Python)
- **Database**: MongoDB (Motor async driver)
- **Auth**: Emergent Google OAuth
- **Payments**: Stripe (test key in env), Razorpay (not yet integrated)
- **Email**: Plug-and-play service (Resend/SendGrid/Brevo/Mailgun/SMTP — set via EMAIL_PROVIDER env)
- **Real-time**: Server-Sent Events (SSE) for live notifications and order tracking
- **Design**: Classy Artisan Bakery Aesthetic (Playfair Display, Warm Beige/Espresso/Caramel/Sage)

## What's Been Implemented

### Platform Core
- Jain Industries umbrella with 4 businesses (seeded)
- Independent business URLs: `/business/:businessId`
- Google OAuth with session-based auth
- Role-based access control (super_admin, business_admin, staff, delivery_agent, customer)

### E-Commerce (Whisked Words)
- Full cart system, checkout, order creation with inventory reservation
- Payment: Stripe (test key), Razorpay (501), COD
- My Orders page with Track links per order

### Product Discovery
- Trending Now, Recently Viewed, Recommended For You

### Phase 3 Features
- Custom Cake Orders, Reviews (50 loyalty points), Loyalty Points (tier system), Subscriptions

### Order Tracking & Delivery
- Admin Orders Dashboard (`/admin/orders`): Stats, order list, filters, confirm/prepare/cancel
- Delivery Agent Management: Add agent via email, assign to orders, base_pincode for auto-assignment
- Delivery Dashboard (`/delivery`): Agent's assigned orders, status updates with reasons
- Customer Order Tracking (`/track/:orderId`): Vertical timeline with SSE auto-refresh
- In-App Notifications: Bell icon with unread count, dropdown, mark-all-read

### Email Billing (Plug-and-Play)
- `email_service.py`: Abstract provider interface supporting Resend, SendGrid, Brevo, Mailgun, SMTP
- Swap providers by changing `EMAIL_PROVIDER` and `EMAIL_API_KEY` in `.env`
- Beautiful branded email template (Whisked Words bakery aesthetic)
- Currently inactive (EMAIL_PROVIDER empty) — activates instantly when configured

### Real-Time Notifications (SSE)
- `sse_routes.py`: Server-Sent Events at `/api/sse/events`
- BakeryNavbar auto-updates notification bell via SSE
- OrderTrackingPage timeline auto-refreshes when status changes
- Fallback to polling if SSE unavailable

### Automated Delivery Assignment
- Auto-assigns nearest available delivery agent when admin confirms an order
- Pincode-based proximity scoring (6-digit prefix match)
- Ties broken by fewest active orders
- Admin can still manually override/reassign

### AWS Deployment Guide
- `/app/AWS_DEPLOYMENT_README.md`: Comprehensive deployment guide
- Frontend: S3 + CloudFront, Backend: ECS Fargate, DB: MongoDB Atlas (recommended)
- CI/CD, cost estimates, database comparison (Atlas vs DocumentDB vs DynamoDB vs RDS)

## Architecture
```
/app/backend/
  server.py, email_service.py, sse_routes.py, order_management_routes.py,
  ecommerce_routes.py, order_routes.py, payment_routes.py,
  custom_order_routes.py, additional_routes.py, ecommerce_models.py, seed_data.py

/app/frontend/src/
  App.js, context/ (Auth, Business, Cart), components/ (BakeryNavbar, BakeryFooter, ProtectedRoute),
  pages/ (Landing, Login, Businesses, BusinessHome, ProductCatalog, CartPage, CheckoutPage,
          OrderSuccessPage, MyOrdersPage, CustomCakeOrderPage, ReviewsPage, LoyaltyPage,
          SubscriptionsPage, AdminOrdersDashboard, DeliveryDashboard, OrderTrackingPage,
          SuperAdminDashboard, BusinessAdminDashboard, StaffDashboard)
```

## Testing
- Iteration 1: Backend 96.5%, Frontend 100%
- Iteration 2: Trending — Backend 100%, Frontend 100%
- Iteration 3: Recently Viewed + Recommended — Backend 100%, Frontend 100%
- Iteration 4: Bakery UI Redesign — Backend 100%, Frontend 95%
- Iteration 5: Order Tracking & Delivery — Backend 100% (20/20), Frontend 100% (bugs fixed)
- Iteration 6: Email/SSE/Auto-assign — Backend 100% (13/13), Frontend 100% (3/3)

## P1 — Polish
- Razorpay integration (needs API keys)
- Production Stripe/Razorpay keys
- Redis pub/sub for SSE in multi-worker deployment
- Deduplicate SSE connections (context/singleton hook)

## P2 — Future
- Additional business storefronts e-commerce
- Super Admin dashboard enhancements
- Refactor server.py into separate router modules
- Stripe/Razorpay webhooks for secure order status updates
