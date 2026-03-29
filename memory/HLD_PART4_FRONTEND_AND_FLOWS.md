# High-Level Design (HLD) - Multi-Business Management System
## Part 4: Frontend Architecture & Implementation Plan

---

## 14. FRONTEND ARCHITECTURE

### 14.1 Application Structure

```
frontend/
├── public/
│   ├── index.html
│   └── assets/
│       ├── logos/              # Business logos
│       └── images/             # Static images
│
├── src/
│   ├── index.js               # Entry point
│   ├── App.js                 # Root component with routing
│   ├── App.css                # Global styles
│   ├── index.css              # Tailwind imports
│   │
│   ├── components/            # Reusable components
│   │   ├── ui/                # Shadcn UI components
│   │   │   ├── button.jsx
│   │   │   ├── card.jsx
│   │   │   ├── dialog.jsx
│   │   │   ├── table.jsx
│   │   │   └── ...
│   │   │
│   │   ├── common/            # Common components
│   │   │   ├── Navbar.jsx
│   │   │   ├── Sidebar.jsx
│   │   │   ├── Footer.jsx
│   │   │   ├── BusinessSelector.jsx
│   │   │   ├── ProductCard.jsx
│   │   │   └── LoadingSpinner.jsx
│   │   │
│   │   └── protected/         # Auth-protected wrapper
│   │       └── ProtectedRoute.jsx
│   │
│   ├── pages/                 # Page components
│   │   ├── public/
│   │   │   ├── Landing.jsx
│   │   │   ├── Login.jsx
│   │   │   ├── AuthCallback.jsx
│   │   │   ├── CustomerPortal.jsx
│   │   │   └── ProductCatalog.jsx
│   │   │
│   │   ├── superadmin/
│   │   │   ├── SuperAdminDashboard.jsx
│   │   │   ├── BusinessManagement.jsx
│   │   │   ├── UserManagement.jsx
│   │   │   └── SystemAnalytics.jsx
│   │   │
│   │   ├── businessadmin/
│   │   │   ├── BusinessDashboard.jsx
│   │   │   ├── InventoryManagement.jsx
│   │   │   ├── ProductManagement.jsx
│   │   │   ├── StaffManagement.jsx
│   │   │   └── BusinessAnalytics.jsx
│   │   │
│   │   └── staff/
│   │       ├── StaffDashboard.jsx
│   │       ├── InventoryUpdate.jsx
│   │       └── InquiryManagement.jsx
│   │
│   ├── context/               # React Context
│   │   ├── AuthContext.jsx    # Authentication state
│   │   └── BusinessContext.jsx # Selected business state
│   │
│   ├── hooks/                 # Custom hooks
│   │   ├── useAuth.js
│   │   ├── useBusiness.js
│   │   ├── useApi.js
│   │   └── use-toast.js
│   │
│   └── utils/                 # Utility functions
│       ├── api.js             # API client
│       ├── constants.js       # App constants
│       └── helpers.js         # Helper functions
│
└── package.json
```

### 14.2 Routing Structure

```javascript
// App.js - Route definitions
<Router>
  <Routes>
    {/* Public Routes */}
    <Route path="/" element={<Landing />} />
    <Route path="/login" element={<Login />} />
    <Route path="/auth-callback" element={<AuthCallback />} />
    <Route path="/businesses" element={<CustomerPortal />} />
    <Route path="/catalog/:businessId" element={<ProductCatalog />} />
    
    {/* Protected Routes - Super Admin */}
    <Route path="/super-admin" element={
      <ProtectedRoute allowedRoles={["super_admin"]}>
        <SuperAdminDashboard />
      </ProtectedRoute>
    } />
    
    {/* Protected Routes - Business Admin */}
    <Route path="/admin" element={
      <ProtectedRoute allowedRoles={["super_admin", "business_admin"]}>
        <BusinessDashboard />
      </ProtectedRoute>
    } />
    
    {/* Protected Routes - Staff */}
    <Route path="/staff" element={
      <ProtectedRoute allowedRoles={["super_admin", "business_admin", "staff"]}>
        <StaffDashboard />
      </ProtectedRoute>
    } />
  </Routes>
</Router>
```

