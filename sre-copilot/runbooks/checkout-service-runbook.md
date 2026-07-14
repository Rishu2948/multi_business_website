# Checkout Service Runbook

**Service**: `checkout-service`  
**Owner**: Platform SRE  
**Last Updated**: 2024-01-15  
**Severity Tiers**: P1 (checkout fully down), P2 (elevated error rate >5%), P3 (degraded latency only)

---

## Table of Contents

1. [Service Overview](#service-overview)
2. [Health Check Commands](#health-check-commands)
3. [Triage: Connection Refused Errors](#triage-connection-refused-errors)
4. [Triage: Timeout Errors](#triage-timeout-errors)
5. [Escalation Path](#escalation-path)
6. [Rollback Procedure](#rollback-procedure)
7. [Post-Incident Checklist](#post-incident-checklist)

---

## Service Overview

The `checkout-service` handles cart finalisation, payment initiation, and order creation. It depends on:

| Dependency | Protocol | Failure Impact |
|---|---|---|
| `payment-service` | HTTP (synchronous) | Checkout blocked |
| `inventory-service` | HTTP (synchronous) | Item availability check blocked |
| `user-service` | HTTP (synchronous) | Auth token validation |
| `order-db` (RDS PostgreSQL) | JDBC | Order creation blocked |
| `redis-cache` | TCP 6379 | Session/cart state unavailable |

**Error categories to watch** (in priority order per Silver layer categorisation):
- `connection_refused` — downstream service or DB unreachable
- `timeout` — downstream response too slow
- `auth_failure` — JWT/token validation errors (usually upstream in `user-service`)

---

## Health Check Commands

Run these first before any deeper triage. The SRE Copilot Agent can answer these questions too — ask it "Why is checkout-service failing?" in the React Chat UI.

### Quick Agent Query
```
# In the SRE Copilot Chat UI:
"What is the current health of checkout-service?"
"Show me error patterns for checkout-service in the last 6 hours"
```

### AWS CloudWatch Logs
```bash
# Tail live logs for checkout-service
aws logs tail /aws/lambda/checkout-service --follow --format short

# Search for connection refused in last 30 minutes
aws logs filter-log-events \
  --log-group-name /aws/lambda/checkout-service \
  --start-time $(date -d '30 minutes ago' +%s000) \
  --filter-pattern "connection refused" \
  --query 'events[*].message'

# Search for timeout errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/checkout-service \
  --start-time $(date -d '30 minutes ago' +%s000) \
  --filter-pattern '"timed out" OR "timeout"'
```

### Kubernetes (if deployed on EKS)
```bash
# Check pod health
kubectl get pods -n production -l app=checkout-service

# Describe a failing pod
kubectl describe pod <pod-name> -n production

# Recent pod logs
kubectl logs -n production -l app=checkout-service --tail=100 --since=30m

# Check HPA scaling
kubectl get hpa checkout-service -n production

# Check endpoints (is the service reachable?)
kubectl get endpoints checkout-service -n production
```

### Service Metrics
```bash
# CloudWatch metric — 5xx error count last 15 min
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name HTTPCode_Target_5XX_Count \
  --dimensions Name=TargetGroup,Value=<checkout-tg-arn> \
  --start-time $(date -d '15 minutes ago' -u +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 60 --statistics Sum

# RDS connection count
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name DatabaseConnections \
  --dimensions Name=DBInstanceIdentifier,Value=order-db \
  --start-time $(date -d '15 minutes ago' -u +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 60 --statistics Average
```

---

## Triage: Connection Refused Errors

**Silver error_category**: `connection_refused`  
**Typical log pattern**: `ConnectionRefusedException`, `connection refused`, `connection reset by peer`

### Step 1 — Identify the refusing endpoint

```bash
# Find which downstream host is refusing connections
aws logs filter-log-events \
  --log-group-name /aws/lambda/checkout-service \
  --start-time $(date -d '1 hour ago' +%s000) \
  --filter-pattern '"connection refused"' \
  --query 'events[*].message' | grep -oP '(?<=connecting to )[^\s]+'
```

Common culprits and their checks:

#### A. Payment Service Down
```bash
# Check payment-service health
kubectl get pods -n production -l app=payment-service
kubectl logs -n production -l app=payment-service --tail=50 --since=10m

# Manual health probe
kubectl exec -n production deploy/checkout-service -- \
  curl -s -o /dev/null -w "%{http_code}" http://payment-service:8080/health
```

#### B. RDS Connection Refused (max_connections exhausted)
```bash
# Check current connections vs max
aws rds describe-db-instances --db-instance-identifier order-db \
  --query 'DBInstances[0].{MaxConns:DBInstanceClass,Status:DBInstanceStatus}'

# Force close idle connections (connect via bastion)
psql -h order-db.cluster-xxxx.us-east-1.rds.amazonaws.com -U sre_readonly -d orders \
  -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'idle';"

# If idle count is high, terminate idle connections
psql -h order-db.cluster-xxxx.us-east-1.rds.amazonaws.com -U admin -d orders \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle' AND query_start < NOW() - INTERVAL '5 minutes';"
```

#### C. Redis Cache Unreachable
```bash
# Check ElastiCache cluster status
aws elasticache describe-cache-clusters \
  --cache-cluster-id checkout-redis \
  --query 'CacheClusters[0].{Status:CacheClusterStatus,Endpoint:ConfigurationEndpoint}'

# Test connectivity from within the VPC
kubectl exec -n production deploy/checkout-service -- \
  redis-cli -h checkout-redis.xxxx.cache.amazonaws.com ping
```

### Step 2 — Check security groups / NACLs
```bash
# Verify checkout-service SG allows outbound to payment-service SG
aws ec2 describe-security-groups --group-ids sg-checkout-service \
  --query 'SecurityGroups[0].IpPermissionsEgress'

# Check VPC flow logs for rejected traffic
aws logs filter-log-events \
  --log-group-name vpc-flow-logs \
  --filter-pattern "REJECT" \
  --start-time $(date -d '30 minutes ago' +%s000)
```

### Step 3 — Immediate Mitigation

| Root Cause | Immediate Action |
|---|---|
| Payment service crashed | Restart: `kubectl rollout restart deploy/payment-service -n production` |
| RDS max connections | Scale RDS instance or restart connection pool: `kubectl rollout restart deploy/checkout-service -n production` |
| Redis cluster failover | ElastiCache auto-fails over; wait 60s and monitor |
| Network ACL misconfiguration | Revert last infra change; see [Rollback Procedure](#rollback-procedure) |

---

## Triage: Timeout Errors

**Silver error_category**: `timeout`  
**Typical log pattern**: `ReadTimeoutException`, `SocketTimeoutException`, `context deadline exceeded`, `timed out after`

### Step 1 — Identify timeout scope

```bash
# Filter for timeout errors and extract duration hints
aws logs filter-log-events \
  --log-group-name /aws/lambda/checkout-service \
  --start-time $(date -d '1 hour ago' +%s000) \
  --filter-pattern '"timed out" OR "timeout" OR "deadline exceeded"' \
  --query 'events[*].message'
```

Distinguish:
- **Client timeout**: checkout-service is waiting too long for a downstream response
- **Lambda timeout**: the Lambda function itself exceeded its configured timeout (check `REPORT RequestId` lines for `Duration` near the limit)
- **DB query timeout**: slow SQL queries blocking threads

### Step 2 — Check downstream service latency

```bash
# CloudWatch — payment-service target response time P99
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name TargetResponseTime \
  --dimensions Name=TargetGroup,Value=<payment-tg-arn> \
  --start-time $(date -d '30 minutes ago' -u +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 60 --statistics p99

# Check RDS slow query log (enable if not already)
aws rds describe-db-log-files --db-instance-identifier order-db \
  --filename-contains slowquery

aws rds download-db-log-file-portion \
  --db-instance-identifier order-db \
  --log-file-name slowquery/mysql-slowquery.log \
  --output text | tail -100
```

### Step 3 — Check Lambda configuration
```bash
# Lambda timeout setting
aws lambda get-function-configuration --function-name checkout-service \
  --query '{Timeout:Timeout,MemorySize:MemorySize}'

# Recent Lambda timeout events
aws logs filter-log-events \
  --log-group-name /aws/lambda/checkout-service \
  --filter-pattern '"Task timed out"'
```

### Step 4 — Immediate Mitigation

| Root Cause | Immediate Action |
|---|---|
| Downstream service slow | Enable circuit breaker if available; reduce timeout + fail fast |
| Lambda too short timeout | `aws lambda update-function-configuration --function-name checkout-service --timeout 60` |
| RDS slow queries | Kill long-running queries; add index if missing (review slow query log first) |
| High CPU on EKS nodes | `kubectl top nodes`; scale node group if needed |

```bash
# Scale checkout-service replicas if throughput is the issue
kubectl scale deploy checkout-service --replicas=5 -n production

# Kill a specific long-running RDS query (get pid from pg_stat_activity)
psql -h order-db... -U admin -d orders \
  -c "SELECT pg_cancel_backend(<pid>);"
```

---

## Escalation Path

```
Level 1 (On-Call SRE, 0–15 min)
  └── Follow this runbook
  └── If not resolved in 15 min → escalate to Level 2

Level 2 (Senior SRE / Platform Lead, 15–45 min)
  └── Review recent deployments: git log --oneline -20
  └── Check AWS Service Health Dashboard: https://health.aws.amazon.com
  └── If database involved → escalate to Database Engineer
  └── If payment-related → escalate to Level 3 (Payment Team Lead)

Level 3 (Engineering Manager + Payment Team, 45+ min or P1)
  └── Engage AWS Support if AWS infrastructure issue suspected
  └── Initiate incident bridge call
  └── Consider initiating rollback (see below)

Contacts (replace with actual):
  On-Call SRE:       PagerDuty rotation "sre-oncall"
  Platform Lead:     @platform-lead on internal Slack / +1-555-000-0001
  Database Engineer: @db-engineer
  Payment Team Lead: @payment-lead
  AWS Support:       https://console.aws.amazon.com/support/
```

---

## Rollback Procedure

Use these steps when a bad deployment caused the incident.

### Step 1 — Identify the last good deployment
```bash
# EKS deployment history
kubectl rollout history deploy/checkout-service -n production

# Lambda version history
aws lambda list-versions-by-function --function-name checkout-service \
  --query 'Versions[-5:].{Version:Version,LastModified:LastModified}'
```

### Step 2 — Roll back Kubernetes deployment
```bash
# Roll back to previous revision
kubectl rollout undo deploy/checkout-service -n production

# Roll back to a specific revision number
kubectl rollout undo deploy/checkout-service -n production --to-revision=<N>

# Monitor rollout progress
kubectl rollout status deploy/checkout-service -n production

# Verify pods are healthy post-rollback
kubectl get pods -n production -l app=checkout-service
```

### Step 3 — Roll back Lambda function
```bash
# Get the previous function version ARN
PREV_VERSION=$(aws lambda list-versions-by-function \
  --function-name checkout-service \
  --query 'Versions[-2].Version' --output text)

# Update the alias to point to the previous version
aws lambda update-alias \
  --function-name checkout-service \
  --name live \
  --function-version $PREV_VERSION
```

### Step 4 — Roll back CloudFormation stack
```bash
# Check stack events to identify failed change
aws cloudformation describe-stack-events \
  --stack-name sre-lambda-tools \
  --query 'StackEvents[?ResourceStatus==`UPDATE_FAILED`]'

# Roll back to last stable state
aws cloudformation cancel-update-stack --stack-name sre-lambda-tools
# OR use a known-good template revision:
aws cloudformation deploy \
  --template-file infra/04-lambda-tools.yaml \
  --stack-name sre-lambda-tools \
  --parameter-overrides DatabricksHost=<HOST> DatabricksHttpPath=<PATH>
```

### Step 5 — Verify recovery
```bash
# Smoke test checkout endpoint
curl -X POST https://api.example.com/checkout \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <test-token>" \
  -d '{"cart_id": "smoke-test-001"}' \
  -w "\nHTTP status: %{http_code}\n"

# Confirm error rate returning to baseline in CloudWatch
# Or ask the SRE Copilot: "Is checkout-service recovering?"
```

---

## Post-Incident Checklist

- [ ] Error rate confirmed returning to baseline
- [ ] All downstream dependencies verified healthy
- [ ] RDS connection count back to normal range
- [ ] CloudWatch alarms cleared
- [ ] Incident timeline documented (use `postmortem-template.md`)
- [ ] PagerDuty incident resolved
- [ ] Action items filed as tickets
- [ ] Runbook updated if new failure modes discovered

---

*This runbook is stored in the Bedrock Knowledge Base (S3) and used as RAG context by the SRE Copilot Agent. Keep it up to date after every incident.*
