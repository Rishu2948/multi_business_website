# Jain Industries Multi-Business Platform — PRD

## Original Problem Statement
Create a multi-business platform for Jain Industries including:
- Rishabh Garments (Kid's Wear)
- Jain Jewellers (Jewellery)
- Jain Sarees (Saree)
- Whisked Words (Bakery)

Requires React frontend + FastAPI backend + MongoDB. Needs Super Admin, Business Admin, and Staff roles. Each business needs independent URLs. Specifically for Whisked Words (Bakery): full e-commerce system (cart, inventory, Razorpay/Stripe gateways) and Phase 3 features (Custom Cake Orders, Reviews, Loyalty, Subscriptions). Send email bill on order confirmation (deferred by user).

## Tech Stack
- **Frontend**: React (CRA + Tailwind CSS + Shadcn/UI components)
- **Backend**: FastAPI (Python)
- **Database**: MongoDB (Motor async driver)
- **Auth**: Emergent Google OAuth
- **Payments**: Stripe (test key in env), Razorpay (not yet integrated — returns 501)
- **Design**: Swiss & High-Contrast Archetype (Archetype 4)

## User Personas
1. **Super Admin** — manages all 4 businesses, sees system-wide stats
2. **Business Admin** — manages products/inventory for assigned business
3. **Staff** — views and manages inventory
4. **Customer** — browses, adds to cart, orders, writes reviews, earns loyalty points, creates subscriptions

## What's Been Implemented

### Platform Core
- Jain Industries umbrella with 4 businesses (seeded)
- Independent business URLs: `/business/:businessId`
- Google OAuth with session-based auth
- Role-based access control (super_admin, business_admin, staff, customer)
- Product catalog per business
- Business admin dashboard with inventory management

### E-Commerce (Whisked Words)
- Full cart system (add, update, remove, clear)
- Checkout with delivery info + payment method selection
- Order creation with inventory reservation
- Payment integration: Stripe (test key), Razorpay (501 — needs keys), COD
- Stripe webhook handling
- Order success page with payment status polling
- My Orders page with order status tracking

### Phase 3 Features
- **Custom Cake Orders**: Multi-step form (cake details → delivery → contact)
- **Reviews**: Create review per product (awards 50 loyalty points), view reviews with star ratings
- **Loyalty Points**: Points balance, tier system (Bronze→Silver→Gold→Platinum), tier progress, transaction history
- **Subscriptions**: Create/manage recurring delivery subscriptions with pause/resume/cancel

### Admin Features
- Business Admin Dashboard with stats (products, inventory value, low stock, out of stock)
- Inventory management table with ± stock adjustments
- Add Product modal for creating new products

### Navigation
- Navbar: BUSINESSES, ORDERS, REWARDS, SUBSCRIBE (when authenticated), Cart, Dashboard, Logout
- Product catalog: "Custom Cake Order" button, "View Reviews" links per product

## Architecture
```
/app/backend/
├── server.py (main app + auth + products/inventory/users/analytics)
├── ecommerce_routes.py (cart CRUD at /api/ecommerce/*)
├── order_routes.py (orders at /api/orders/*)
├── payment_routes.py (payments at /api/payments/*)
├── custom_order_routes.py (custom cake orders at /api/custom-orders/*)
├── additional_routes.py (reviews/loyalty/subscriptions)
├── ecommerce_models.py (Pydantic models)
└── seed_data.py

/app/frontend/src/
├── App.js (routing)
├── context/ (AuthContext, BusinessContext, CartContext)
├── components/ (Navbar, Footer, AddProductModal, ProtectedRoute)
├── pages/ (Landing, Login, Businesses, BusinessHome, ProductCatalog,
│           CartPage, CheckoutPage, OrderSuccessPage, MyOrdersPage,
│           CustomCakeOrderPage, ReviewsPage, LoyaltyPage, SubscriptionsPage,
│           SuperAdminDashboard, BusinessAdminDashboard, StaffDashboard)
└── utils/api.js
```

## P0 — Remaining / Next Steps
- Email bill on order confirmation (deferred by user request)
- Razorpay integration (needs API keys)

## P1 — Polish
- Group inventory variants under single product row in admin dashboard
- Production Stripe/Razorpay keys

## P2 — Future
- Additional business storefronts (Rishabh Garments, Jain Jewellers, Jain Sarees e-commerce)
- Super Admin dashboard enhancements
- Refactor server.py into central router file

## Testing
- Backend: 96.5% pass rate (28/29), order creation variant_id fix applied
- Frontend: 100% critical flows working
- Test report: /app/test_reports/iteration_1.json
