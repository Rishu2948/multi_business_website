# Backend API Services Runbook

**Services**: `auth-service`, `order-service`, `payment-service`, `product-service`, `inventory-service`, `user-service`  
**Owner**: Platform SRE  
**Last Updated**: 2024-01-15  
**Severity Tiers**: P1 (auth fully down / payments failing), P2 (elevated 401/403 or circuit-breaker trips), P3 (degraded latency only)

---

## Table of Contents

1. [Service Overview](#service-overview)
2. [Health Check Commands](#health-check-commands)
3. [Triage: Auth Failure Errors](#triage-auth-failure-errors)
4. [Triage: Circuit Breaker Patterns](#triage-circuit-breaker-patterns)
5. [Escalation Path](#escalation-path)
6. [Rollback Procedure](#rollback-procedure)
7. [Post-Incident Checklist](#post-incident-checklist)

---

## Service Overview

The multi-business-website backend is a FastAPI application (`backend/server.py`) serving a React frontend. It exposes a `/api` router with the following sub-services:

| Sub-service | Router file | Key routes | Dependencies |
|---|---|---|---|
| `auth-service` | `server.py` | `POST /api/auth/google`, `GET /api/auth/me`, `POST /api/auth/logout` | MongoDB (`user_sessions`, `users`), Google OAuth2 API |
| `user-service` | `server.py` | `GET /api/users`, `POST /api/users/{id}/role` | MongoDB (`users`) |
| `business-service` | `server.py` | `GET /api/businesses`, `GET /api/businesses/public` | MongoDB (`businesses`) |
| `product-service` | `server.py` | `GET /api/products`, `POST /api/products`, `GET /api/products/trending/{business_id}` | MongoDB (`products`, `reviews`, `orders`) |
| `inventory-service` | `server.py` | `GET /api/inventory`, `PUT /api/inventory/{id}` | MongoDB (`inventory`) |
| `order-service` | `order_routes.py` | `POST /api/orders/create`, `GET /api/orders/my-orders` | MongoDB (`orders`, `inventory`, `carts`) |
| `payment-service` | `payment_routes.py` | `POST /api/payments/create-checkout-session` | MongoDB (`payment_transactions`), Stripe/Razorpay API |
| `ecommerce-service` | `ecommerce_routes.py` | `POST /api/ecommerce/cart/add`, `GET /api/ecommerce/cart` | MongoDB (`carts`, `products`) |
| `order-management` | `order_management_routes.py` | Order status updates, notifications, SSE | MongoDB, `email_service` |
| `sse-service` | `sse_routes.py` | `GET /api/sse/notifications` | MongoDB, in-process SSE stream |

**MongoDB collections**: `users`, `user_sessions`, `businesses`, `products`, `categories`, `orders`, `inventory`, `carts`, `reviews`, `product_views`, `payment_transactions`, `notifications`, `delivery_assignments`

**Error categories to watch** (per Silver layer categorisation):
- `auth_failure` — 401/403 from Google OAuth, expired sessions, missing tokens
- `circuit_breaker` — cascading failures from MongoDB or external APIs tripping internal error handling
- `internal_error` — 500s from unhandled FastAPI exceptions
- `connection_refused` — MongoDB host unreachable
- `timeout` — MongoDB query timeout, Google OAuth API slow

---

## Health Check Commands

Ask the SRE Copilot Agent first:
```
"What is the health of auth-service?"
"Show me auth_failure patterns for backend-api in the last hour"
"Are there circuit-breaker events in the last 6 hours?"
```

### AWS / ECS Health Check
```bash
# FastAPI health endpoint
curl -s https://api.example.com/api/health
# Expected: {"status": "ok"}

# ECS task health
aws ecs describe-tasks \
  --cluster multi-business-cluster \
  --tasks $(aws ecs list-tasks --cluster multi-business-cluster --query 'taskArns[*]' --output text) \
  --query 'tasks[*].{Status:lastStatus,Health:healthStatus,Task:taskArn}'

# Docker container health (local)
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### CloudWatch Logs
```bash
# Auth failure events in last 30 minutes
aws logs filter-log-events \
  --log-group-name /ecs/multi-business-backend \
  --start-time $(date -d '30 minutes ago' +%s000) \
  --filter-pattern '"401" OR "403" OR "Unauthorized" OR "Invalid session"'

# 500 internal errors
aws logs filter-log-events \
  --log-group-name /ecs/multi-business-backend \
  --start-time $(date -d '30 minutes ago' +%s000) \
  --filter-pattern '"500" OR "Internal Server Error" OR "Exception"'

# MongoDB connection errors
aws logs filter-log-events \
  --log-group-name /ecs/multi-business-backend \
  --start-time $(date -d '30 minutes ago' +%s000) \
  --filter-pattern '"ServerSelectionTimeoutError" OR "connection refused" OR "MongoNetworkError"'
```

### MongoDB Atlas Health
```bash
# Check MongoDB Atlas cluster status via Atlas CLI
atlas clusters describe multi-business-cluster --projectId <PROJECT_ID>

# Or connect directly to verify responsiveness
mongosh "$MONGO_URL" --eval "db.adminCommand({ping: 1})"

# Check current ops / slow queries
mongosh "$MONGO_URL" --eval "db.currentOp({'secs_running': {\$gt: 5}})"

# Check connection pool saturation
mongosh "$MONGO_URL" --eval "db.serverStatus().connections"
```

---

## Triage: Auth Failure Errors

**Silver error_category**: `auth_failure`  
**Typical log patterns**: `Invalid Google token`, `Invalid session`, `Session expired`, `401`, `403`, `Access forbidden`

The auth flow involves three steps where failures can occur:
1. **Google OAuth token verification** — `POST /api/auth/google` calls `id_token.verify_oauth2_token`
2. **Session cookie lookup** — `get_current_user` middleware reads `user_sessions` from MongoDB
3. **RBAC role check** — `require_role` decorator enforces role-based access

### Step 1 — Identify which auth layer is failing

```bash
# Isolate Google OAuth errors
aws logs filter-log-events \
  --log-group-name /ecs/multi-business-backend \
  --start-time $(date -d '1 hour ago' +%s000) \
  --filter-pattern '"Invalid Google token" OR "google" OR "ValueError"'

# Isolate session expiry / not found
aws logs filter-log-events \
  --log-group-name /ecs/multi-business-backend \
  --start-time $(date -d '1 hour ago' +%s000) \
  --filter-pattern '"Invalid session" OR "Session expired" OR "User not found"'

# Isolate RBAC failures
aws logs filter-log-events \
  --log-group-name /ecs/multi-business-backend \
  --start-time $(date -d '1 hour ago' +%s000) \
  --filter-pattern '"Access forbidden" OR "403"'
```

### Step 2A — Google OAuth API errors

**Symptoms**: All logins failing simultaneously; log shows `ValueError: Token has wrong audience` or `TransportError`.

```bash
# Check Google API status
curl -s https://oauth2.googleapis.com/.well-known/openid-configuration | python3 -m json.tool

# Verify GOOGLE_CLIENT_ID env var is set correctly on the container
aws ecs describe-task-definition \
  --task-definition multi-business-backend \
  --query 'taskDefinition.containerDefinitions[0].environment[?name==`GOOGLE_CLIENT_ID`]'

# If GOOGLE_CLIENT_ID is wrong or missing:
# 1. Update the ECS task definition env var
# 2. Force a new deployment (see rollback procedure)
```

**Common root causes**:

| Symptom | Likely Cause | Fix |
|---|---|---|
| `Token has wrong audience` | `GOOGLE_CLIENT_ID` mismatch | Update env var in ECS task definition |
| `Token used too early` | Server clock skew > 5 min | Re-sync NTP: `chronyc makestep` on the EC2 host |
| `TransportError` | Google API unreachable | Check outbound internet from VPC; verify NAT gateway |
| All users getting 401 | JWT signature changed (Google rotates keys periodically) | Restart container to force key refresh |

### Step 2B — Session / MongoDB auth failures

**Symptoms**: Users logged in previously now getting 401; database connection working but session lookups failing.

```bash
# Check if sessions exist in MongoDB
mongosh "$MONGO_URL" --eval "
  db.user_sessions.find({}, {session_token: 0}).limit(5).pretty()
"

# Check for expired sessions clogging the collection
mongosh "$MONGO_URL" --eval "
  db.user_sessions.countDocuments({expires_at: {\$lt: new Date()}})
"

# Purge expired sessions (safe to run)
mongosh "$MONGO_URL" --eval "
  db.user_sessions.deleteMany({expires_at: {\$lt: new Date()}})
"

# Verify TTL index exists on user_sessions (should auto-expire sessions)
mongosh "$MONGO_URL" --eval "
  db.user_sessions.getIndexes()
"
```

If the TTL index is missing, create it:
```bash
mongosh "$MONGO_URL" --eval "
  db.user_sessions.createIndex({expires_at: 1}, {expireAfterSeconds: 0})
"
```

### Step 2C — RBAC / role failures

**Symptoms**: Specific users (non-super_admin) getting 403 on routes they should access.

```bash
# Check a user's current role and business_access
mongosh "$MONGO_URL" --eval "
  db.users.findOne({email: 'user@example.com'}, {role: 1, business_access: 1})
"

# If role is wrong, fix it:
mongosh "$MONGO_URL" --eval "
  db.users.updateOne(
    {email: 'user@example.com'},
    {\$set: {role: 'business_admin', updated_at: new Date()}}
  )
"
```

**Allowed roles** (`server.py`): `super_admin`, `business_admin`, `staff`, `delivery_agent`, `customer`

### Step 3 — Immediate Mitigation for Auth Failures

| Root Cause | Immediate Action |
|---|---|
| Wrong `GOOGLE_CLIENT_ID` | Update ECS task definition env var and force redeploy |
| Google OAuth API down | Display maintenance page; check https://status.cloud.google.com |
| MongoDB down | See [Triage: Circuit Breaker Patterns](#triage-circuit-breaker-patterns) |
| All sessions invalid (e.g., after secret rotation) | Notify users to re-login; sessions are stateless — no forced logout needed |
| CORS blocking auth flow | Check `CORS_ORIGINS` env var; ensure frontend origin is listed |

---

## Triage: Circuit Breaker Patterns

**Silver error_category**: `circuit_breaker`  
**Typical log patterns**: `ServerSelectionTimeoutError`, `motor`, `asyncio`, cascading `500` responses

The FastAPI backend uses `motor` (async MongoDB driver) with `serverSelectionTimeoutMS=5000`. When MongoDB is unreachable, requests cascade to 500 errors across all endpoints simultaneously — resembling a circuit-breaker trip.

### Step 1 — Confirm MongoDB is the root cause

```bash
# Check if all endpoints are failing (not just one route)
for endpoint in /api/health /api/businesses/public; do
  echo -n "$endpoint: "
  curl -s -o /dev/null -w "%{http_code}" https://api.example.com$endpoint
  echo
done
# If /api/health returns 200 but /api/businesses/public returns 500, MongoDB is down

# Test MongoDB connectivity directly
mongosh "$MONGO_URL" --eval "db.adminCommand({ping: 1})" --quiet
```

### Step 2 — Diagnose MongoDB failure type

**Atlas connection string** is stored in `backend/.env` as `MONGO_URL` (or AWS Secrets Manager `sre/cloudwatch-credentials` equivalent).

```bash
# A. Atlas cluster status
curl -u "$ATLAS_PUBLIC_KEY:$ATLAS_PRIVATE_KEY" \
  "https://cloud.mongodb.com/api/atlas/v1.0/groups/$ATLAS_PROJECT_ID/clusters/multi-business-cluster" \
  | python3 -m json.tool | grep -E '"stateName"|"mongoURIUpdated"'

# B. Check for Atlas maintenance window or ongoing incident
# https://status.mongodb.com

# C. Check if connection string IP whitelist is blocking the ECS task IP
# Get current ECS task IP
TASK_IP=$(aws ecs describe-tasks \
  --cluster multi-business-cluster \
  --tasks $(aws ecs list-tasks --cluster multi-business-cluster --query 'taskArns[0]' --output text) \
  --query 'tasks[0].containers[0].networkInterfaces[0].privateIpv4Address' --output text)
echo "ECS Task IP: $TASK_IP"
# Compare with Atlas IP Access List in Atlas UI → Network Access
```

### Step 3 — Common circuit-breaker scenarios

#### Scenario A: MongoDB Atlas paused (free tier auto-pause)
Atlas M0 free-tier clusters auto-pause after 60 days of inactivity.

```bash
# Check if paused
curl -u "$ATLAS_PUBLIC_KEY:$ATLAS_PRIVATE_KEY" \
  "https://cloud.mongodb.com/api/atlas/v1.0/groups/$ATLAS_PROJECT_ID/clusters/multi-business-cluster" \
  | python3 -m json.tool | grep '"paused"'

# Resume the cluster
curl -u "$ATLAS_PUBLIC_KEY:$ATLAS_PRIVATE_KEY" \
  -X PATCH \
  "https://cloud.mongodb.com/api/atlas/v1.0/groups/$ATLAS_PROJECT_ID/clusters/multi-business-cluster" \
  -H "Content-Type: application/json" \
  -d '{"paused": false}'
# Wait 2-3 minutes for cluster to resume; monitor Atlas UI
```

#### Scenario B: Connection pool exhausted
Occurs under high concurrent load; `motor` hits `maxPoolSize` (default 100).

```bash
# Check current connections
mongosh "$MONGO_URL" --eval "
  let s = db.serverStatus().connections;
  print('current:', s.current, 'available:', s.available, 'totalCreated:', s.totalCreated)
"

# Immediate relief: restart the FastAPI container to flush connection pool
aws ecs update-service \
  --cluster multi-business-cluster \
  --service multi-business-backend \
  --force-new-deployment

# Long-term: add maxPoolSize to MONGO_URL connection string
# e.g.: mongodb+srv://.../?maxPoolSize=50
```

#### Scenario C: `serverSelectionTimeoutMS` cascading (slow but not down)
MongoDB responds slowly (replica set election in progress); all requests timeout after 5s.

```bash
# Check for slow operations
mongosh "$MONGO_URL" --eval "
  db.currentOp({
    'active': true,
    'secs_running': {\$gte: 3},
    'ns': {\$regex: '^multi_business'}
  })
"

# Kill a long-running operation
mongosh "$MONGO_URL" --eval "db.killOp(<opid>)"

# Check if a replica set election is in progress
mongosh "$MONGO_URL" --eval "rs.status().members.map(m => ({name: m.name, state: m.stateStr}))"
```

#### Scenario D: ECS task lost network path to Atlas
Security group or NAT gateway change cut off Atlas connectivity.

```bash
# Test from within the VPC using an ECS exec
aws ecs execute-command \
  --cluster multi-business-cluster \
  --task $(aws ecs list-tasks --cluster multi-business-cluster --query 'taskArns[0]' --output text) \
  --container backend \
  --interactive \
  --command "nc -zv <atlas-cluster-hostname> 27017"

# If blocked: check security group outbound rules allow TCP 27017/27016 to 0.0.0.0/0
# Also verify NAT gateway is healthy if tasks run in private subnets
aws ec2 describe-nat-gateways --query 'NatGateways[?State==`available`]'
```

### Step 4 — Cascading failures involving external APIs

**Payment service** (`payment_routes.py`) calls Stripe/Razorpay. If those APIs are down, orders that attempt payment will 500 with `501 Not Implemented` (integration stub) or `ConnectionError`.

```bash
# Check Stripe status
curl -s https://status.stripe.com/api/v2/status.json | python3 -m json.tool | grep '"description"'

# Check Razorpay status
curl -s https://status.razorpay.com/api/v2/status.json | python3 -m json.tool

# Temporarily disable payment routes by setting env var (if supported)
# or respond to users that payment is unavailable and redirect to COD
```

### Step 5 — Immediate Mitigation for Circuit Breaker

| Root Cause | Immediate Action |
|---|---|
| Atlas cluster paused | Resume via Atlas API (see Scenario A) |
| Connection pool exhausted | `aws ecs update-service --force-new-deployment` |
| Atlas IP whitelist blocking ECS | Add ECS task IP to Atlas Network Access List |
| Slow MongoDB ops | `db.killOp(<opid>)` on the offending operation |
| Stripe/Razorpay down | Log incident; direct users to COD; monitor status pages |
| ECS NAT gateway down | Restore NAT gateway; check route tables |

---

## Escalation Path

```
Level 1 (On-Call SRE, 0–15 min)
  └── Follow this runbook
  └── Check SRE Copilot: "Show auth_failure or circuit_breaker patterns"
  └── If not resolved in 15 min → escalate to Level 2

Level 2 (Senior SRE / Platform Lead, 15–45 min)
  └── Review recent deployments and env var changes
  └── Check MongoDB Atlas status: https://status.mongodb.com
  └── Check Google Cloud status: https://status.cloud.google.com
  └── If MongoDB involvement confirmed → engage Database Admin

Level 3 (Engineering Manager + Service Owner, 45+ min or P1)
  └── If auth is fully down (all users unable to login) → P1
  └── If payments failing → engage Payment Team Lead
  └── Consider rollback (see below)
  └── Engage MongoDB Atlas support if Atlas incident

Contacts (replace with actual):
  On-Call SRE:        PagerDuty rotation "sre-oncall"
  Platform Lead:      @platform-lead
  Database Admin:     @db-admin
  Payment Team Lead:  @payment-lead
  MongoDB Support:    https://support.mongodb.com
```

---

## Rollback Procedure

### Step 1 — Identify the last known-good state
```bash
# ECS service deployment history
aws ecs describe-services \
  --cluster multi-business-cluster \
  --services multi-business-backend \
  --query 'services[0].deployments'

# Git log for recent changes
git -C /path/to/multi_business_website log --oneline -20 -- backend/
```

### Step 2 — Roll back ECS deployment
```bash
# Get the previous task definition revision
PREV_TASK_DEF=$(aws ecs describe-services \
  --cluster multi-business-cluster \
  --services multi-business-backend \
  --query 'services[0].deployments[-1].taskDefinition' --output text)

echo "Rolling back to: $PREV_TASK_DEF"

# Update service to use previous task definition
aws ecs update-service \
  --cluster multi-business-cluster \
  --service multi-business-backend \
  --task-definition "$PREV_TASK_DEF"

# Monitor rollout
aws ecs wait services-stable \
  --cluster multi-business-cluster \
  --services multi-business-backend
```

### Step 3 — Roll back environment variable changes
```bash
# If GOOGLE_CLIENT_ID or MONGO_URL was changed in the latest deployment:
# 1. Describe the previous task definition to get old env vars
aws ecs describe-task-definition \
  --task-definition "$PREV_TASK_DEF" \
  --query 'taskDefinition.containerDefinitions[0].environment'

# 2. Register a new task definition with corrected env vars
# 3. Update the service to the new task definition
```

### Step 4 — Roll back MongoDB schema / data changes
```bash
# If a migration script introduced bad data:
# Restore from Atlas backup (point-in-time restore)
# Atlas UI → Clusters → ... → Backup → Restore

# For immediate relief, if a bad index was added:
mongosh "$MONGO_URL" --eval "
  db.users.getIndexes()
  // then drop the problematic index:
  // db.users.dropIndex('index_name')
"
```

### Step 5 — Verify recovery
```bash
# Health check
curl -s https://api.example.com/api/health

# Auth smoke test
curl -X POST https://api.example.com/api/auth/google \
  -H "Content-Type: application/json" \
  -d '{"token": "<valid-test-google-token>"}' \
  -w "\nHTTP: %{http_code}\n"

# Public products endpoint (no auth needed)
curl -s "https://api.example.com/api/businesses/public" | python3 -m json.tool | head -20

# Ask the SRE Copilot:
"Is auth-service healthy? Are there any active circuit_breaker patterns?"
```

---

## Post-Incident Checklist

- [ ] Error rate confirmed returning to baseline across all backend routes
- [ ] MongoDB Atlas cluster healthy; connection counts normal
- [ ] Google OAuth integration responding correctly
- [ ] Authentication flow tested end-to-end (login → session → logout)
- [ ] Payment routes smoke-tested (even if partial)
- [ ] SSE notifications endpoint verified
- [ ] CloudWatch alarms cleared
- [ ] Incident timeline documented (use `postmortem-template.md`)
- [ ] MongoDB TTL index on `user_sessions` confirmed present
- [ ] Atlas IP whitelist reviewed and tightened if needed
- [ ] PagerDuty incident resolved
- [ ] Action items filed as tickets
- [ ] Runbook updated if new failure modes discovered

---

## Quick Reference: Backend API Routes

| Route | Method | Auth | Common Failure Mode |
|---|---|---|---|
| `/api/health` | GET | None | Always 200; if 500, ECS task crashed |
| `/api/auth/google` | POST | None | Google API down; wrong `GOOGLE_CLIENT_ID` |
| `/api/auth/me` | GET | Cookie/Bearer | MongoDB down; expired session |
| `/api/businesses/public` | GET | None | MongoDB down |
| `/api/products` | GET | None | MongoDB slow; missing index |
| `/api/products/trending/{id}` | GET | None | Aggregation pipeline timeout on large datasets |
| `/api/orders/create` | POST | Optional | Inventory lock contention; MongoDB timeout |
| `/api/payments/create-checkout-session` | POST | None | Stripe/Razorpay API down |
| `/api/ecommerce/cart/add` | POST | Optional | MongoDB write conflict |
| `/api/sse/notifications` | GET | Cookie | Long-lived connection limit; ECS ALB idle timeout |

---

*This runbook is stored in the Bedrock Knowledge Base (S3) and used as RAG context by the SRE Copilot Agent. Keep it current after every incident.*
