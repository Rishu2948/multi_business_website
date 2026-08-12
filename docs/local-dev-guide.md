# Local Development Guide

## Prerequisites

- Python 3.11+
- Node.js 18+ (with yarn or npm)
- MongoDB Atlas connection (already configured in `.env`)

---

## 1. Backend Setup

```bash
cd backend

# Create a virtual environment (first time only)
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Start the backend server
uvicorn server:app --reload --port 8000
```

Backend runs at: **http://localhost:8000**  
API docs (Swagger): **http://localhost:8000/docs**

---

## 2. Frontend Setup

```bash
cd frontend

# Install dependencies (first time only)
npm install
# or: yarn install

# Start the dev server
npm start
# or: yarn start
```

Frontend runs at: **http://localhost:3000**

The frontend already points to `http://localhost:8000` via `REACT_APP_BACKEND_URL` in `frontend/.env`.

---

## 3. Run Database Migrations

Migrations add new fields to products and seed categories, store config, and offers.
Run these **once** after pulling new code or setting up a fresh environment.

```bash
cd backend
source venv/bin/activate

# Run all migrations in order (idempotent — safe to re-run)
python3 run_migrations.py

# Or run a specific migration:
python3 run_migrations.py --only 001   # add product fields
python3 run_migrations.py --only 002   # seed categories from products
python3 run_migrations.py --only 003   # seed store config, offers, announcements
```

---

## 4. Seed Product Data (100 bakery products)

```bash
cd backend
source venv/bin/activate

# Preview without writing (dry run)
python3 expand_bakery_seed.py --dry-run

# Seed 100 products + inventory to MongoDB Atlas
python3 expand_bakery_seed.py
```

This is safe to run repeatedly — it skips products that already exist.

---

## 5. Full Local Setup (fresh environment)

Run these steps in order:

```bash
# Terminal 1: Backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 run_migrations.py          # migrations first
python3 expand_bakery_seed.py      # seed 100 products
uvicorn server:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm install
npm start
```

Open http://localhost:3000

---

## 6. Admin Dashboard Access

Log in with a Google account that has been assigned an admin role.

| Role | Dashboard URL | Access |
|---|---|---|
| `super_admin` | `/super-admin` | All businesses, all config |
| `business_admin` | `/admin` | Own business only |
| `staff` | `/staff` | Order management |

**Admin navigation** (accessible after login from the dashboard):

| Page | URL | Purpose |
|---|---|---|
| Business Dashboard | `/admin` | Overview + config links |
| Category Manager | `/admin/categories` | Add/rename/reorder categories |
| Product Manager | `/admin/products` | Add/edit products + addons |
| Store Config | `/admin/store-config` | Hours, delivery, order types |
| Offers Manager | `/admin/offers` | Create promo codes + discounts |
| Announcement Manager | `/admin/announcements` | Edit the top banner bar |
| Collection Manager | `/admin/collections` | Gifting, Festive groupings |
| Order Management | `/admin/orders` | View + manage all orders |

**Assigning admin role** — use the Super Admin dashboard to find a user and assign `business_admin` or `super_admin` role:

1. Login with any Google account
2. In the backend shell, run:

```python
# Quick way to promote a user to super_admin via Python
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
load_dotenv()

async def promote(email):
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    r = await db.users.update_one(
        {"email": email},
        {"$set": {"role": "super_admin"}}
    )
    print("Updated:", r.modified_count)
    client.close()

asyncio.run(promote("your-email@gmail.com"))
```

Or use the API directly after login:

```bash
# First login, then promote via the API
curl -X PATCH http://localhost:8000/api/users/<user_id> \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <session_token>" \
  -d '{"role": "super_admin"}'
```

---

## 7. Environment Variables

### Backend (`backend/.env`)
Already configured. Key values:

```env
MONGO_URL=mongodb+srv://...   # Atlas connection
DB_NAME=multi_business
CORS_ORIGINS=http://localhost:3000
GOOGLE_CLIENT_ID=...
```

### Frontend (`frontend/.env`)
```env
REACT_APP_BACKEND_URL=http://localhost:8000
REACT_APP_GOOGLE_CLIENT_ID=...
```

---

## 8. Verify Everything is Working

After starting both servers and running migrations, check these URLs:

| Check | URL | Expected |
|---|---|---|
| Backend health | http://localhost:8000/api/health | `{"status":"ok"}` |
| Backend docs | http://localhost:8000/docs | Swagger UI |
| Categories API | http://localhost:8000/api/categories/whisked_words | List of categories |
| Products API | http://localhost:8000/api/products?business_id=whisked_words&limit=10 | 10 products |
| Store info | http://localhost:8000/api/store/info/whisked_words | Store config |
| Offers | http://localhost:8000/api/offers/whisked_words | Active offers |
| Frontend | http://localhost:3000 | Landing page |
| Catalog | http://localhost:3000/business/whisked_words/catalog | Product catalog |

---

## 9. Common Issues & Fixes

**"Only 8 products showing in catalog"**
- Run `python3 expand_bakery_seed.py` to seed 100 products
- Check categories exist: `GET /api/categories/whisked_words`
- Products must have `status: "active"` — migrations set this

**"Store shows CLOSED"**
- Run `python3 run_migrations.py --only 003` to seed store config
- Edit hours via `/admin/store-config` in the UI

**"Filters show 0 products"**
- Filters use fields like `is_veg`, `is_bestseller` added by migration 001
- Run `python3 run_migrations.py --only 001` to add these fields

**"Can't access admin dashboard"**
- Ensure your user has `role: "business_admin"` or `role: "super_admin"`
- Use the promote script above
- Admin links appear in BakeryNavbar → hamburger menu for admin roles

**"Announcement bar not showing"**  
- Run `python3 run_migrations.py --only 003` to seed the sample announcement

**CORS errors in browser**
- Ensure backend `CORS_ORIGINS=http://localhost:3000` in `backend/.env`
- Restart backend after `.env` changes
