# UI Upgrade Plan — Theobroma-Inspired + Config-Controlled Admin

**Inspiration:** Theobroma ordering UI  
**Stack:** React, Tailwind CSS, Framer Motion, SWR  
**Design System:** `#FAF8F5` bg, `#4A3B32` primary, `#D4A373` accent, Playfair Display + Manrope  

**Core Principle:** Every piece of business content — categories, products, offers, store hours, announcements — is editable by `super_admin` or `business_admin` through the admin dashboard, with changes instantly reflected on the customer-facing site. No hardcoded lists, no code deploys needed to add a "Namkeen" category.

---

## Mobile-First Rules (Global)

- Touch targets: minimum `44×44px`
- Modals open as bottom sheets on mobile, centered on desktop
- Left sidebar becomes a slide-in drawer on mobile
- Filter bar: horizontal scrollable pill strip on mobile (no wrapping)
- Floating cart bar on mobile (sticky bottom), replaces navbar cart icon
- Font minimum: `text-sm` (14px) on mobile
- Category chips: sticky horizontal scroll strip on mobile (Swiggy/Zomato style)
- Framer Motion: respect `prefers-reduced-motion`

---

## Part A — Customer-Facing UI Upgrades

### Phase 1 — Navbar Redesign

#### 1A. Announcement Bar

Fetches from `GET /announcements/:businessId`. Dismissable, persisted in `localStorage`.

**Desktop/Mobile:** Full-width strip, bg/text colors from API response.

```jsx
// src/components/common/AnnouncementBar.jsx
// Props: businessId
// Fetches active announcement on mount, renders nothing if none active
// Dismissed state stored in localStorage keyed by announcement_id
```

#### 1B. Main Navbar — Marketing Site (`BakeryNavbar`)

**Desktop:**
```
[Logo]   About Us   Products   Speciality Cakes   Find Us   Contact Us
                                          [🔍 Search]  [ORDER ONLINE →]
```

**Mobile:**
```
[Logo]                          [🔍] [☰]
  ↓ Drawer: nav links + ORDER ONLINE CTA
```

Nav links (except ORDER ONLINE) can be controlled by `store_config.show_in_nav` collections field. No hardcoded link list.

#### 1C. Order Navbar (`OrderNavbar`)

Used on `/business/:businessId/catalog`. Data from `GET /store/info/:businessId` and `GET /offers/:businessId`.

**Desktop:**
```
[Logo]  Home  Order Now  Products  [Collections from API]  Contact  Login
─────────────────────────────────────────────────────────────────────────
[Store Name] ⓘ [OPEN/CLOSED]  📍 [location_label]  ORDER TYPE: [type ▾]  [N OFFERS ▸]
```

**Mobile:**
```
[Logo]                          [🛒 N]
[📍 location]  [Delivery ▾]   [OFFERS]
```

All data (store name, location, open status, order types, offer count) fetched from API — **no hardcoded strings**.

---

### Phase 2 — Product Catalog Overhaul (`ProductCatalog.jsx`)

#### 2A. Category-Driven Layout

Categories fetched from `GET /categories/:businessId`. The sidebar and chip strip are **rendered from API data** — adding "Namkeen" in the admin immediately shows it here.

**Desktop (≥1024px):**
```
┌─────────────────────────┬──────────────────────────────────────────┐
│  SIDEBAR (w-64, sticky) │  CONTENT (flex-1, scrollable)            │
│                         │                                           │
│  Menu                   │  FEATURED ITEMS  (from API)    4 items   │
│  ─────────              │  [product cards carousel]                 │
│  ▸ Featured Items  6    │                                           │
│  ▾ Value Combos   21    │  NAMKEEN                       8 items   │
│    · Snack        10    │  [product cards]                          │
│  ▸ Cakes          25    │                                           │
│  ▸ Pastries       14    │  CAKES                         25 items  │
│  ▸ Namkeen        8     │  ...                                      │
└─────────────────────────┴──────────────────────────────────────────┘
```

**Mobile (<1024px):** Horizontal scrollable chip strip (sticky below navbar), products in single-column list.

