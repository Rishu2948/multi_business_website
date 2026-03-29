# High-Level Design (HLD) - Multi-Business Management System
## Part 3: API Architecture & Authentication Flow

---

## 10. API ARCHITECTURE

### 10.1 RESTful API Design Principles

**Base URL**: `https://yourdomain.com/api`

**Design Standards**:
- RESTful conventions (GET, POST, PUT, DELETE)
- JSON request/response format
- HTTP status codes for responses
- Bearer token authentication
- CORS enabled for frontend
- Rate limiting (future: 100 req/min per user)

### 10.2 API Route Structure

```
/api
├── /auth                        # Authentication
│   ├── GET  /me                # Get current user info
│   ├── POST /session           # Exchange session_id for session_token
│   └── POST /logout            # Logout user
│
├── /businesses                  # Business Management
│   ├── GET    /                # List all businesses (Super Admin)
│   ├── GET    /:id             # Get business details
│   ├── POST   /                # Create business (Super Admin)
│   ├── PUT    /:id             # Update business (Super Admin)
│   └── DELETE /:id             # Delete business (Super Admin)
│
├── /users                       # User Management
│   ├── GET    /                # List users (filtered by business)
│   ├── GET    /:id             # Get user details
│   ├── POST   /                # Create user (Admin)
│   ├── PUT    /:id             # Update user
│   ├── DELETE /:id             # Delete user (Admin)
│   └── POST   /:id/role        # Assign role to user
│
├── /categories                  # Product Categories
│   ├── GET    /                # List categories (by business)
│   ├── GET    /:id             # Get category details
│   ├── POST   /                # Create category
│   ├── PUT    /:id             # Update category
│   └── DELETE /:id             # Delete category
│
├── /products                    # Product Management
│   ├── GET    /                # List products (by business, public)
│   ├── GET    /:id             # Get product details (public)
│   ├── POST   /                # Create product (Admin/Staff)
│   ├── PUT    /:id             # Update product (Admin/Staff)
│   └── DELETE /:id             # Delete product (Admin)
│
├── /inventory                   # Inventory Management
│   ├── GET    /                # List inventory (by business)
│   ├── GET    /:id             # Get inventory details
│   ├── POST   /                # Create inventory record
│   ├── PUT    /:id             # Update inventory (stock adjustment)
│   ├── POST   /:id/movement    # Record inventory movement
│   └── GET    /low-stock       # Get low stock alerts
│
├── /inquiries                   # Customer Inquiries
│   ├── GET    /                # List inquiries (Admin/Staff)
│   ├── GET    /:id             # Get inquiry details
│   ├── POST   /                # Create inquiry (public)
│   ├── PUT    /:id             # Update inquiry status
│   └── DELETE /:id             # Delete inquiry
│
├── /analytics                   # Analytics & Reports
│   ├── GET /dashboard          # Get dashboard stats
│   ├── GET /inventory-summary  # Inventory summary
│   ├── GET /top-products       # Top products by business
│   └── GET /low-stock-report   # Low stock report
│
└── /audit                       # Audit Logs
    ├── GET /                   # List audit logs (Admin)
    └── GET /:id                # Get specific log entry
```

---

## 11. AUTHENTICATION & AUTHORIZATION FLOW

### 11.1 Google OAuth Flow (Emergent Integration)

```
┌──────────┐                                          ┌─────────────┐
│  User    │                                          │   Emergent  │
│ (Browser)│                                          │    OAuth    │
└────┬─────┘                                          └──────┬──────┘
     │                                                        │
     │  1. Click "Login with Google"                        │
     │────────────────────────────────────────────────────► │
     │                                                        │
     │  2. Redirect to Emergent OAuth                        │
     │    https://auth.emergentagent.com/                   │
     │    ?redirect={window.location.origin}/dashboard      │
     │◄───────────────────────────────────────────────────  │
     │                                                        │
     │  3. Google OAuth (handled by Emergent)               │
     │◄──────────────────────────────────────────────────► │
     │                                                        │
     │  4. Redirect back with session_id                    │
     │    {redirect_url}#session_id={session_id}            │
     │◄─────────────────────────────────────────────────── │
     │                                                        │
┌────▼─────┐                                          ┌──────┴──────┐
│ Frontend │                                          │   Backend   │
└────┬─────┘                                          └──────┬──────┘
     │                                                        │
     │  5. Extract session_id from URL fragment              │
     │────────────────────────────────────────────────────► │
     │    POST /api/auth/session                             │
     │    Body: { session_id }                               │
     │                                                        │
     │                    6. Backend calls Emergent API      │
     │                       GET /auth/v1/env/oauth/session-data
     │                       Header: X-Session-ID: {session_id}
     │                                                 ┌──────▼──────┐
     │                                                 │  Emergent   │
     │                                                 │   OAuth     │
     │                                                 └──────┬──────┘
     │                    7. Return user data                 │
     │                       { email, name, picture,          │
     │                         session_token }                │
     │                                                 ◄──────┘
     │                                                        │
     │  8. Store session in DB + set httpOnly cookie         │
     │    Set-Cookie: session_token=xxx;                     │
     │              HttpOnly; Secure; SameSite=None          │
     │◄─────────────────────────────────────────────────── │
     │                                                        │
     │  9. Redirect to Dashboard with user data              │
     │◄─────────────────────────────────────────────────── │
     │                                                        │
     │  10. Protected routes use session_token cookie        │
     │      for all subsequent API calls                     │
     │                                                        │
```