---

## 15. PAGE DESIGNS & USER FLOWS

### 15.1 Landing Page (Public)

**Purpose**: Homepage showcasing all 4 businesses

**Layout**:
```
┌─────────────────────────────────────────────────────────┐
│  HEADER                                                  │
│  Logo | Home | About | Contact | [Login with Google]   │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│                    HERO SECTION                          │
│     "One Platform, Four Amazing Businesses"             │
│           [Explore Our Businesses] ↓                    │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│              BUSINESS SHOWCASE (4 CARDS)                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐│
│  │ Rishabh  │  │   Jain   │  │   Jain   │  │ Whisked ││
│  │ Garments │  │ Jewellers│  │  Sarees  │  │  Words  ││
│  │ [Visit]  │  │ [Visit]  │  │ [Visit]  │  │ [Visit] ││
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘│
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│  FOOTER                                                  │
│  © 2024 Multi-Business Platform | Privacy | Terms       │
└─────────────────────────────────────────────────────────┘
```

**Features**:
- Showcase all 4 businesses with logos/images
- Brief description of each business
- "Visit" button leads to individual product catalogs
- "Login with Google" for admin/staff access

---

### 15.2 Customer Portal (Public - Business Catalog)

**Purpose**: Browse products for a specific business

**URL**: `/catalog/rishabh_garments`

**Layout**:
```
┌─────────────────────────────────────────────────────────┐
│  HEADER: Rishabh Garments                                │
│  [← Back to Home] | [Contact Us]                        │
└─────────────────────────────────────────────────────────┘
┌───────────┬─────────────────────────────────────────────┐
│ FILTERS   │         PRODUCT GRID                        │
│           │  ┌─────────┐  ┌─────────┐  ┌─────────┐    │
│ Category  │  │ Product │  │ Product │  │ Product │    │
│ □ Shirts  │  │  Image  │  │  Image  │  │  Image  │    │
│ □ Pants   │  │  ₹499   │  │  ₹599   │  │  ₹399   │    │
│ □ Dresses │  │ [View]  │  │ [View]  │  │ [View]  │    │
│           │  └─────────┘  └─────────┘  └─────────┘    │
│ Size      │                                             │
│ □ S       │  Pagination: [1] [2] [3] ... [10]          │
│ □ M       │                                             │
│ □ L       │                                             │
└───────────┴─────────────────────────────────────────────┘
```

**Features**:
- Filter by category, size, price range
- Product grid with images, prices
- Product detail modal (no cart/checkout in MVP)
- Contact/Inquiry form for product questions

---

### 15.3 Login Page

**Purpose**: OAuth login for admin/staff users