**Scroll spy:** `IntersectionObserver` auto-highlights active category in sidebar/chips as user scrolls.

#### 2B. Components

**`src/components/catalog/CategorySidebar.jsx`**
- Fetches categories from context/prop (passed from `ProductCatalog`)
- Expandable sub-categories (accordion)
- Active state: `border-l-2 border-[#4A3B32]` + bold
- Item count badge from `category.product_count`

**`src/components/catalog/CategoryChipStrip.jsx`**
- Same data source as sidebar
- `overflow-x-auto scrollbar-hide`
- Active chip: `bg-[#4A3B32] text-white`

**`src/components/catalog/CategorySection.jsx`**
- Renders a titled section with an anchor `id={category.category_id}`
- Shows `category.display_name` + item count
- Uses `OrderProductCard` for each product

#### 2C. Product Filter Pills Bar

**`src/components/catalog/ProductFiltersBar.jsx`**

Filters are applied client-side after fetch. The filter pills are hardcoded UX controls but filter against API-provided product fields:

```
[🔍 Search]  [● Veg]  [○ Non-Veg]  [★ Bestseller]  [% On Offer]  [✨ What's New]  [⭐ Rated 4+]
```

| Pill | Field |
|---|---|
| Veg | `product.is_veg === true` |
| Non-Veg | `product.is_veg === false` |
| Bestseller | `product.is_bestseller === true` |
| On Offer | `product.has_active_offer === true` |
| What's New | `product.created_at` within last 30 days |
| Rated 4+ | `product.avg_rating >= 4` |

---

### Phase 3 — Product Cards Upgrade

#### 3A. Veg/Non-Veg Badge
`src/components/catalog/VegNonVegBadge.jsx` — green/red square indicator, `is_veg` from API.

#### 3B. Quality Badges
`src/components/catalog/ProductBadge.jsx` — "Best Seller", "Highly Ordered", "On Offer" from API fields.

#### 3C. Order Product Card (Horizontal layout)
`src/components/catalog/OrderProductCard.jsx`

**Desktop & Mobile:**
```
[●] [Badge] Product Name
    Description (2 lines)
    ₹130              [Img 80×80]
                      [ADD +]
```

---

### Phase 4 — Product Item Modal

`src/components/catalog/ProductItemModal.jsx`

Add-on groups fetched from `product.addons` (API-driven). When admin adds a new addon group (e.g., "Dips & Sauces"), it automatically appears in this modal — no frontend code change.

**Mobile:** Bottom sheet (slides up, `max-h-[90vh]`, drag handle)  
**Desktop:** Centered modal (`max-w-lg`)

```
[Product image]
[Name + Veg badge]   [Share]
[Description] [Allergens from API]
₹130

── GROUP NAME (Optional, "choose up to N") ──
☐ Item 1  +₹X
☐ Item 2  +₹X

─────────────────────────────────────────────
₹130.00              [Add to Cart]
```

---

### Phase 5 — Floating Cart Bar (Mobile)

`src/components/common/FloatingCartBar.jsx`

```
🛒  2 items in cart          ₹260  [View Cart →]
```

- `lg:hidden`, fixed bottom
- `pb-[env(safe-area-inset-bottom)]` for iPhone notch
- Visible only when cart has ≥1 item

---

### Phase 6 — Offers Panel

`src/components/catalog/OffersPanel.jsx`

Data from `GET /offers/:businessId` — fully API-driven. Admin creates offers in dashboard; they appear here instantly.

**Mobile:** Bottom sheet  
**Desktop:** Dropdown below store bar

```
🏷  N Available Offers
─────────────────────────────
COMBO15   FLAT 15% OFF on all combos
          Use code COMBO15        [Copy]
FIRST200  ₹200 OFF on first order
          Min order ₹499          [Copy]
```

---

### Phase 7 — Collections / Gifting Page

**Route:** `/business/:businessId/collections/:collectionId`  
**File:** `src/pages/CollectionsPage.jsx`

Collection metadata (title, description, banner image) from `GET /collections/:businessId`. Products from `GET /products?collection=:collectionId`.

**Mobile filter:** Bottom sheet triggered by "Filters" button.

