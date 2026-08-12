# Deployment Guide

This directory contains all deployment-related scripts, CloudFormation templates, and workflow configurations for the multi-business bakery platform.

## Architecture Overview

The platform uses a **hybrid deployment strategy**:

- **Backend code deploys with Auth_Module** - Single deployment unit for simplicity
- **Auth infrastructure is separate** - Secrets and resources have dedicated lifecycle
- **Auth migrations are separate workflow** - Database operations controlled independently
- **Infrastructure as Code** - CloudFormation templates for reproducible deployments

## Directory Structure

```
deployment/
├── cloudformation/
│   ├── backend-infrastructure.yaml    # ECS, ALB, security groups
│   └── auth-infrastructure.yaml        # Secrets, Redis, monitoring
├── deploy.sh                           # Local deployment script
└── README.md                           # This file
```

## Quick Start

### Prerequisites

- AWS CLI installed and configured
- Docker installed
- Python 3.9+
- jq installed (for JSON processing)
- AWS credentials with appropriate permissions

### Initial Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd multi_business_website
   ```

2. **Set environment variables:**
   ```bash
   export AWS_REGION=us-east-1
   export PROJECT_NAME=multi-business-bakery
   export VPC_ID=<your-vpc-id>
   export PRIVATE_SUBNET_1=<your-private-subnet-1>
   export PRIVATE_SUBNET_2=<your-private-subnet-2>
   export PUBLIC_SUBNET_1=<your-public-subnet-1>
   export PUBLIC_SUBNET_2=<your-public-subnet-2>
   export AWS_ACCOUNT_ID=<your-account-id>
   ```

3. **Make deployment script executable:**
   ```bash
   chmod +x deployment/deploy.sh
   ```

## Deployment Commands

### Local Deployment Script

The `deploy.sh` script provides a simple interface for local development deployments:

```bash
# Deploy everything (infrastructure + code) to staging
./deployment/deploy.sh all staging

# Deploy backend infrastructure only
./deployment/deploy.sh backend-infra staging

# Deploy auth infrastructure only
./deployment/deploy.sh auth-infra staging

# Build and push Docker image
./deployment/deploy.sh build staging

# Deploy to ECS
./deployment/deploy.sh deploy staging

# Run auth migrations
./deployment/deploy.sh migrations staging

# Revoke legacy sessions (cutover)
./deployment/deploy.sh revoke-sessions staging

# Run security sweep
./deployment/deploy.sh security-sweep staging
```

### GitHub Actions Workflows

For production deployments, use the GitHub Actions workflows:

#### Backend Deployment

**File:** `.github/workflows/backend-deployment.yml`

**Triggers:**
- Push to main branch (backend files changed)
- Manual workflow dispatch

**Parameters:**
- `environment` - Target environment (staging/production)
- `run_auth_workflows` - Whether to trigger auth deployment

**Usage:**
```bash
# Trigger via GitHub UI or CLI
gh workflow run backend-deployment.yml \
  -f environment=staging \
  -f run_auth_workflows=false
```

#### Auth Deployment

**File:** `.github/workflows/auth-deployment.yml`

**Triggers:**
- Manual workflow dispatch only

**Parameters:**
- `environment` - Target environment
- `run_migrations` - Run database migrations
- `enforce_mfa` - Enable MFA enforcement
- `revoke_legacy_sessions` - Cutover to new auth system

**Usage:**
```bash
# Trigger auth deployment with migrations
gh workflow run auth-deployment.yml \
  -f environment=staging \
  -f run_migrations=true \
  -f enforce_mfa=false \
  -f revoke_legacy_sessions=false

# Enable MFA enforcement
gh workflow run auth-deployment.yml \
  -f environment=production \
  -f run_migrations=false \
  -f enforce_mfa=true \
  -f revoke_legacy_sessions=false

# Cutover to new auth system
gh workflow run auth-deployment.yml \
  -f environment=production \
  -f run_migrations=false \
  -f enforce_mfa=true \
  -f revoke_legacy_sessions=true