**Layout**:
```
┌─────────────────────────────────────────────────────────┐
│                                                          │
│                    [Business Logo]                       │
│                                                          │
│              Multi-Business Admin Portal                │
│                                                          │
│        ┌──────────────────────────────────┐            │
│        │                                   │            │
│        │   [🔐 Login with Google]         │            │
│        │                                   │            │
│        └──────────────────────────────────┘            │
│                                                          │
│           For admin and staff access only               │
│                                                          │
│               [← Back to Homepage]                      │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

**Flow**:
1. Click "Login with Google"
2. Redirect to Emergent OAuth
3. After auth, redirect to AuthCallback
4. Process session_id → redirect to appropriate dashboard

---

### 15.4 Super Admin Dashboard

**Purpose**: System-wide overview and management

**URL**: `/super-admin`

**Layout**:
```
┌─────────────────────────────────────────────────────────┐
│  HEADER: Super Admin Dashboard                          │
│  👤 John Doe | [Logout]                                 │
└─────────────────────────────────────────────────────────┘
┌───────────┬─────────────────────────────────────────────┐
│ SIDEBAR   │         DASHBOARD CONTENT                   │
│           │                                              │
│ Dashboard │  ┌───────────┐ ┌───────────┐ ┌──────────┐ │
│ Businesses│  │  Total    │ │  Total    │ │  Total   │ │
│ Users     │  │ Products  │ │ Inventory │ │  Users   │ │
│ Analytics │  │   600     │ │ ₹5.2M     │ │   45     │ │
│ Settings  │  └───────────┘ └───────────┘ └──────────┘ │
│           │                                              │
│           │  BUSINESS OVERVIEW (TABLE)                  │
│           │  ┌──────────────────────────────────────┐  │
│           │  │ Business    │ Products │ Inventory   │  │
│           │  │─────────────┼──────────┼────────────│  │
│           │  │ Rishabh G.  │   150    │  ₹1.5M     │  │
│           │  │ Jain Jew.   │   200    │  ₹2.8M     │  │
│           │  │ Jain Sarees │   180    │  ₹800K     │  │
│           │  │ Whisked W.  │    70    │  ₹100K     │  │
│           │  └──────────────────────────────────────┘  │
│           │                                              │
└───────────┴─────────────────────────────────────────────┘
```

**Features**:
- System-wide statistics
- All business overview
- User management (create, edit, delete users)
- Assign roles and business access
- View audit logs

---

### 15.5 Business Admin Dashboard

**Purpose**: Manage single business operations

**URL**: `/admin`

**Layout**:
```
┌─────────────────────────────────────────────────────────┐
│  HEADER: Business Admin Dashboard                       │
│  Business: [Rishabh Garments ▼] | 👤 Jane Doe | Logout │
└─────────────────────────────────────────────────────────┘
┌───────────┬─────────────────────────────────────────────┐
│ SIDEBAR   │         DASHBOARD CONTENT                   │
│           │                                              │
│ Dashboard │  ┌───────────┐ ┌───────────┐ ┌──────────┐ │
│ Products  │  │  Total    │ │ Low Stock │ │ Pending  │ │
│ Inventory │  │ Products  │ │   Items   │ │Inquiries │ │
│ Staff     │  │   150     │ │    12     │ │    8     │ │
│ Inquiries │  └───────────┘ └───────────┘ └──────────┘ │
│ Analytics │                                              │
│           │  INVENTORY ALERTS                           │
│           │  ┌──────────────────────────────────────┐  │
│           │  │ Product      │ Current │ Reorder    │  │
│           │  │──────────────┼─────────┼───────────│  │
│           │  │ T-Shirt Red  │    5    │    10      │  │
│           │  │ Pants Blue   │    8    │    15      │  │
│           │  └──────────────────────────────────────┘  │
│           │                                              │
└───────────┴─────────────────────────────────────────────┘
```

**Features**:
- Business-specific statistics
- Product management (CRUD operations)
- Inventory management (stock updates)
- Staff management (assign staff to business)
- View and respond to inquiries
- Business analytics

---

### 15.6 Inventory Management Page

**Purpose**: Manage inventory for business

**URL**: `/admin/inventory`

**Layout**:
```
┌─────────────────────────────────────────────────────────┐
│  Inventory Management | Business: Rishabh Garments      │
│  [+ Add Stock] [Export CSV] [Filter ▼]                 │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│  INVENTORY TABLE                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ SKU        │ Product    │ Available │ Actions    │  │
│  │────────────┼────────────┼───────────┼───────────│  │
│  │ RG-TS-001  │ T-Shirt    │    50     │ [Edit][+/-]│  │
│  │ RG-PT-002  │ Pants      │    8 ⚠️   │ [Edit][+/-]│  │
│  │ RG-DR-003  │ Dress      │    30     │ [Edit][+/-]│  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  Legend: ⚠️ Low Stock (< 10 items)                      │
└─────────────────────────────────────────────────────────┘

