# High-Level Design (HLD) - Multi-Business Management System
## Part 1: System Overview & Architecture

---

## 1. SYSTEM OVERVIEW

### 1.1 Project Scope
A unified web-based platform managing four distinct businesses under one umbrella system:
- **Rishabh Garments** - Kid's wear retail business
- **Jain Jewellers** - Jewellery retail business  
- **Jain Sarees** - Saree retail business
- **Whisked Words** - Bakery business

### 1.2 Key Objectives
1. Centralized multi-business management with isolated data
2. Role-based access control (RBAC) across all businesses
3. Independent inventory management per business
4. Customer portal for browsing and inquiries
5. Admin/Staff portals for business operations
6. Scalable architecture ready for cloud deployment

### 1.3 Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React 18+ | Single-page application with routing |
| Backend | FastAPI (Python) | RESTful API server |
| Database | MongoDB | NoSQL database for flexible schema |
| Authentication | Emergent Google OAuth | Hassle-free authentication |
| Styling | Tailwind CSS | Modern, responsive UI |
| State Management | React Context/Hooks | Client-side state |

---

## 2. SYSTEM ARCHITECTURE

### 2.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              React Frontend (SPA)                    │   │
│  │  - Customer Portal   - Admin Dashboard              │   │
│  │  - Business Selector - Inventory Management          │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↕ HTTPS (REST API)
┌─────────────────────────────────────────────────────────────┐
│                      API GATEWAY LAYER                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              FastAPI Backend Server                  │   │
│  │  - Authentication Middleware                         │   │
│  │  - Authorization (RBAC)                              │   │
│  │  - Business Logic Layer                              │   │
│  │  - API Route Handlers                                │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                     AUTHENTICATION LAYER                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         Emergent Google OAuth Service                │   │
│  │  - Session Management                                │   │
│  │  - Token Validation                                  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                       DATA LAYER                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              MongoDB Database                        │   │
│  │  Collections:                                        │   │
│  │  - users                - user_sessions              │   │
│  │  - businesses          - inventory                   │   │
│  │  - products            - orders                      │   │
│  │  - customers           - staff                       │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Component Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    FRONTEND MODULES                         │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Landing    │  │    Auth      │  │   Business   │    │
│  │     Page     │  │   Callback   │  │   Selector   │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │            CUSTOMER PORTAL (PUBLIC)                   │ │
│  │  - Browse Products  - View Catalog  - Contact        │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │         SUPER ADMIN DASHBOARD (PROTECTED)             │ │
│  │  - All Business Overview  - User Management          │ │
│  │  - Analytics Dashboard    - System Settings           │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │       BUSINESS ADMIN DASHBOARD (PROTECTED)            │ │
│  │  - Inventory Management   - Order Management          │ │
│  │  - Staff Management       - Business Analytics        │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │          STAFF PORTAL (PROTECTED)                     │ │
│  │  - Inventory Updates    - Order Processing            │ │
│  │  - Customer Inquiries                                 │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

### 2.3 Backend Module Structure

```
backend/
├── server.py                    # Main FastAPI application
├── models/                      # Pydantic models & schemas
│   ├── user.py
│   ├── business.py
│   ├── product.py
│   ├── inventory.py
│   └── order.py
├── routes/                      # API route handlers
│   ├── auth.py                  # Authentication endpoints
│   ├── business.py              # Business management
│   ├── inventory.py             # Inventory operations
│   ├── products.py              # Product CRUD
│   ├── orders.py                # Order management
│   └── users.py                 # User management
├── middleware/                  # Custom middleware
│   ├── auth.py                  # Auth middleware
│   └── rbac.py                  # Role-based access control
├── utils/                       # Utility functions
│   ├── db.py                    # Database connection
│   └── helpers.py               # Helper functions
└── requirements.txt             # Python dependencies
```

---

## 3. USER ROLES & PERMISSIONS

### 3.1 Role Hierarchy

```
                    ┌─────────────────┐
                    │   Super Admin   │
                    │  (All Access)   │
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
    ┌───────▼──────┐  ┌─────▼──────┐  ┌─────▼──────┐
    │  Business 1  │  │ Business 2  │  │ Business 3  │
    │    Admin     │  │   Admin     │  │   Admin     │
    └───────┬──────┘  └─────┬──────┘  └─────┬──────┘
            │                │                │
    ┌───────▼──────┐  ┌─────▼──────┐  ┌─────▼──────┐
    │   Staff 1    │  │  Staff 2    │  │  Staff 3    │
    │  (Limited)   │  │ (Limited)   │  │ (Limited)   │
    └──────────────┘  └─────────────┘  └─────────────┘

    ┌──────────────────────────────────────────────────┐
    │              Customers (Public)                   │
    │         (Read-only, No Login Required)            │
    └──────────────────────────────────────────────────┘
```