```

## CloudFormation Templates

### Backend Infrastructure

**File:** `deployment/cloudformation/backend-infrastructure.yaml`

**Resources:**
- ECS Cluster
- ECS Task Definition
- ECS Service
- Application Load Balancer
- Target Groups
- Security Groups
- IAM Roles
- CloudWatch Alarms

**Deployment:**
```bash
aws cloudformation deploy \
  --template-file deployment/cloudformation/backend-infrastructure.yaml \
  --stack-name multi-business-bakery-staging-backend \
  --parameter-overrides \
    Environment=staging \
    ProjectName=multi-business-bakery \
    VpcId=$VPC_ID \
    PrivateSubnet1=$PRIVATE_SUBNET_1 \
    PrivateSubnet2=$PRIVATE_SUBNET_2 \
    PublicSubnet1=$PUBLIC_SUBNET_1 \
    PublicSubnet2=$PUBLIC_SUBNET_2 \
  --capabilities CAPABILITY_IAM
```

### Auth Infrastructure

**File:** `deployment/cloudformation/auth-infrastructure.yaml`

**Resources:**
- Secrets Manager (MFA encryption key, JWT secret, webhook secret)
- SSM Parameters (auth configuration, MFA configuration)
- Redis cluster (for rate limiting, optional)
- CloudWatch alarms (auth metrics monitoring)

**Deployment:**
```bash
aws cloudformation deploy \
  --template-file deployment/cloudformation/auth-infrastructure.yaml \
  --stack-name multi-business-bakery-staging-auth-infrastructure \
  --parameter-overrides \
    Environment=staging \
    ProjectName=multi-business-bakery \
    RedisEnabled=false \
  --capabilities CAPABILITY_IAM
```

## Deployment Scenarios

### Scenario 1: Initial Deployment to Staging

**Goal:** Deploy infrastructure and backend code to staging

**Steps:**
```bash
# 1. Deploy backend infrastructure
./deployment/deploy.sh backend-infra staging

# 2. Deploy auth infrastructure
./deployment/deploy.sh auth-infra staging

# 3. Build and push Docker image
./deployment/deploy.sh build staging

# 4. Deploy to ECS
./deployment/deploy.sh deploy staging

# 5. Run auth migrations
./deployment/deploy.sh migrations staging
```

### Scenario 2: Enable MFA Enforcement

**Goal:** Enable MFA for privileged users in staging

**Steps:**
```bash
# 1. Update SSM parameter to enable MFA
aws ssm put-parameter \
  --name /multi-business-bakery/staging/auth/config \
  --value '{"mfa_enforce_for_admins":"true","auth_accept_legacy_session":"true","auth_rate_limit_per_minute":"10","webhook_skip_verify":"false","max_sessions_per_user":"5","access_token_ttl_seconds":"900","refresh_token_ttl_seconds":"604800"}' \
  --type String \
  --overwrite

# 2. Restart ECS tasks to pick up new configuration
aws ecs update-service \
  --cluster multi-business-bakery-staging-cluster \
  --service multi-business-bakery-backend \
  --force-new-deployment
```

### Scenario 3: Legacy Session Cutover

**Goal:** Disable legacy session acceptance and revoke existing sessions

**Steps:**
```bash
# 1. Check current enrollment status
./deployment/deploy.sh migrations staging

# 2. Verify MFA enrollment rate is 100%
# (Check migration report output)

# 3. Revoke legacy sessions
./deployment/deploy.sh revoke-sessions staging

# 4. Update SSM parameter to disable legacy sessions
aws ssm put-parameter \
  --name /multi-business-bakery/staging/auth/config \
  --value '{"mfa_enforce_for_admins":"true","auth_accept_legacy_session":"false","auth_rate_limit_per_minute":"10","webhook_skip_verify":"false","max_sessions_per_user":"5","access_token_ttl_seconds":"900","refresh_token_ttl_seconds":"604800"}' \
  --type String \
  --overwrite

# 5. Restart ECS tasks
aws ecs update-service \
  --cluster multi-business-bakery-staging-cluster \
  --service multi-business-bakery-backend \
  --force-new-deployment

# 6. Run security sweep
./deployment/deploy.sh security-sweep staging
```

### Scenario 4: Production Deployment

**Goal:** Deploy to production with full MFA enforcement

**Steps:**
```bash
# 1. Deploy to staging first (verify everything works)
./deployment/deploy.sh all staging

# 2. Test auth flows in staging
# - Login with Google OAuth
# - MFA enrollment
# - MFA verification
# - Token refresh