### 11.2 Session Management

**Session Creation**:
```python
# Backend: After OAuth callback
session_data = {
    "session_id": str(uuid.uuid4()),
    "user_id": user["user_id"],
    "session_token": emergent_session_token,
    "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
    "created_at": datetime.now(timezone.utc),
    "ip_address": request.client.host,
    "user_agent": request.headers.get("user-agent")
}
await db.user_sessions.insert_one(session_data)

# Set httpOnly cookie
response.set_cookie(
    key="session_token",
    value=emergent_session_token,
    httponly=True,
    secure=True,
    samesite="none",
    path="/",
    max_age=7*24*60*60  # 7 days
)
```

**Session Validation**:
```python
# Middleware: Check session on protected routes
async def get_current_user(request: Request):
    # Try cookie first
    session_token = request.cookies.get("session_token")
    
    # Fallback to Authorization header
    if not session_token:
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header.split(" ")[1]
    
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Validate session
    session = await db.user_sessions.find_one(
        {"session_token": session_token},
        {"_id": 0}
    )
    
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    # Check expiry
    expires_at = session["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    
    # Get user
    user = await db.users.find_one(
        {"user_id": session["user_id"]},
        {"_id": 0}
    )
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user
```

### 11.3 Role-Based Access Control (RBAC)

**Permission Checks**:
```python
# Decorator for role-based access
def require_role(allowed_roles: list):
    async def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Access forbidden")
        return current_user
    return role_checker

# Usage in routes
@app.get("/api/businesses")
async def list_businesses(
    current_user: dict = Depends(require_role(["super_admin"]))
):
    # Only super_admin can list all businesses
    pass

@app.post("/api/products")
async def create_product(
    product_data: ProductCreate,
    current_user: dict = Depends(require_role(["super_admin", "business_admin", "staff"]))
):
    # Admin and staff can create products
    pass
```

**Business-Specific Access**:
```python
# Check if user has access to specific business
async def check_business_access(user: dict, business_id: str) -> bool:
    # Super admin has access to all businesses
    if user["role"] == "super_admin":
        return True
    
    # Check business_access array
    for access in user.get("business_access", []):
        if access["business_id"] == business_id:
            return True
    
    return False

# Usage
@app.get("/api/products")
async def list_products(
    business_id: str,
    current_user: dict = Depends(get_current_user)
):
    # Public route - no auth required for viewing
    # But for modifications, check access
    if not await check_business_access(current_user, business_id):
        raise HTTPException(status_code=403, detail="Access denied")
```

---

## 12. API ENDPOINT SPECIFICATIONS

### 12.1 Authentication Endpoints

#### POST /api/auth/session
Exchange session_id for session_token after OAuth callback

**Request**:
```json
{
  "session_id": "emergent_session_id_xxx"
}
```

**Response** (200 OK):
```json
{
  "user": {
    "user_id": "user_abc123",
    "email": "admin@example.com",
    "name": "John Doe",
    "picture": "https://...",
    "role": "super_admin",
    "business_access": []
  },
  "message": "Login successful"
}
```

**Cookies Set**:
```
session_token=emergent_token_xxx; HttpOnly; Secure; SameSite=None; Path=/; Max-Age=604800
```

---

#### GET /api/auth/me
Get current authenticated user details

**Headers**:
```
Cookie: session_token=xxx
OR
Authorization: Bearer xxx
```

**Response** (200 OK):
```json
{
  "user_id": "user_abc123",
  "email": "admin@example.com",
  "name": "John Doe",
  "picture": "https://...",
  "role": "super_admin",
  "business_access": [],
  "status": "active"
}
```

---

#### POST /api/auth/logout
Logout current user

**Response** (200 OK):
```json
{
  "message": "Logged out successfully"
}
```

**Cookies Cleared**: `session_token` removed

---

### 12.2 Business Endpoints

#### GET /api/businesses
List all businesses (Super Admin only)

**Response** (200 OK):
```json
{
  "businesses": [
    {
      "business_id": "rishabh_garments",
      "business_name": "Rishabh Garments",
      "business_type": "kids_wear",
      "logo_url": "https://...",
      "status": "active"
    },
    {
      "business_id": "jain_jewellers",
      "business_name": "Jain Jewellers",
      "business_type": "jewellery",
      "logo_url": "https://...",
      "status": "active"
    }
  ],
  "total": 4
}
```

---

#### GET /api/businesses/:id
Get specific business details

