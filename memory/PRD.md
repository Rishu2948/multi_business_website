# Product Requirements Document (PRD)
## Multi-Business Management Platform - Phase 1 (MVP)

---

## 1. PRODUCT OVERVIEW

### 1.1 Product Name
Multi-Business Management Platform

### 1.2 Description
A unified SaaS platform for managing four distinct businesses (Rishabh Garments, Jain Jewellers, Jain Sarees, Whisked Words) with separate inventory management, role-based access control, and public-facing product catalogs.

### 1.3 Technology Stack
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI
- **Backend**: Python FastAPI
- **Database**: MongoDB
- **Authentication**: Emergent Google OAuth
- **Deployment**: Kubernetes (Dev), AWS-ready architecture

---

## 2. USER ROLES & PERMISSIONS

### 2.1 Role Hierarchy
1. **Super Admin** - Full system access, manages all businesses
2. **Business Admin** - Manages specific business(es)
3. **Staff** - Limited access to inventory updates
4. **Customer** - Public access to browse products (no login required)

### 2.2 Permission Matrix
| Feature | Super Admin | Business Admin | Staff | Customer |
|---------|------------|----------------|-------|----------|
| View All Businesses | ✅ | ❌ | ❌ | ❌ |
| View Business Analytics | ✅ | ✅ (Own) | ❌ | ❌ |
| Manage Inventory | ✅ | ✅ (Own) | ✅ (Limited) | ❌ |
| Add/Edit Products | ✅ | ✅ (Own) | ✅ (Own) | ❌ |
| Manage Users | ✅ | ✅ (Own Staff) | ❌ | ❌ |
| Browse Products | ✅ | ✅ | ✅ | ✅ |

---

## 3. CORE FEATURES IMPLEMENTED

### 3.1 Authentication & Authorization
- ✅ Google OAuth integration (Emergent-managed)
- ✅ Role-based access control (RBAC)
- ✅ Session management with httpOnly cookies
- ✅ 7-day session expiry
- ✅ Protected route enforcement

### 3.2 Business Management
- ✅ Four businesses configured:
  - Rishabh Garments (Kids Wear)
  - Jain Jewellers (Jewellery)
  - Jain Sarees (Sarees)
  - Whisked Words (Bakery)
- ✅ Business-specific data isolation
- ✅ Business switching for multi-business users

### 3.3 Product Management
- ✅ Product CRUD operations
- ✅ Business-specific product attributes (flexible schema)
- ✅ Product variants (size, color, weight, etc.)
- ✅ Image support (multiple images per product)
- ✅ Public product catalog browsing
- ✅ Category support

### 3.4 Inventory Management
- ✅ Real-time stock tracking
- ✅ Available/Reserved/Total quantity tracking
- ✅ Low stock alerts
- ✅ Inventory movement logging
- ✅ Quick stock adjustment (+/- buttons)
- ✅ Warehouse location tracking
- ✅ Reorder level configuration

### 3.5 Analytics & Dashboard
- ✅ Super Admin: System-wide statistics
  - Total businesses, products, users
  - Low stock alerts across all businesses
- ✅ Business Admin: Business-specific stats
  - Total products
  - Inventory value
  - Low stock items
  - Out of stock items
- ✅ Real-time data updates

### 3.6 User Interface
- ✅ Swiss/High-Contrast design (Archetype 4)
- ✅ Monochrome color palette (95% black/white/gray)
- ✅ Outfit font for headings, Manrope for body
- ✅ Sharp corners (rounded-none)
- ✅ Technical grid borders for dashboards
- ✅ Responsive design (mobile-friendly)
- ✅ Sticky navigation with glass-morphism
- ✅ Hover animations and transitions

---

## 4. API ENDPOINTS IMPLEMENTED

### 4.1 Authentication
- `POST /api/auth/session` - Exchange OAuth session_id for token
- `GET /api/auth/me` - Get current user info
- `POST /api/auth/logout` - Logout user