# 3. Deploy backend infrastructure to production
aws cloudformation deploy \
  --template-file deployment/cloudformation/backend-infrastructure.yaml \
  --stack-name multi-business-bakery-production-backend \
  --parameter-overrides \
    Environment=production \
    ProjectName=multi-business-bakery \
    VpcId=$PROD_VPC_ID \
    PrivateSubnet1=$PROD_PRIVATE_SUBNET_1 \
    PrivateSubnet2=$PROD_PRIVATE_SUBNET_2 \
    PublicSubnet1=$PROD_PUBLIC_SUBNET_1 \
    PublicSubnet2=$PROD_PUBLIC_SUBNET_2 \
  --capabilities CAPABILITY_IAM

# 4. Deploy auth infrastructure to production
aws cloudformation deploy \
  --template-file deployment/cloudformation/auth-infrastructure.yaml \
  --stack-name multi-business-bakery-production-auth-infrastructure \
  --parameter-overrides \
    Environment=production \
    ProjectName=multi-business-bakery \
    RedisEnabled=true \
  --capabilities CAPABILITY_IAM

# 5. Build and push Docker image
./deployment/deploy.sh build production

# 6. Deploy to production ECS
./deployment/deploy.sh deploy production

# 7. Run auth migrations in production
./deployment/deploy.sh migrations production

# 8. Monitor metrics and user enrollment
# (Use CloudWatch dashboard)

# 9. When ready, enable MFA enforcement
gh workflow run auth-deployment.yml \
  -f environment=production \
  -f run_migrations=false \
  -f enforce_mfa=true \
  -f revoke_legacy_sessions=false

# 10. After MFA enrollment reaches 100%, cutover
gh workflow run auth-deployment.yml \
  -f environment=production \
  -f run_migrations=false \
  -f enforce_mfa=true \
  -f revoke_legacy_sessions=true
```

## Environment Variables

### Required for Local Deployment

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012

# Project Configuration
PROJECT_NAME=multi-business-bakery
ENVIRONMENT=staging

# Network Configuration
VPC_ID=vpc-xxxxxxxx
PRIVATE_SUBNET_1=subnet-xxxxxxxx
PRIVATE_SUBNET_2=subnet-xxxxxxxx
PUBLIC_SUBNET_1=subnet-xxxxxxxx
PUBLIC_SUBNET_2=subnet-xxxxxxxx

# MongoDB Configuration (for migrations)
MONGO_URL=mongodb://localhost:27017
DB_NAME=multi_business_db
```

### Required for Production

In addition to the above, production requires:

```bash
# SSL Certificate
SSL_CERTIFICATE_ARN=arn:aws:acm:region:account:certificate/xxxxxxxx

# MongoDB (from Secrets Manager)
# These are typically stored in AWS Secrets Manager
# and referenced by the task definition, not as env vars
```

## Secrets Management

### Creating Secrets

**MFA Encryption Key:**
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**JWT Secret:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Razorpay Webhook Secret:**
```bash
# Get from Razorpay dashboard
```

### Storing Secrets in AWS Secrets Manager

```bash
# MFA Encryption Key
aws secretsmanager create-secret \
  --name multi-business-bakery-staging/mfa-encryption-key \
  --secret-string '{"mfa_encryption_key":"your-32-char-key"}'

# JWT Secret
aws secretsmanager create-secret \
  --name multi-business-bakery-staging/jwt-secret \
  --secret-string '{"jwt_secret":"your-jwt-secret"}'

# Razorpay Webhook Secret
aws secretsmanager create-secret \
  --name multi-business-bakery-staging/razorpay-webhook-secret \
  --secret-string '{"razorpay_webhook_secret":"your-webhook-secret"}'
```

## Monitoring

### CloudWatch Metrics

**Backend Metrics:**
- CPU utilization
- Memory utilization
- Request count
- Error rate
- Latency

**Auth Metrics:**
- MFA verification success rate
- MFA verification failure rate
- Authentication failure rate
- Rate limit exceeded count
- Token refresh success rate

### CloudWatch Alarms

**Backend Alarms:**
- CPU utilization > 80%
- Memory utilization > 80%
- Error rate > 5%

**Auth Alarms:**
- MFA verification failure rate > 5%
- Authentication failure rate > 10%
- Rate limit exceeded > 100 in 5 minutes

### Log Streams

