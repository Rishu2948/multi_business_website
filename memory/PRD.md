# Jain Industries Multi-Business Platform - PRD

## Original Problem Statement
Create a multi-business platform for Jain Industries including:
- Rishabh Garments (Kid's Wear)
- Jain Jewellers (Jewellery)
- Jain Sarees (Saree)
- Whisked Words (Bakery)

Requires React frontend + FastAPI backend + MongoDB. Needs Super Admin, Business Admin, Staff, and Delivery Agent roles. Each business needs independent URLs. Specifically for Whisked Words (Bakery): full e-commerce system (cart, inventory, Razorpay/Stripe gateways) and Phase 3 features (Custom Cake Orders, Reviews, Loyalty, Subscriptions). Order Tracking with admin dashboard, delivery agent management, customer timeline. Email bill on order confirmation (deferred by user).

## Tech Stack
- **Frontend**: React (CRA + Tailwind CSS + Shadcn/UI + Framer Motion)
- **Backend**: FastAPI (Python)
- **Database**: MongoDB (Motor async driver)
- **Auth**: Emergent Google OAuth
- **Payments**: Stripe (test key in env), Razorpay (not yet integrated)
- **Design**: Classy Artisan Bakery Aesthetic (Playfair Display, Warm Beige/Espresso/Caramel/Sage)

## User Personas
1. **Super Admin** - manages all 4 businesses, sees system-wide stats
2. **Business Admin** - manages products/inventory, order management, assigns delivery agents
3. **Staff** - views and manages inventory
4. **Delivery Agent** - views assigned orders, updates delivery status
5. **Customer** - browses, orders, tracks, earns loyalty, subscribes

## What's Been Implemented

### Platform Core
- Jain Industries umbrella with 4 businesses (seeded)
- Independent business URLs: `/business/:businessId`
- Google OAuth with session-based auth
- Role-based access control (super_admin, business_admin, staff, delivery_agent, customer)
- Product catalog per business
- Business admin dashboard with inventory management

### E-Commerce (Whisked Words)
- Full cart system (add, update, remove, clear)
- Checkout with delivery info + payment method selection
- Order creation with inventory reservation
- Payment integration: Stripe (test key), Razorpay (501), COD
- Stripe webhook handling
- Order success page with payment status polling
- My Orders page with order status tracking + Track links

### Product Discovery
- **Trending Now**: Auto-ranked by order count + reviews
- **Recently Viewed**: localStorage + server-side DB tracking
- **Recommended For You**: Smart recommendations (category_match, also_bought, discovery, top_rated)

### Phase 3 Features
- **Custom Cake Orders**: Multi-step form
- **Reviews**: Create review per product (50 loyalty points)
- **Loyalty Points**: Tier system (Bronze -> Platinum)
- **Subscriptions**: Recurring delivery subscriptions

### Order Tracking & Delivery (NEW - Verified)
- **Admin Orders Dashboard** (`/admin/orders`): Stats cards, order list, status filters, confirm/prepare/cancel actions
- **Delivery Agent Management**: Add agent via email search, manual assignment to orders
- **Delivery Dashboard** (`/delivery`): Agent's assigned orders, status updates (on_the_way, reached_doorstep, delivered, not_delivered with reasons)
- **Customer Order Tracking** (`/track/:orderId`): Vertical timeline visualization (pending -> confirmed -> preparing -> on_the_way -> reached_doorstep -> delivered)
- **In-App Notifications**: Bell icon with unread count, dropdown, mark-all-read, links to order tracking

### UI/Design
- Bakery Theme: Playfair Display + Manrope, Warm Beige #FAF8F5, Espresso #4A3B32, Caramel #D4A373, Sage #A3B18A
- Custom BakeryNavbar (centered serif logo, notification bell) and BakeryFooter
- Framer Motion animations, scrolling marquee, editorial product cards

## Architecture
```
/app/backend/
  server.py (main app + auth + products/inventory/users/analytics)
  ecommerce_routes.py (cart CRUD)
  order_routes.py (orders)
  payment_routes.py (payments)
  custom_order_routes.py (custom cake orders)
  additional_routes.py (reviews/loyalty/subscriptions)
  order_management_routes.py (admin orders, delivery, notifications, tracking)
  ecommerce_models.py (Pydantic models)
  seed_data.py

/app/frontend/src/
  App.js (routing)
  context/ (AuthContext, BusinessContext, CartContext)
  components/common/ (BakeryNavbar, BakeryFooter)
  components/protected/ (ProtectedRoute)
  pages/ (Landing, Login, Businesses, BusinessHome, ProductCatalog,
          CartPage, CheckoutPage, OrderSuccessPage, MyOrdersPage,
          CustomCakeOrderPage, ReviewsPage, LoyaltyPage, SubscriptionsPage,
          AdminOrdersDashboard, DeliveryDashboard, OrderTrackingPage,
          SuperAdminDashboard, BusinessAdminDashboard, StaffDashboard)
  utils/api.js
```

## Key API Endpoints
- `/api/order-management/orders` - Admin: list all orders
- `/api/order-management/orders/stats` - Admin: order stats
- `/api/order-management/orders/{id}/status` - Admin: update status
- `/api/order-management/orders/{id}/assign` - Admin: assign delivery agent
- `/api/order-management/delivery-agents` - Admin: list delivery agents
- `/api/order-management/users/{id}/make-delivery-agent` - Admin: promote user
- `/api/order-management/delivery/my-orders` - Agent: assigned orders
- `/api/order-management/delivery/orders/{id}/status` - Agent: update delivery status
- `/api/order-management/notifications` - User: get notifications
- `/api/order-management/track/{id}` - User: order tracking timeline
- `/api/users/search` - Admin: search users by email

## Testing
- Iteration 1: Backend 96.5%, Frontend 100% (order variant_id fix)
- Iteration 2: Trending feature - Backend 100%, Frontend 100%
- Iteration 3: Recently Viewed + Recommended - Backend 100%, Frontend 100%
- Iteration 4: Bakery UI Redesign - Backend 100%, Frontend 95%
- Iteration 5: Order Tracking & Delivery - Backend 100% (20/20), Frontend 85% -> 100% (bugs fixed: MyOrdersPage auth race, server.py expires_at KeyError, DeliveryDashboard UX)

## P0 - Next Steps
- Email bill on order confirmation via Resend (deferred by user)

## P1 - Polish
- Automated delivery partner assignment based on location
- Razorpay integration (needs API keys)
- Production Stripe/Razorpay keys

## P2 - Future
- Additional business storefronts e-commerce
- Super Admin dashboard enhancements
- Refactor server.py into separate router modules
- Stripe/Razorpay webhooks for secure order status updates