[Stock Update Modal]
┌─────────────────────────────────────┐
│  Update Stock: T-Shirt Red (M)     │
│                                     │
│  Current: 50                        │
│  Adjustment: [+10▼] [Reason]       │
│  New Total: 60                      │
│                                     │
│  [Cancel] [Update]                 │
└─────────────────────────────────────┘
```

**Features**:
- View all inventory items
- Quick stock adjustment (+/- buttons)
- Low stock alerts (red/yellow indicators)
- Bulk import/export (CSV)
- Filter by category, low stock

---

### 15.7 Product Management Page

**Purpose**: Create and manage products

**URL**: `/admin/products`

**Layout**:
```
┌─────────────────────────────────────────────────────────┐
│  Product Management | Business: Jain Jewellers          │
│  [+ Add Product] [Categories] [Filter ▼]               │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│  PRODUCT GRID                                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐       │
│  │  [Image]   │  │  [Image]   │  │  [Image]   │       │
│  │ Gold Ring  │  │Gold Necklace│ │  Earrings  │       │
│  │ ₹45,000    │  │ ₹85,000    │  │ ₹25,000    │       │
│  │ [Edit][Del]│  │ [Edit][Del]│  │ [Edit][Del]│       │
│  └────────────┘  └────────────┘  └────────────┘       │
└─────────────────────────────────────────────────────────┘

[Add Product Form]
┌─────────────────────────────────────────────────────────┐
│  Add New Product                                         │
│  Product Name: [_____________________]                  │
│  Category: [Necklaces ▼]                                │
│  Price: ₹ [_____]                                       │
│  Description: [________________________]                │
│  Images: [Upload]                                        │
│                                                          │
│  Business-Specific Attributes:                          │
│  Metal Type: [Gold ▼]                                   │
│  Purity: [22K ▼]                                        │
│  Weight: [___] grams                                    │
│  Stone: [Ruby ▼]                                        │
│                                                          │
│  [Cancel] [Save Product]                                │
└─────────────────────────────────────────────────────────┘
```

**Features**:
- Product CRUD operations
- Business-specific attribute fields (dynamic based on business type)
- Image upload (multiple images per product)
- Variant management (size, color)
- Category assignment

---

## 16. DATA FLOW DIAGRAMS

### 16.1 Authentication Flow

```
┌─────────┐                 ┌──────────┐                ┌─────────┐
│ Browser │                 │ Frontend │                │ Backend │
└────┬────┘                 └────┬─────┘                └────┬────┘
     │                            │                           │
     │  1. Click "Login"          │                           │
     ├───────────────────────────►│                           │
     │                            │                           │
     │  2. Redirect to OAuth      │                           │
     │◄───────────────────────────┤                           │
     │                            │                           │
     │  3. OAuth (external)       │                           │
     │◄──────────────────────────►│                           │
     │                            │                           │
     │  4. Return with session_id │                           │
     │───────────────────────────►│                           │
     │                            │                           │
     │                            │  5. POST /api/auth/session│
     │                            ├──────────────────────────►│
     │                            │  { session_id }           │
     │                            │                           │
     │                            │  6. Validate with Emergent│
     │                            │◄─────────────────────────►│
     │                            │                           │
     │                            │  7. Store session + cookie│
     │                            │◄──────────────────────────┤
     │                            │  Set-Cookie: session_token│
     │                            │                           │
     │  8. Redirect to dashboard  │                           │
     │◄───────────────────────────┤                           │
     │                            │                           │
