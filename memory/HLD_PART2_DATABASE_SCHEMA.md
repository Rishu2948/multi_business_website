# High-Level Design (HLD) - Multi-Business Management System
## Part 2: Database Schema Design

---

## 7. DATABASE DESIGN

### 7.1 Database Selection Rationale

**Choice**: MongoDB (NoSQL Document Database)

**Reasons**:
1. **Flexible Schema**: Each business has different inventory attributes
   - Garments: size, color, age_group
   - Jewellery: weight, purity, stone_type
   - Sarees: fabric, design, length
   - Bakery: ingredients, shelf_life, allergens

2. **Document-Oriented**: Natural fit for hierarchical business data
3. **Horizontal Scaling**: Built-in sharding support
4. **Rich Queries**: Aggregation pipeline for analytics
5. **JSON-like Structure**: Seamless integration with FastAPI/React

### 7.2 Collections Overview

```
MongoDB Database: multi_business_platform
├── users                  # All users (admin, staff, customers)
├── user_sessions         # Authentication sessions
├── businesses            # Business configurations
├── inventory             # Inventory records per business
├── products              # Product catalog
├── categories            # Product categories
├── orders                # Order management
├── inquiries             # Customer inquiries
└── audit_logs            # System audit trail
```

---

## 8. DETAILED SCHEMA DESIGN

### 8.1 Users Collection

**Purpose**: Store all user accounts with role-based access

```javascript
{
  "user_id": "user_abc123def456",           // Custom UUID (MongoDB _id excluded)
  "email": "admin@example.com",
  "name": "John Doe",
  "picture": "https://lh3.googleusercontent.com/...",
  "role": "super_admin",                     // super_admin | business_admin | staff | customer
  "business_access": [                       // Empty array for super_admin (all access)
    {
      "business_id": "rishabh_garments",
      "role": "business_admin",              // business_admin | staff
      "assigned_at": "2024-01-15T10:30:00Z"
    }
  ],
  "status": "active",                        // active | suspended | inactive
  "created_at": "2024-01-10T08:00:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "last_login": "2024-01-20T14:25:00Z"
}

// Indexes
db.users.createIndex({ "user_id": 1 }, { unique: true })
db.users.createIndex({ "email": 1 }, { unique: true })
db.users.createIndex({ "role": 1 })
db.users.createIndex({ "business_access.business_id": 1 })
```