### 3.2 Permission Matrix

| Feature | Super Admin | Business Admin | Staff | Customer |
|---------|-------------|----------------|-------|----------|
| View All Businesses | ✅ | ❌ | ❌ | ❌ |
| Manage Users (All) | ✅ | ❌ | ❌ | ❌ |
| System Settings | ✅ | ❌ | ❌ | ❌ |
| View Business Analytics | ✅ | ✅ (Own) | ❌ | ❌ |
| Manage Inventory | ✅ | ✅ (Own) | ✅ (Limited) | ❌ |
| Add/Edit Products | ✅ | ✅ (Own) | ✅ (Own) | ❌ |
| View Orders | ✅ | ✅ (Own) | ✅ (Own) | ❌ |
| Manage Staff | ✅ | ✅ (Own) | ❌ | ❌ |
| Browse Products | ✅ | ✅ | ✅ | ✅ |
| Contact/Inquiry | ✅ | ✅ | ✅ | ✅ |

---

## 4. BUSINESS CONFIGURATION

### 4.1 Business Entities

Each business has unique characteristics:

| Business ID | Name | Type | Inventory Type |
|-------------|------|------|----------------|
| `rishabh_garments` | Rishabh Garments | Kid's Wear | Clothing (size, color, age group) |
| `jain_jewellers` | Jain Jewellers | Jewellery | Jewellery (weight, purity, type) |
| `jain_sarees` | Jain Sarees | Saree | Textile (fabric, design, length) |
| `whisked_words` | Whisked Words | Bakery | Food Items (weight, ingredients, shelf life) |

### 4.2 Business-Specific Data Isolation

Each business maintains:
- Separate inventory records
- Separate product catalogs
- Separate staff assignments
- Separate analytics/reports
- Shared customer database (optional)

---

## 5. DEPLOYMENT ARCHITECTURE (AWS READY)

### 5.1 Kubernetes to AWS Migration Path

**Current Environment**: Kubernetes (Dev/Staging)
**Target Environment**: AWS Cloud

```
┌────────────────────────────────────────────────────────┐
│                    CloudFront CDN                       │
│         (Static Assets + API Gateway Cache)            │
└───────────────────────┬────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
   ┌────▼─────┐                  ┌─────▼─────┐
   │  S3      │                  │    ALB    │
   │ (Static) │                  │  (API)    │
   └──────────┘                  └─────┬─────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
              ┌─────▼──────┐    ┌─────▼──────┐    ┌─────▼──────┐
              │   EC2      │    │  Lambda    │    │  Fargate   │
              │ (Backend)  │    │ (Compute)  │    │  (Spot)    │
              └─────┬──────┘    └─────┬──────┘    └─────┬──────┘
                    │                  │                  │
                    └──────────────────┼──────────────────┘
                                       │
                                ┌──────▼──────┐
                                │  MongoDB    │
                                │   Atlas     │
                                └─────────────┘
```

### 5.2 Service Deployment Strategy

| Service | AWS Service | Purpose |
|---------|------------|---------|
| Frontend | S3 + CloudFront | Static React app hosting |
| API Gateway | ALB + CloudFront | Load balancing & caching |
| Core API | EC2 (Auto-scaling) | Main backend services |
| Background Jobs | Lambda | Async tasks (reports, emails) |
| Inventory Service | ECS Fargate Spot | Cost-effective compute |
| Database | MongoDB Atlas | Managed MongoDB |
| Auth | Emergent OAuth | Managed authentication |

---

## 6. SCALABILITY CONSIDERATIONS

### 6.1 Horizontal Scaling
- **Frontend**: CDN distribution via CloudFront
- **Backend**: Auto-scaling EC2 instances behind ALB
- **Database**: MongoDB sharding (by business_id)

### 6.2 Caching Strategy
- **Frontend**: CloudFront edge caching (static assets)
- **API**: Redis cache for frequently accessed data
- **Database**: MongoDB indexes on query-heavy fields

### 6.3 Performance Optimization
- Lazy loading for business-specific modules
- API response pagination (limit 50 items)
- Image optimization and CDN delivery
- Database connection pooling

---

**Document Status**: Part 1 Complete
**Next**: Part 2 - Database Schema Design