---

### Phase 8 — Cart & Checkout Mobile

- Cart: single column on mobile, swipe-to-remove, sticky "Checkout" bar
- Checkout: accordion sections (Delivery → Payment → Review), sticky "Place Order" footer

---

### Phase 9 — BusinessHome Upgrades

Category tiles fetched from `GET /categories/:businessId?is_featured=true` — admin marks categories as featured in the dashboard.

```
[Quick actions: Order Now | Custom Cake | Loyalty | Subscriptions]
[Category tiles: Cakes | Pastries | Namkeen | ...]  ← from API
[Testimonials row]
```

---

## Part B — Admin Dashboard: Config Management UI

This is the new section that makes everything config-controlled. All admin pages live under `/admin/**` and `/super-admin/**`.

### B1 — Category Manager

**Route:** `/admin/categories` (business_admin) / `/super-admin/categories` (super_admin)  
**File:** `src/pages/admin/CategoryManager.jsx`

**Features:**
- List all categories for the selected business in a sortable table
- Drag-and-drop reorder (changes `sort_order`, updates sidebar immediately)
- Inline toggle: `is_active`, `is_featured`
- "Add Category" form:
  - Display name (required) → auto-generates `category_id` slug shown as preview
  - Optional: description, emoji icon, image upload, parent category (sub-category)
  - Sort order (auto-set to last)
- Edit category: full edit form in a side panel or modal
- Delete: soft delete (products remain, category hidden from nav)

**Mobile:**
- Cards instead of table rows
- Tap to expand edit form
- Reorder via up/down arrow buttons (drag-and-drop replaced on mobile)

```
CATEGORY MANAGER                         [+ Add Category]
─────────────────────────────────────────────────────────
☰  Featured Items    Active  Featured   8 products   [Edit]
☰  Cakes             Active           25 products   [Edit]
☰  Namkeen           Active            0 products   [Edit]
☰  Pastries          Active           14 products   [Edit]
   [Inactive: Old Items]                             [Edit]
```

### B2 — Product Manager

**Route:** `/admin/products`  
**File:** `src/pages/admin/ProductManager.jsx`

**Extends the existing `AddProductModal` into a full page.**

**Features:**
- Filterable, searchable product table: by category, active/inactive, is_veg, is_featured
- Bulk actions: toggle active, set category, add collection tag
- "Add Product" → full form:
  - Category dropdown (from `GET /categories/:businessId`) — **not hardcoded**
  - Sub-category dropdown (filtered by parent)
  - Name, description, price, images
  - Veg/Non-veg toggle
  - Is featured, is bestseller (manual override) toggles
  - Allergens multi-select (from configurable list or free-text)
  - Collection tags multi-select (from `GET /collections/:businessId`)
  - Sort order within category
  - **Add-ons section:** Add/edit/delete addon groups and items inline
- Edit product: same form pre-populated
- Quick stock toggle: in-table "In Stock / Out of Stock" toggle

**Add-ons builder UI:**
```
ADD-ONS & COMBOS
────────────────────────────────────
+ Add Addon Group

[Group: COLD BEVERAGES]  Optional  Max: 3  [Edit] [Delete]
  Items:
  • Valencia Orange Juice  +₹170  [✓ Available]  [Edit] [✕]
  • Mango & Pineapple      +₹170  [✓ Available]  [Edit] [✕]
  [+ Add Item]

[Group: HOT BEVERAGES]  Optional  Max: 3  [Edit] [Delete]
  • Hot Chocolate [250ml]  +₹195  [✓ Available]  [Edit] [✕]
  [+ Add Item]
```

### B3 — Collection Manager

**Route:** `/admin/collections`  
**File:** `src/pages/admin/CollectionManager.jsx`

- Create collection: name, description, banner image, illustration, show_in_nav toggle, show_on_homepage toggle
- Collections show in navbar and homepage tiles based on these toggles — no code change needed
- Products are tagged to collections from the Product Manager form

### B4 — Offers Manager

**Route:** `/admin/offers`  
**File:** `src/pages/admin/OffersManager.jsx`