**Backend Logs:**
- ECS task logs
- Application logs
- Error logs

**Auth Logs:**
- MFA enrollment events
- MFA verification events
- Token refresh events
- Session revocation events

## Troubleshooting

### Common Issues

**Issue: Deployment fails with "Stack does not exist"**

**Solution:**
```bash
# Check if stack exists
aws cloudformation describe-stacks --stack-name <stack-name>

# If it doesn't exist, the script will create it automatically
# If it does exist but is in a failed state, delete it first
aws cloudformation delete-stack --stack-name <stack-name>
```

**Issue: ECS tasks can't access secrets**

**Solution:**
```bash
# Check IAM role permissions
aws iam get-role-policy \
  --role-name <task-role-name> \
  --policy-name secrets-access

# Verify secret ARN is correct
aws secretsmanager describe-secret \
  --secret-id <secret-name>
```

**Issue: MFA verification failing**

**Solution:**
```bash
# Check MFA_ENCRYPTION_KEY is set
aws secretsmanager get-secret-value \
  --secret-id multi-business-bakery-staging/mfa-encryption-key

# Check SSM parameter for MFA enforcement
aws ssm get-parameter \
  --name /multi-business-bakery/staging/auth/config

# Verify MongoDB indexes exist
# Connect to MongoDB and check:
# db.mfa_pending_enrollments.getIndexes()
# db.users.getIndexes()
```

**Issue: Rate limiting not working**

**Solution:**
```bash
# Check Redis is accessible
aws elasticache describe-replication-groups \
  --replication-group-id <redis-cluster-name>

# Check REDIS_URL is set in task definition
aws ecs describe-task-definition \
  --task-definition <task-def-arn> \
  --query 'taskDefinition.containerDefinitions[0].environment'
```

## Rollback Procedures

### Backend Rollback

```bash
# Revert to previous task definition
aws ecs update-service \
  --cluster <cluster-name> \
  --service <service-name> \
  --task-definition <previous-task-def-arn>

# Wait for rollback to complete
aws ecs wait services-stable \
  --cluster <cluster-name> \
  --services <service-name>
```

### Auth Configuration Rollback

```bash
# Disable MFA enforcement
aws ssm put-parameter \
  --name /multi-business-bakery/staging/auth/config \
  --value '{"mfa_enforce_for_admins":"false","auth_accept_legacy_session":"true",...}' \
  --type String \
  --overwrite

# Restart ECS tasks
aws ecs update-service \
  --cluster <cluster-name> \
  --service <service-name> \
  --force-new-deployment
```

### Infrastructure Rollback

```bash
# CloudFormation automatically rolls back on failure
# Manual rollback:
aws cloudformation rollback-stack \
  --stack-name <stack-name> \
  --role-arn <role-arn>
```

## Best Practices

### Development

1. **Test locally** before deploying to staging
2. **Use environment variables** for local development
3. **Run tests** before building Docker image
4. **Review logs** after deployment

### Staging

1. **Always deploy to staging first** before production
2. **Test all auth flows** in staging
3. **Verify monitoring** is working
4. **Review migration reports** before production

### Production

1. **Schedule deployments** during low-traffic periods
2. **Have rollback plan** ready before deployment
3. **Monitor metrics** closely after deployment
4. **Document any issues** for future reference

## Cost Optimization

### Development/Staging

- Use smaller ECS task sizes (0.25 vCPU, 512MB memory)
- Disable Redis (use in-memory rate limiting)
- Use lower desired count (1-2 tasks)
- Shorter log retention (7 days)

### Production

- Use appropriate ECS task sizes (0.5-1 vCPU, 1-2GB memory)
- Enable Redis for distributed rate limiting
- Use appropriate desired count (2+ tasks)
- Longer log retention (30 days)

## Support

For deployment issues:
- **Primary Contact**: DevOps Team
- **Secondary Contact**: Security Team
- **Escalation**: CTO Office

## References

- [Deployment Architecture Guide](../docs/DEPLOYMENT_ARCHITECTURE.md)
- [MFA Setup and Migration Guide](../docs/MFA_SETUP_MIGRATION.md)
- [Production Security Checklist](../docs/PRODUCTION_SECURITY_CHECKLIST.md)
- [JWT Key Rotation Guide](../docs/JWT_KEY_ROTATION.md)