**Response** (200 OK):
```json
{
  "business_id": "rishabh_garments",
  "business_name": "Rishabh Garments",
  "business_type": "kids_wear",
  "description": "Premium kids wear collection",
  "logo_url": "https://...",
  "contact": {
    "email": "contact@rishabhgarments.com",
    "phone": "+91-9876543210",
    "address": {...}
  },
  "settings": {...},
  "status": "active"
}
```

---

### 12.3 Product Endpoints

#### GET /api/products
List products (public route, filtered by business)

**Query Parameters**:
- `business_id` (required): Filter by business
- `category_id` (optional): Filter by category
- `status` (optional): Filter by status (default: active)
- `page` (optional): Page number (default: 1)
- `limit` (optional): Items per page (default: 50)

**Example**: `/api/products?business_id=rishabh_garments&category_id=cat_abc123&page=1&limit=20`

**Response** (200 OK):
```json
{
  "products": [
    {
      "product_id": "prod_abc123",
      "business_id": "rishabh_garments",
      "category_id": "cat_abc123",
      "product_name": "Boys Cotton T-Shirt",
      "description": "100% cotton, comfortable fit",
      "base_price": 499.00,
      "currency": "INR",
      "images": [...],
      "attributes": {...},
      "variants": [...],
      "status": "active"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 150,
    "total_pages": 8
  }
}
```

---

#### POST /api/products
Create new product (Admin/Staff only)

**Request**:
```json
{
  "business_id": "rishabh_garments",
  "category_id": "cat_abc123",
  "product_name": "Boys Cotton T-Shirt",
  "description": "100% cotton, comfortable fit",
  "base_price": 499.00,
  "currency": "INR",
  "images": [
    {
      "url": "https://...",
      "alt": "Front view",
      "is_primary": true
    }
  ],
  "attributes": {
    "age_group": "5-7 years",
    "sizes": ["S", "M", "L"],
    "colors": ["Red", "Blue", "Green"],
    "material": "100% Cotton",
    "brand": "RG Kids"
  },
  "variants": [
    {
      "sku": "RG-TS-001-RED-M",
      "size": "M",
      "color": "Red",
      "additional_price": 0,
      "inventory_count": 50
    }
  ]
}
```

**Response** (201 Created):
```json
{
  "product_id": "prod_abc123",
  "message": "Product created successfully"
}
```

---

### 12.4 Inventory Endpoints

#### GET /api/inventory
List inventory (filtered by business)

**Query Parameters**:
- `business_id` (required): Filter by business
- `low_stock` (optional): Show only low stock items (boolean)

**Response** (200 OK):
```json
{
  "inventory": [
    {
      "inventory_id": "inv_abc123",
      "business_id": "rishabh_garments",
      "product_id": "prod_abc123",
      "product_name": "Boys Cotton T-Shirt",
      "variant_id": "var_001",
      "sku": "RG-TS-001-RED-M",
      "quantity": {
        "available": 50,
        "reserved": 5,
        "total": 55
      },
      "reorder": {
        "reorder_level": 10,
        "reorder_quantity": 50
      },
      "last_updated": "2024-01-20T14:25:00Z"
    }
  ],
  "total": 250
}
```

---

#### PUT /api/inventory/:id
Update inventory (stock adjustment)

**Request**:
```json
{
  "quantity_change": 10,
  "movement_type": "purchase",
  "reason": "New stock arrival",
  "location": {
    "warehouse": "Main Warehouse",
    "shelf": "A-12",
    "bin": "3"
  }
}
```

**Response** (200 OK):
```json
{
  "inventory_id": "inv_abc123",
  "new_quantity": {
    "available": 60,
    "reserved": 5,
    "total": 65
  },
  "message": "Inventory updated successfully"
}
```

---

### 12.5 Analytics Endpoints

#### GET /api/analytics/dashboard
Get dashboard statistics

**Query Parameters**:
- `business_id` (optional): Filter by business (required for non-super-admin)

**Response** (200 OK):
```json
{
  "business_stats": {
    "total_products": 150,
    "total_inventory_value": 1500000.00,
    "low_stock_items": 12,
    "out_of_stock_items": 3,
    "pending_inquiries": 8
  },
  "recent_activities": [
    {
      "action": "Product Added",
      "details": "Boys Cotton T-Shirt",
      "user": "John Doe",
      "timestamp": "2024-01-20T14:25:00Z"
    }
  ]
}
```

---

## 13. ERROR HANDLING

### 13.1 Standard Error Response

All API errors return consistent format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format"
      }
    ]
  }
}
```

### 13.2 HTTP Status Codes

| Code | Meaning | Usage |
|------|---------|-------|
| 200 | OK | Successful GET/PUT request |
| 201 | Created | Successful POST request |
| 204 | No Content | Successful DELETE request |
| 400 | Bad Request | Invalid request data |
| 401 | Unauthorized | Missing/invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Duplicate resource |
| 422 | Unprocessable Entity | Validation errors |
| 500 | Internal Server Error | Server-side error |

---

**Document Status**: Part 3 Complete
**Next**: Part 4 - Frontend Architecture & Data Flow