```

### 16.2 Product Browsing Flow (Public)

```
┌─────────┐                 ┌──────────┐                ┌─────────┐
│Customer │                 │ Frontend │                │ Backend │
└────┬────┘                 └────┬─────┘                └────┬────┘
     │                            │                           │
     │  1. Visit catalog page     │                           │
     ├───────────────────────────►│                           │
     │                            │                           │
     │                            │  2. GET /api/products?    │
     │                            │     business_id=xxx       │
     │                            ├──────────────────────────►│
     │                            │                           │
     │                            │  3. Query MongoDB         │
     │                            │     (no auth required)    │
     │                            │◄──────────────────────────┤
     │                            │  { products: [...] }      │
     │                            │                           │
     │  4. Display products       │                           │
     │◄───────────────────────────┤                           │
     │                            │                           │
     │  5. Click product          │                           │
     ├───────────────────────────►│                           │
     │                            │                           │
     │  6. Show details modal     │                           │
     │◄───────────────────────────┤                           │
     │                            │                           │
```

### 16.3 Inventory Update Flow (Protected)

```
┌─────────┐                 ┌──────────┐                ┌─────────┐
│  Admin  │                 │ Frontend │                │ Backend │
└────┬────┘                 └────┬─────┘                └────┬────┘
     │                            │                           │
     │  1. Open inventory page    │                           │
     ├───────────────────────────►│                           │
     │                            │                           │
     │                            │  2. GET /api/inventory    │
     │                            │     Cookie: session_token │
     │                            ├──────────────────────────►│
     │                            │                           │
     │                            │  3. Validate session      │
     │                            │     Check RBAC            │
     │                            │◄──────────────────────────┤
     │                            │  { inventory: [...] }     │
     │                            │                           │
     │  4. Display inventory      │                           │
     │◄───────────────────────────┤                           │
     │                            │                           │
     │  5. Update stock (+10)     │                           │
     ├───────────────────────────►│                           │
     │                            │                           │
     │                            │  6. PUT /api/inventory/123│
     │                            │     { quantity_change: 10 }│
     │                            ├──────────────────────────►│
     │                            │                           │
     │                            │  7. Update MongoDB        │
     │                            │     Log audit trail       │
     │                            │◄──────────────────────────┤
     │                            │  { new_quantity: 60 }     │
     │                            │                           │
     │  8. Show success message   │                           │
     │◄───────────────────────────┤                           │
     │                            │                           │
```

---

## 17. SECURITY CONSIDERATIONS

### 17.1 Authentication Security
- HttpOnly cookies prevent XSS attacks
- Secure flag ensures HTTPS-only transmission
- SameSite=None for cross-origin requests
- 7-day session expiry with automatic cleanup

### 17.2 Authorization
- Role-based access control (RBAC) on all protected routes
- Business-specific access validation
- Audit logging for all sensitive operations

### 17.3 Data Validation
- Backend validation for all inputs
- MongoDB injection prevention (parameterized queries)
- File upload restrictions (image types, size limits)

### 17.4 CORS Policy
```python
# Allow frontend origin only
allow_origins=[os.getenv("FRONTEND_URL")]
allow_credentials=True
```

---

## 18. IMPLEMENTATION PHASES

### Phase 1: Foundation (MVP)
1. **Setup & Configuration**
   - MongoDB database setup
   - Seed initial business data
   - Environment configuration

2. **Authentication**
   - Google OAuth integration
   - Session management
   - Protected route implementation

3. **Core Backend**
   - User management API
   - Business API
   - Product API
   - Inventory API

4. **Core Frontend**
   - Landing page
   - Login flow
   - Customer portal (product browsing)
   - Super Admin dashboard
   - Business Admin dashboard

### Phase 2: Enhancement
1. Order management system
2. Advanced analytics
3. Email notifications
4. Image CDN integration
5. Search and filtering

### Phase 3: Optimization
1. Performance optimization
2. Caching strategy
3. AWS deployment
4. Mobile responsiveness
5. SEO optimization

---

**Document Status**: Part 4 Complete
**HLD Document Complete** ✅

All 4 parts created:
1. Part 1: System Overview & Architecture
2. Part 2: Database Schema Design
3. Part 3: API Architecture & Authentication Flow
4. Part 4: Frontend Architecture & Implementation Plan

**Next Step**: Begin implementation of Phase 1 (Foundation/MVP)
