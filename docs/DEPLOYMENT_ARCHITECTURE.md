# Deployment Architecture Guide

## Overview

This document describes the recommended deployment architecture for the multi-business bakery platform's authentication and security infrastructure.

## Architecture Decision: Hybrid Deployment Strategy

### Recommended Approach

We use a **hybrid deployment strategy** where:

1. **Auth code deploys with backend** - Auth_Module, MFA routes, and security middleware are part of the main backend codebase
2. **Auth infrastructure is separate** - Secrets, Redis, and monitoring resources have their own CloudFormation stack
3. **Auth migrations are separate workflow** - Database migrations and cutover procedures run independently
4. **Backend deployment triggers auth workflows** - Main deployment can optionally trigger auth-specific workflows

### Why This Approach?

#### Advantages

**Code Deployment with Backend:**
- ✅ **No network overhead** - Auth code runs in the same process as business logic
- ✅ **Simpler development** - No microservice complexity or API versioning
- ✅ **Consistent environment** - Same runtime, same configuration, same dependencies
- ✅ **Easier debugging** - Single codebase, single deployment unit
- ✅ **Cost-effective** - No additional infrastructure for auth service

**Separate Infrastructure:**
- ✅ **Security isolation** - Secrets and auth resources have dedicated lifecycle
- ✅ **Independent scaling** - Redis for rate limiting can scale independently
- ✅ **Compliance** - Secrets management follows security best practices
- ✅ **Observability** - Auth metrics can be monitored independently

**Separate Migrations:**
- ✅ **Phased rollout** - Deploy code first, then run migrations
- ✅ **Safe rollback** - Can rollback code without rolling back migrations
- ✅ **Manual control** - Migrations require explicit trigger (important for cutover)
- ✅ **Auditable** - Each migration run is logged and can be reviewed

#### Alternatives Considered

**Option 1: Monolithic Deployment (Everything Together)**
- ❌ Migrations would run automatically on every deploy (risky for cutover)
- ❌ Can't deploy code without running migrations
- ❌ No separation of concerns between code and infrastructure
- ❌ Harder to rollback migrations independently

**Option 2: Separate Auth Microservice**
- ❌ Network overhead and latency
- ❌ Additional infrastructure complexity
- ❌ Duplicate deployment configuration
- ❌ Harder to debug distributed issues
- ❌ Higher operational cost

**Option 3: Infrastructure as Code in Main Stack**
- ❌ Secrets would be created with every backend deploy
- ❌ Harder to manage secret rotation
- ❌ Can't update infrastructure without deploying code
- ❌ Blurs line between application and infrastructure

## Deployment Flow

### Normal Backend Deployment

```
Push to main
    ↓
Build Backend (Docker image)
    ↓
Run Tests
    ↓
Push to ECR
    ↓
Deploy to ECS
    ↓
Backend is live with Auth code
```

### Auth Infrastructure Deployment

```
Manual trigger or schedule
    ↓
Deploy CloudFormation Stack
    ↓
Create/Update Secrets
    ↓
Create/Update SSM Parameters
    ↓
Deploy Redis (if enabled)
    ↓
Create CloudWatch Alarms
    ↓
Backend ECS tasks pick up new secrets
```

### Auth Migration Workflow

```
Manual trigger (with parameters)
    ↓
Deploy Auth Infrastructure (if needed)
    ↓
Run Database Migrations
    │   - Create MFA indexes
    │   - Generate migration report
    ↓
Optional: Revoke Legacy Sessions
    │   - Check statistics
    │   - Revoke legacy sessions
    │   - Update SSM parameter
    ↓
Optional: Enable MFA Enforcement
    │   - Update SSM parameter
    │   - ECS tasks pick up new config
    ↓
Run Security Sweep
    │   - Verify privileged APIs
    │   - Check authentication enforcement
    ↓
Generate Deployment Summary
```

## Component Breakdown

### 1. Backend Deployment Workflow

**File:** `.github/workflows/backend-deployment.yml`

**Responsibilities:**
- Build and test backend code
- Build Docker image
- Push to ECR
- Deploy to ECS
- Optionally trigger auth deployment

**Triggers:**
- Push to main branch (backend files changed)
- Manual workflow dispatch

**Environment Variables:**
- `run_auth_workflows` - Whether to trigger auth deployment
- `environment` - Target environment (staging/production)

### 2. Auth Deployment Workflow

**File:** `.github/workflows/auth-deployment.yml`