**Key Points**:
- `user_id`: Custom UUID field (not MongoDB's _id)
- `role`: Primary role in system hierarchy
- `business_access`: Array of business-specific roles
- Super Admin has empty `business_access` (implicitly all access)

---

### 8.2 User Sessions Collection

**Purpose**: Manage authentication sessions

```javascript
{
  "session_id": "session_xyz789abc123",
  "user_id": "user_abc123def456",           // References users.user_id
  "session_token": "emergent_session_token_xxx",
  "expires_at": "2024-01-27T10:30:00Z",    // 7 days from creation
  "created_at": "2024-01-20T10:30:00Z",
  "ip_address": "192.168.1.1",
  "user_agent": "Mozilla/5.0..."
}

// Indexes
db.user_sessions.createIndex({ "session_token": 1 }, { unique: true })
db.user_sessions.createIndex({ "user_id": 1 })
db.user_sessions.createIndex({ "expires_at": 1 }, { expireAfterSeconds: 0 })  // TTL index
```

---

### 8.3 Businesses Collection

**Purpose**: Store business configurations

```javascript
{
  "business_id": "rishabh_garments",        // Unique identifier (slug)
  "business_name": "Rishabh Garments",
  "business_type": "kids_wear",             // kids_wear | jewellery | saree | bakery
  "description": "Premium kids wear collection",
  "logo_url": "https://...",
  "contact": {
    "email": "contact@rishabhgarments.com",
    "phone": "+91-9876543210",
    "address": {
      "street": "123 Main Street",
      "city": "Mumbai",
      "state": "Maharashtra",
      "pincode": "400001",
      "country": "India"
    }
  },
  "settings": {
    "currency": "INR",
    "timezone": "Asia/Kolkata",
    "inventory_alerts": {
      "low_stock_threshold": 10,
      "enable_email_alerts": true
    }
  },
  "status": "active",                       // active | inactive
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}

// Indexes
db.businesses.createIndex({ "business_id": 1 }, { unique: true })
db.businesses.createIndex({ "status": 1 })
```

**Initial Businesses**:
1. `rishabh_garments` - Rishabh Garments
2. `jain_jewellers` - Jain Jewellers
3. `jain_sarees` - Jain Sarees
4. `whisked_words` - Whisked Words

---

### 8.4 Categories Collection

**Purpose**: Product categorization (business-specific)

```javascript
{
  "category_id": "cat_abc123",
  "business_id": "rishabh_garments",
  "category_name": "Boys T-Shirts",
  "parent_category_id": null,               // For hierarchical categories
  "description": "Comfortable cotton t-shirts for boys",
  "display_order": 1,
  "status": "active",
  "created_at": "2024-01-10T08:00:00Z"
}

// Indexes
db.categories.createIndex({ "category_id": 1 }, { unique: true })
db.categories.createIndex({ "business_id": 1 })
db.categories.createIndex({ "business_id": 1, "status": 1 })
```

---

### 8.5 Products Collection

**Purpose**: Product catalog with flexible attributes

```javascript
// Example: Kids Garment Product
{
  "product_id": "prod_abc123",
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
  
  // Business-specific attributes (flexible)
  "attributes": {
    "age_group": "5-7 years",
    "sizes": ["S", "M", "L"],
    "colors": ["Red", "Blue", "Green"],
    "material": "100% Cotton",
    "brand": "RG Kids"
  },
  
  "variants": [                             // Size/Color variants
    {
      "variant_id": "var_001",
      "sku": "RG-TS-001-RED-M",
      "size": "M",
      "color": "Red",
      "additional_price": 0,
      "inventory_count": 50
    }
  ],
  
  "status": "active",                       // active | inactive | out_of_stock
  "created_at": "2024-01-10T08:00:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}

// Example: Jewellery Product
{
  "product_id": "prod_xyz789",
  "business_id": "jain_jewellers",
  "category_id": "cat_xyz123",
  "product_name": "Gold Necklace",
  "description": "22K gold necklace with intricate design",
  "base_price": 85000.00,
  "currency": "INR",
  "images": [...],
  
  "attributes": {
    "metal_type": "Gold",
    "purity": "22K",
    "weight": "25.5g",
    "stone_type": "Ruby",
    "making_charges": 5000.00,
    "hallmark": true
  },
  
  "variants": [],                           // Jewellery usually no variants
  
  "status": "active",
  "created_at": "2024-01-10T08:00:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}

// Example: Bakery Product
{
  "product_id": "prod_bakery123",
  "business_id": "whisked_words",
  "category_id": "cat_bakery001",
  "product_name": "Chocolate Truffle Cake",
  "description": "Rich chocolate cake with truffle filling",
  "base_price": 850.00,
  "currency": "INR",
  "images": [...],
  
  "attributes": {
    "weight": "500g",
    "serves": "4-6 people",
    "ingredients": ["Flour", "Cocoa", "Sugar", "Butter", "Eggs"],
    "allergens": ["Gluten", "Dairy", "Eggs"],
    "shelf_life": "2 days",
    "storage": "Refrigerated",
    "customizable": true
  },
  
  "variants": [
    {
      "variant_id": "var_001",
      "sku": "WW-CAKE-001-500G",
      "weight": "500g",
      "additional_price": 0
    },
    {
      "variant_id": "var_002",
      "sku": "WW-CAKE-001-1KG",
      "weight": "1kg",
      "additional_price": 750.00
    }
  ],
  
  "status": "active",
  "created_at": "2024-01-10T08:00:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}

// Indexes
db.products.createIndex({ "product_id": 1 }, { unique: true })
db.products.createIndex({ "business_id": 1 })
db.products.createIndex({ "business_id": 1, "status": 1 })
db.products.createIndex({ "category_id": 1 })
db.products.createIndex({ "business_id": 1, "category_id": 1 })
```

---

### 8.6 Inventory Collection

**Purpose**: Track inventory levels and movements

```javascript
{
  "inventory_id": "inv_abc123",
  "business_id": "rishabh_garments",
  "product_id": "prod_abc123",
  "variant_id": "var_001",                  // If product has variants
  "sku": "RG-TS-001-RED-M",
  
  "quantity": {
    "available": 50,
    "reserved": 5,                          // Items in pending orders
    "total": 55
  },
  
  "location": {
    "warehouse": "Main Warehouse",
    "shelf": "A-12",
    "bin": "3"
  },
  
  "reorder": {
    "reorder_level": 10,                    // Trigger restock alert
    "reorder_quantity": 50,
    "supplier": "ABC Textiles"
  },
  
  "last_restocked": "2024-01-15T10:30:00Z",
  "last_updated": "2024-01-20T14:25:00Z",
  
  "movements": [                            // Recent inventory movements
    {
      "movement_id": "mov_001",
      "type": "purchase",                   // purchase | sale | return | adjustment
      "quantity": 100,
      "reason": "New stock arrival",
      "performed_by": "user_abc123",
      "timestamp": "2024-01-15T10:30:00Z"
    }
  ]
}

// Indexes
db.inventory.createIndex({ "inventory_id": 1 }, { unique: true })
db.inventory.createIndex({ "business_id": 1 })
db.inventory.createIndex({ "product_id": 1 })
db.inventory.createIndex({ "business_id": 1, "sku": 1 })
db.inventory.createIndex({ "quantity.available": 1 })
```

---

### 8.7 Orders Collection

**Purpose**: Order management (future scope - not MVP)

```javascript
{
  "order_id": "ord_abc123",
  "business_id": "rishabh_garments",
  "customer": {
    "name": "Customer Name",
    "email": "customer@example.com",
    "phone": "+91-9876543210"
  },
  "items": [
    {
      "product_id": "prod_abc123",
      "variant_id": "var_001",
      "product_name": "Boys Cotton T-Shirt",
      "quantity": 2,
      "unit_price": 499.00,
      "subtotal": 998.00
    }
  ],
  "pricing": {
    "subtotal": 998.00,
    "tax": 179.64,
    "discount": 0.00,
    "total": 1177.64,
    "currency": "INR"
  },
  "status": "pending",                      // pending | confirmed | shipped | delivered | cancelled
  "created_at": "2024-01-20T10:30:00Z",
  "updated_at": "2024-01-20T14:25:00Z"
}

// Indexes
db.orders.createIndex({ "order_id": 1 }, { unique: true })
db.orders.createIndex({ "business_id": 1 })
db.orders.createIndex({ "status": 1 })
db.orders.createIndex({ "created_at": -1 })
```

---

### 8.8 Inquiries Collection

**Purpose**: Customer inquiries and contact messages

```javascript
{
  "inquiry_id": "inq_abc123",
  "business_id": "jain_jewellers",
  "customer": {
    "name": "Jane Doe",
    "email": "jane@example.com",
    "phone": "+91-9876543210"
  },
  "product_id": "prod_xyz789",              // Optional: inquiry about specific product
  "subject": "Product Inquiry",
  "message": "I'm interested in this gold necklace...",
  "status": "pending",                      // pending | responded | closed
  "assigned_to": "user_abc123",             // Staff member handling inquiry
  "created_at": "2024-01-20T10:30:00Z",
  "responded_at": null
}

// Indexes
db.inquiries.createIndex({ "inquiry_id": 1 }, { unique: true })
db.inquiries.createIndex({ "business_id": 1 })
db.inquiries.createIndex({ "status": 1 })
db.inquiries.createIndex({ "created_at": -1 })
```

---

### 8.9 Audit Logs Collection

**Purpose**: System activity tracking

```javascript
{
  "log_id": "log_abc123",
  "business_id": "rishabh_garments",        // null for system-wide actions
  "user_id": "user_abc123",
  "action": "inventory_update",             // login | product_create | inventory_update | etc.
  "entity_type": "inventory",               // user | product | inventory | order | etc.
  "entity_id": "inv_abc123",
  "details": {
    "field_changed": "quantity.available",
    "old_value": 50,
    "new_value": 45
  },
  "ip_address": "192.168.1.1",
  "timestamp": "2024-01-20T14:25:00Z"
}

// Indexes
db.audit_logs.createIndex({ "log_id": 1 }, { unique: true })
db.audit_logs.createIndex({ "user_id": 1 })
db.audit_logs.createIndex({ "business_id": 1 })
db.audit_logs.createIndex({ "timestamp": -1 })
db.audit_logs.createIndex({ "timestamp": 1 }, { expireAfterSeconds: 15552000 })  // 180 days TTL
```

---

## 9. DATA RELATIONSHIPS

### 9.1 Relationship Diagram

```
┌─────────────┐
│    users    │
└──────┬──────┘
       │
       │ 1:N
       │
┌──────▼──────────┐
│  user_sessions  │
└─────────────────┘

┌─────────────┐
│    users    │◄───────────┐
└──────┬──────┘            │
       │                   │
       │ N:M               │ N:1
       │                   │
┌──────▼──────────┐   ┌────┴────────┐
│   businesses    │   │ audit_logs  │
└──────┬──────────┘   └─────────────┘
       │
       │ 1:N
       │
┌──────▼──────────┐
│   categories    │
└──────┬──────────┘
       │
       │ 1:N
       │
┌──────▼──────────┐
│    products     │
└──────┬──────────┘
       │
       │ 1:N
       │
┌──────▼──────────┐
│   inventory     │
└─────────────────┘

┌─────────────┐
│ businesses  │
└──────┬──────┘
       │
       │ 1:N
       │
┌──────▼──────────┐
│   inquiries     │
└─────────────────┘
```

### 9.2 Key Relationships

1. **Users ↔ Businesses**: Many-to-Many via `business_access` array
2. **Users ↔ Sessions**: One-to-Many (one user, multiple sessions)
3. **Business ↔ Categories**: One-to-Many (hierarchical)
4. **Business ↔ Products**: One-to-Many
5. **Products ↔ Inventory**: One-to-Many (via variants)
6. **Business ↔ Orders**: One-to-Many
7. **Products ↔ Orders**: Many-to-Many via order items

---

**Document Status**: Part 2 Complete
**Next**: Part 3 - API Architecture & Authentication Flow