### 4.2 Business
- `GET /api/businesses` - List businesses (filtered by role)
- `GET /api/businesses/public` - List active businesses (public)
- `GET /api/businesses/:id` - Get business details

### 4.3 Products
- `GET /api/products` - List products (public, filtered)
- `GET /api/products/:id` - Get product details
- `POST /api/products` - Create product (Admin/Staff)
- `PUT /api/products/:id` - Update product
- `DELETE /api/products/:id` - Soft delete product

### 4.4 Inventory
- `GET /api/inventory` - List inventory (filtered by business)
- `PUT /api/inventory/:id` - Update inventory (stock adjustment)
- `GET /api/inventory/low-stock` - Get low stock items

### 4.5 Analytics
- `GET /api/analytics/dashboard` - Get dashboard statistics

### 4.6 User Management
- `GET /api/users` - List users (filtered by business)
- `POST /api/users/:id/role` - Assign role to user

---

## 5. DATABASE SCHEMA

### 5.1 Collections
1. **users** - User accounts with roles
2. **user_sessions** - Authentication sessions
3. **businesses** - Business configurations
4. **products** - Product catalog
5. **inventory** - Inventory records
6. **categories** - Product categories (structure ready)

### 5.2 Key Design Decisions
- Custom `user_id` field (UUID) instead of MongoDB's `_id`
- All queries exclude `_id` using `{"_id": 0}` projection
- Flexible product attributes (JSON field)
- Business-specific access array in user documents
- Timezone-aware datetime fields

---

## 6. SAMPLE DATA SEEDED

### 6.1 Businesses
- 4 businesses with complete contact info and settings

### 6.2 Products
- 5 sample products across businesses:
  - 2 for Rishabh Garments (T-Shirt, Dress)
  - 1 for Jain Jewellers (Gold Necklace)
  - 1 for Jain Sarees (Banarasi Saree)
  - 1 for Whisked Words (Chocolate Cake)

### 6.3 Inventory
- 7 inventory records (linked to product variants)
- Varying stock levels for testing alerts

---

## 7. PAGES IMPLEMENTED

### 7.1 Public Pages
1. **Landing Page** (`/`)
   - Hero section
   - Business showcase (4 cards)
   - Features section
   - CTA section

2. **Businesses Page** (`/businesses`)
   - List all active businesses
   - Business details with location

3. **Product Catalog** (`/catalog/:businessId`)
   - Business header with logo
   - Product grid
   - Product details (price, attributes)

4. **Login Page** (`/login`)
   - Google OAuth button
   - Minimalist design

5. **Auth Callback** (`/auth-callback`)
   - Handles OAuth redirect
   - Session token exchange

### 7.2 Protected Pages
6. **Super Admin Dashboard** (`/super-admin`)
   - System-wide statistics
   - All businesses table
   - Quick action links

7. **Business Admin Dashboard** (`/admin`)
   - Business selector
   - Business-specific stats
   - Inventory management table
   - Quick stock adjustment

8. **Staff Portal** (`/staff`)
   - Business selector
   - Inventory updates only
   - Stock status indicators

---

## 8. SECURITY FEATURES

### 8.1 Authentication Security
- ✅ HttpOnly cookies (XSS protection)
- ✅ Secure flag (HTTPS only)
- ✅ SameSite=None (cross-origin support)
- ✅ 7-day session expiry with auto-cleanup

### 8.2 Authorization
- ✅ Role-based access control on all protected routes
- ✅ Business-specific access validation
- ✅ Server-side permission checks

### 8.3 Data Security
- ✅ No sensitive data in URLs or logs
- ✅ Environment variables for all configs
- ✅ CORS policy (frontend origin only)
- ✅ MongoDB injection prevention (parameterized queries)

---

## 9. DEPLOYMENT ARCHITECTURE