**Responsibilities:**
- Deploy auth infrastructure (CloudFormation)
- Run database migrations
- Revoke legacy sessions (cutover)
- Enable MFA enforcement
- Run security sweep

**Triggers:**
- Manual workflow dispatch only
- Can be triggered by backend deployment

**Parameters:**
- `environment` - Target environment
- `run_migrations` - Run database migrations
- `enforce_mfa` - Enable MFA enforcement
- `revoke_legacy_sessions` - Cutover to new auth system

### 3. Auth Infrastructure CloudFormation

**File:** `deployment/cloudformation/auth-infrastructure.yaml`

**Resources:**
- Secrets Manager (MFA encryption key, JWT secret, webhook secret)
- SSM Parameters (auth configuration, MFA configuration)
- Redis cluster (for rate limiting, optional)
- CloudWatch alarms (auth metrics monitoring)

**Outputs:**
- Secret ARNs (for ECS task definition)
- Redis endpoint (for rate limiting)
- SSM parameter names

## Deployment Scenarios

### Scenario 1: Initial Deployment

**Goal:** Deploy Auth infrastructure with MFA disabled

**Steps:**
1. Deploy backend code (includes Auth_Module)
2. Trigger auth deployment workflow:
   - `environment: staging`
   - `run_migrations: true`
   - `enforce_mfa: false`
   - `revoke_legacy_sessions: false`

**Result:**
- Backend running with Auth_Module
- Secrets created in Secrets Manager
- MongoDB indexes created
- MFA not enforced (users can log in normally)

### Scenario 2: Enable MFA Enforcement

**Goal:** Enable MFA for privileged users

**Steps:**
1. Communicate with users about MFA rollout
2. Trigger auth deployment workflow:
   - `environment: staging`
   - `run_migrations: true`
   - `enforce_mfa: true`
   - `revoke_legacy_sessions: false`

**Result:**
- MFA enforcement enabled via SSM parameter
- ECS tasks pick up new configuration
- Users prompted to enroll in MFA on next login

### Scenario 3: Legacy Session Cutover

**Goal:** Disable legacy session acceptance and revoke existing sessions

**Steps:**
1. Verify MFA enrollment rate is 100%
2. Trigger auth deployment workflow:
   - `environment: production`
   - `run_migrations: false`
   - `enforce_mfa: true`
   - `revoke_legacy_sessions: true`

**Result:**
- Legacy sessions revoked from database
- `AUTH_ACCEPT_LEGACY_SESSION` set to false
- All users must use new JWT authentication

### Scenario 4: Secret Rotation

**Goal:** Rotate MFA encryption key

**Steps:**
1. Update CloudFormation stack with new secret (or use AWS Secrets Manager rotation)
2. Trigger auth deployment workflow:
   - `environment: production`
   - `run_migrations: false`
   - `enforce_mfa: true`
   - `revoke_legacy_sessions: false`

**Result:**
- New secret created in Secrets Manager
- ECS tasks pick up new secret ARN
- Old secret remains valid until old sessions expire

## Security Considerations

### Secret Management

**Best Practices:**
- ✅ Secrets stored in AWS Secrets Manager with KMS encryption
- ✅ Secrets referenced by ARN, not by value
- ✅ ECS tasks use Secrets Manager for runtime secret resolution
- ✅ Secret rotation supported (via CloudFormation or AWS Secrets Manager rotation)
- ✅ Never log or output secret values

**Implementation:**
```yaml
# CloudFormation
MFAEncryptionKeySecret:
  Type: AWS::SecretsManager::Secret
  Properties:
    SecretString: '{"mfa_encryption_key":"random_value"}'
    KmsKeyId: alias/aws/secretsmanager

# ECS Task Definition
secrets:
  - name: MFA_ENCRYPTION_KEY
    valueFrom: arn:aws:secretsmanager:region:account:secret:mfa-encryption-key
```

### Database Migrations

**Safety Measures:**
- ✅ Migrations require explicit trigger (not automatic)
- ✅ Migration steps are idempotent (can run multiple times safely)
- ✅ Migration reports are saved as artifacts
- ✅ Failed migrations stop the workflow
- ✅ Rollback procedures documented

**Implementation:**
```python
# Idempotent index creation
await db.collection.create_index(
    [('field', 1)],
    background=True
)  # Safe to run multiple times
```

### Phased Rollout

**Strategy:**
1. Deploy code to staging
2. Run migrations in staging
3. Test auth flows in staging
4. Deploy code to production
5. Run migrations in production (manual trigger)
6. Monitor metrics
7. Enable MFA enforcement (separate trigger)
8. Monitor user enrollment
9. Revoke legacy sessions (separate trigger)