```
OFFERS MANAGER                           [+ Create Offer]
─────────────────────────────────────────────────────────────────────
COMBO15   15% OFF   Active   Category: Value Combos   Expires 31 Dec
FIRST200  ₹200 OFF  Active   All products             74 uses / 500
WINTER10  10% OFF   Expired  All products             ─
```

**Create Offer form:**
- Title, promo code (optional — leave blank for auto-apply)
- Type: Percentage / Flat Amount / Free Delivery / Buy X Get Y
- Discount value + max cap
- Min order amount
- Scope: All Products / Specific Categories / Specific Products / Collections
  - Scope dropdown: multi-select from categories/products/collections (from API)
- Valid from / Valid until date pickers
- Usage limit, per-user limit
- Show in offers panel toggle

### B5 — Store Config Manager

**Route:** `/admin/store-config`  
**File:** `src/pages/admin/StoreConfigManager.jsx`

```
STORE CONFIGURATION
────────────────────────────────────────────────────────

Store Display Name: [Whisked Words          ]
Location Label:     [HSR Layout, Bengaluru  ]

Business Hours:
  Monday     [✓ Open]  Open: [08:00]  Close: [22:00]
  Tuesday    [✓ Open]  Open: [08:00]  Close: [22:00]
  ...
  Sunday     [✓ Open]  Open: [09:00]  Close: [21:00]

Temporarily Closed: [Toggle]
Closed Reason:      [___________________________]

Order Types:  [✓ Delivery]  [✓ Takeaway]  [○ Dine-in]

Delivery Settings:
  Min Order (Delivery):  [₹199 ]
  Delivery Charge:       [₹50  ]
  Free Delivery Above:   [₹499 ] (leave blank to disable)
  Est. Delivery Time:    [30-45 mins]
  Delivery Radius:       [10 km]

Tax Rate: [5%]

[Save Changes]
```

All fields save to `store_config` collection. Changes reflect on the order navbar instantly.

### B6 — Announcement Manager

**Route:** `/admin/announcements`  
**File:** `src/pages/admin/AnnouncementManager.jsx`

- List announcements with active/expired status
- Create: message text, optional link + link text, colors, validity dates
- Live preview of the announcement bar as you type
- Toggle active/inactive

### B7 — Inventory Manager (Extended)

Extends the current `BusinessAdminDashboard` inventory table.

**New capabilities:**
- Set reorder level per product (triggers low stock alert)
- Bulk import/export (CSV)
- Low stock alert feed
- Out-of-stock products highlighted prominently
- "Mark as out of stock" quick action (sets `is_available = false` on product)

### B8 — Super Admin: Multi-Business Control Panel

**Route:** `/super-admin`  
**File extends:** `src/pages/SuperAdminDashboard.jsx`

**New sections:**
- Business selector → loads any business's Category/Product/Store/Offers config in the same admin UI
- Cross-business analytics view
- Create new business button (full onboarding form)
- Impersonate business admin (super_admin can act as any business_admin for support)

---

## Routing Additions

```jsx
// App.js additions

// Admin routes (business_admin + super_admin)
<Route path="/admin/categories" element={<ProtectedRoute allowedRoles={['super_admin','business_admin']}><CategoryManager /></ProtectedRoute>} />
<Route path="/admin/products" element={<ProtectedRoute allowedRoles={['super_admin','business_admin']}><ProductManager /></ProtectedRoute>} />
<Route path="/admin/collections" element={<ProtectedRoute allowedRoles={['super_admin','business_admin']}><CollectionManager /></ProtectedRoute>} />
<Route path="/admin/offers" element={<ProtectedRoute allowedRoles={['super_admin','business_admin']}><OffersManager /></ProtectedRoute>} />
<Route path="/admin/store-config" element={<ProtectedRoute allowedRoles={['super_admin','business_admin']}><StoreConfigManager /></ProtectedRoute>} />
<Route path="/admin/announcements" element={<ProtectedRoute allowedRoles={['super_admin','business_admin']}><AnnouncementManager /></ProtectedRoute>} />

// Customer-facing collection pages
<Route path="/business/:businessId/collections/:collectionId" element={<CollectionsPage />} />
```