### 9.1 Current (Development)
- **Frontend**: React SPA on port 3000
- **Backend**: FastAPI on port 8001
- **Database**: MongoDB on localhost:27017
- **Deployment**: Kubernetes cluster

### 9.2 AWS Migration Path (Ready)
The architecture is designed for seamless AWS deployment:
- **CloudFront CDN**: Static assets + API caching
- **S3**: Static React app hosting
- **ALB**: Load balancing for backend
- **EC2 Auto-scaling**: Core API services
- **Lambda**: Background jobs (future)
- **ECS Fargate Spot**: Inventory service (cost-effective)
- **MongoDB Atlas**: Managed database

---

## 10. KNOWN LIMITATIONS (MVP Scope)

### 10.1 Features Not Implemented (Future Phases)
- ❌ Order management system
- ❌ Payment processing
- ❌ Email notifications
- ❌ Advanced search and filtering
- ❌ Customer accounts and wishlists
- ❌ Product reviews and ratings
- ❌ Multi-language support
- ❌ Image upload functionality (using placeholder images)
- ❌ CSV import/export
- ❌ Advanced analytics and reports

### 10.2 Current Constraints
- New users default to "customer" role (manual upgrade needed)
- No password reset flow (OAuth-based login)
- Limited error handling on frontend
- No bulk operations for inventory
- No audit trail UI (logs exist in database)

---

## 11. TESTING NOTES

### 11.1 Test Credentials
- **Super Admin Email**: superadmin@multibiz.com
- **Login Method**: Google OAuth (any account can login)
- **Default Role**: New users get "customer" role

### 11.2 Test Data
- 4 active businesses
- 5 sample products
- 7 inventory records with varying stock levels

### 11.3 Manual Testing Checklist
- ✅ Landing page loads with images
- ✅ Business listing page shows 4 businesses
- ✅ Product catalog displays correctly
- ✅ Login redirects to Google OAuth
- ✅ Auth callback processes session correctly
- ✅ Protected routes enforce authentication
- ✅ Role-based access works (403 for unauthorized)
- ✅ Inventory updates persist correctly
- ✅ Dashboard stats calculate accurately

---

## 12. NEXT STEPS (Phase 2)

### 12.1 High Priority
1. Add product functionality to Admin dashboard
2. Category management
3. User management UI (assign roles)
4. Advanced filtering on product catalog
5. Image upload with CDN integration

### 12.2 Medium Priority
6. Order management system
7. Customer inquiry system
8. Email notifications (low stock, orders)
9. CSV import/export for products
10. Mobile app considerations

### 12.3 Low Priority
11. Advanced analytics dashboards
12. Multi-language support
13. Theme customization per business
14. API documentation (Swagger)
15. Automated testing suite

---

## 13. PERFORMANCE METRICS

### 13.1 Page Load Times
- Landing page: < 2 seconds
- Product catalog: < 2 seconds
- Dashboards: < 3 seconds (with data fetching)

### 13.2 Database Performance
- Products query: < 100ms
- Inventory query: < 150ms
- Dashboard stats: < 200ms

### 13.3 Scalability Targets
- Support 10+ businesses
- Handle 10,000+ products
- Support 100+ concurrent users
- 99.9% uptime

---

## 14. BUSINESS VALUE

### 14.1 Key Benefits
1. **Unified Management**: Single platform for 4 diverse businesses
2. **Data Isolation**: Secure separation of business data
3. **Role-Based Access**: Granular permissions for team collaboration
4. **Real-Time Inventory**: Accurate stock tracking prevents overselling
5. **Public Catalog**: Customer browsing without login friction

### 14.2 Potential ROI
- Reduce inventory management time by 60%
- Eliminate manual stock tracking errors
- Improve team collaboration with role-based access
- Increase customer engagement with public catalogs

---

**Status**: Phase 1 (MVP) Complete ✅
**Next Milestone**: Phase 2 Enhancement Planning
**Last Updated**: March 29, 2026