## Monitoring and Observability

### CloudWatch Alarms

**Auth Metrics:**
- MFA verification failure rate (>5%)
- Authentication failure rate (>10%)
- Rate limit exceeded count (>100 in 5 minutes)

**Custom Metrics:**
- MFA enrollment rate
- Legacy session usage
- Token refresh success rate
- Webhook verification failures

### Log Streams

**Auth Module Logs:**
- Enrollment events
- Verification events
- Token refresh events
- Session revocation events
- Rate limit events

**CloudWatch Insights Queries:**
```sql
fields @timestamp, event_type, user_id, success
| filter event_type like /MFA_/
| stats count() by event_type, success
```

## Rollback Procedures

### Backend Rollback

**Scenario:** New backend code breaks auth

**Steps:**
1. Revert backend deployment to previous image
2. ECS automatically rolls back task definition
3. Auth infrastructure unchanged (secrets still valid)
4. No need to rollback migrations

**Command:**
```bash
aws ecs update-service \
  --cluster cluster-name \
  --service service-name \
  --task-definition previous-task-def-arn
```

### Auth Configuration Rollback

**Scenario:** MFA enforcement causing issues

**Steps:**
1. Update SSM parameter to disable MFA
2. ECS tasks pick up new configuration (next deployment or manual restart)
3. No code rollback needed

**Command:**
```bash
aws ssm put-parameter \
  --name /project/environment/auth/config \
  --value '{"mfa_enforce_for_admins":"false",...}' \
  --overwrite
```

### Infrastructure Rollback

**Scenario:** CloudFormation deployment fails

**Steps:**
1. CloudFormation automatically rolls back on failure
2. Previous infrastructure state preserved
3. No impact on running ECS tasks

**Command:**
```bash
aws cloudformation rollback-stack \
  --stack-name stack-name \
  --role-arn role-arn
```

## Cost Optimization

### Redis Usage

**Development/Testing:**
- Use in-memory rate limiting (no Redis)
- Lower cost, simpler setup

**Production:**
- Use Redis for distributed rate limiting
- Higher cost, better scalability

**Configuration:**
```yaml
RedisEnabled:
  Type: String
  Default: false  # Disabled by default
```

### CloudWatch Alarms

**Standard Metrics:**
- Custom metrics for auth events
- Alarms for critical thresholds
- Reasonable evaluation periods (5 minutes)

**Cost Estimate:**
- Custom metrics: ~$0.50 per metric per month
- Alarms: Included with metrics
- Total: ~$2-3 per month for auth monitoring

## Troubleshooting

### Common Issues

**Issue: ECS tasks can't access secrets**

**Diagnosis:**
- Check IAM role permissions
- Verify secret ARN is correct
- Check secret exists in Secrets Manager

**Solution:**
```bash
aws iam get-role-policy \
  --role-name ecs-task-role \
  --policy-name secrets-access
```

**Issue: MFA enrollment failing**

**Diagnosis:**
- Check MFA_ENCRYPTION_KEY is set
- Verify encryption key is valid Fernet key
- Check MongoDB indexes exist

**Solution:**
```bash
aws secretsmanager get-secret-value \
  --secret-id mfa-encryption-key
```

**Issue: Rate limiting not working**

**Diagnosis:**
- Check Redis is accessible
- Verify REDIS_URL is set
- Check rate limit configuration

**Solution:**
```bash
aws elasticache describe-replication-groups \
  --replication-group-id redis-cluster-name
```

## Best Practices

### Development

1. **Test migrations locally** before running in staging
2. **Use environment variables** for local development
3. **Mock external services** (Redis, Secrets Manager) for tests
4. **Generate migration reports** to understand impact

### Staging

1. **Always run migrations** in staging before production
2. **Test auth flows** with real users
3. **Verify monitoring** is working
4. **Review migration reports** before production

### Production

1. **Schedule deployments** during low-traffic periods
2. **Have rollback plan** ready before deployment
3. **Monitor metrics** closely after deployment
4. **Document any issues** for future reference

## Conclusion

The hybrid deployment strategy provides the best balance of:
- **Simplicity** - Auth code deploys with backend
- **Security** - Secrets and infrastructure are separate
- **Flexibility** - Migrations can be controlled independently
- **Observability** - Auth metrics are monitored separately
- **Cost-effectiveness** - No unnecessary infrastructure duplication

This architecture is production-ready and follows AWS best practices for secure, scalable deployments.