---

## Full Component Inventory

### New Customer-Facing Components

| File | Description |
|---|---|
| `components/common/AnnouncementBar.jsx` | API-driven promo strip |
| `components/common/OrderNavbar.jsx` | Order page nav + store info |
| `components/common/FloatingCartBar.jsx` | Mobile sticky cart bar |
| `components/catalog/CategorySidebar.jsx` | Desktop category nav (API-driven) |
| `components/catalog/CategoryChipStrip.jsx` | Mobile chip scroll (API-driven) |
| `components/catalog/CategorySection.jsx` | Product section per category |
| `components/catalog/ProductFiltersBar.jsx` | Filter pills row |
| `components/catalog/OrderProductCard.jsx` | Horizontal product card |
| `components/catalog/ProductItemModal.jsx` | Add-on modal (API-driven addons) |
| `components/catalog/OffersPanel.jsx` | API-driven offers display |
| `components/catalog/VegNonVegBadge.jsx` | Food type indicator |
| `components/catalog/ProductBadge.jsx` | Best Seller etc. badge |
| `pages/CollectionsPage.jsx` | Gifting/collection page |

### New Admin Components

| File | Description |
|---|---|
| `pages/admin/CategoryManager.jsx` | Full category CRUD with drag reorder |
| `pages/admin/ProductManager.jsx` | Full product management + addon builder |
| `pages/admin/CollectionManager.jsx` | Collection CRUD |
| `pages/admin/OffersManager.jsx` | Offers CRUD with scope selector |
| `pages/admin/StoreConfigManager.jsx` | Store hours, delivery, order types |
| `pages/admin/AnnouncementManager.jsx` | Announcement bar editor |
| `components/admin/AddonGroupBuilder.jsx` | Reusable addon builder widget |
| `components/admin/CategoryPicker.jsx` | Reusable dropdown from API categories |
| `components/admin/CollectionTagPicker.jsx` | Multi-select from API collections |

### Modified Files

| File | Changes |
|---|---|
| `components/common/BakeryNavbar.jsx` | Two-level, mobile drawer, API nav items |
| `pages/ProductCatalog.jsx` | Full layout overhaul, categories from API |
| `pages/BusinessHome.jsx` | Featured category tiles from API |
| `pages/CartPage.jsx` | Mobile single-column, add-ons display |
| `pages/CheckoutPage.jsx` | Accordion sections, offer code field |
| `pages/SuperAdminDashboard.jsx` | Add cross-business config links |
| `pages/BusinessAdminDashboard.jsx` | Add links to all new admin sections |
| `App.js` | New routes |

---

## Priority Order

| Priority | Item | Effort | Impact |
|---|---|---|---|
| 🔴 1 | Category Manager admin page | Medium | Unlocks everything config-driven |
| 🔴 2 | Categories API → sidebar/chips in catalog | Large | Core ordering UX |
| 🔴 3 | Product Manager (extend add product modal) | Large | Core inventory control |
| 🟡 4 | Product item modal with API addons | Medium | Core add-on UX |
| 🟡 5 | Store Config Manager | Small | Store hours control |
| 🟡 6 | Offers Manager + OffersPanel | Medium | Marketing control |
| 🟡 7 | Floating cart bar + product cards upgrade | Small | Mobile UX |
| 🟢 8 | Announcement Manager + AnnouncementBar | Small | Marketing control |
| 🟢 9 | Collection Manager + CollectionsPage | Medium | Content feature |
| 🟢 10 | Navbar redesign (two-level) | Medium | Brand polish |
| 🟢 11 | Cart/Checkout mobile improvements | Medium | Checkout UX |

---

## Accessibility

- All interactive elements: `data-testid`
- Icon-only buttons: `aria-label`
- Decorative images: `aria-hidden="true"`
- Focus rings: `focus:ring-2 focus:ring-[#4A3B32]`
- Bottom sheets trap focus when open
- Color contrast: `#2C2420` on `#FAF8F5` — WCAG AA compliant
- Admin forms: proper `<label for>` associations, error messages with `role="alert"`
