# AWS Deployment Guide — Jain Industries Multi-Business Platform

## Architecture Overview

```
                    ┌──────────────┐
                    │  Route 53    │  (DNS)
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  CloudFront  │  (CDN + SSL)
                    └──────┬───────┘
                           │
              ┌────────────┴────────────┐
              │                         │
    ┌─────────▼──────────┐   ┌─────────▼──────────┐
    │  S3 Bucket         │   │  ALB (Application   │
    │  (React Frontend)  │   │  Load Balancer)     │
    └────────────────────┘   └─────────┬───────────┘
                                       │
                              ┌────────▼────────┐
                              │  ECS Fargate     │
                              │  (FastAPI)       │
                              └────────┬────────┘
                                       │
                          ┌────────────┴────────────┐
                          │                         │
                ┌─────────▼──────────┐   ┌─────────▼──────────┐
                │  MongoDB Atlas     │   │  ElastiCache Redis  │
                │  (Primary DB)      │   │  (Sessions/Cache)   │
                └────────────────────┘   └────────────────────┘
```

---

## 1. Frontend Deployment (React → S3 + CloudFront)

### Build

```bash
cd frontend
# Set production API URL
echo "REACT_APP_BACKEND_URL=https://api.yourdomain.com" > .env.production
yarn build
```

### S3 Bucket Setup

```bash
# Create bucket
aws s3 mb s3://jain-industries-frontend --region ap-south-1

# Enable static website hosting
aws s3 website s3://jain-industries-frontend \
  --index-document index.html \
  --error-document index.html

# Upload build
aws s3 sync build/ s3://jain-industries-frontend --delete

# Bucket policy (public read for CloudFront OAI)
cat <<EOF > bucket-policy.json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "CloudFrontOAI",
    "Effect": "Allow",
    "Principal": {"AWS": "arn:aws:iam::cloudfront:user/CloudFront Origin Access Identity YOUR_OAI_ID"},
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::jain-industries-frontend/*"
  }]
}
EOF
aws s3api put-bucket-policy --bucket jain-industries-frontend --policy file://bucket-policy.json
```

### CloudFront Distribution

```bash
aws cloudfront create-distribution \
  --origin-domain-name jain-industries-frontend.s3.ap-south-1.amazonaws.com \
  --default-root-object index.html \
  --query 'Distribution.DomainName'
```

Key CloudFront settings:
- **Custom error response**: 403/404 → `/index.html` (200) — SPA routing
- **HTTPS**: ACM certificate for your domain
- **Cache behavior**: `index.html` → TTL 0 (no cache), `static/*` → TTL 1 year
- **Origin Access Identity**: Restrict S3 to CloudFront only

---

## 2. Backend Deployment (FastAPI → ECS Fargate)

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8001
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "4"]
```

### ECR (Container Registry)

```bash
# Create repository
aws ecr create-repository --repository-name jain-industries-api --region ap-south-1

# Login, build, push
aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT.dkr.ecr.ap-south-1.amazonaws.com

docker build -t jain-industries-api .
docker tag jain-industries-api:latest YOUR_ACCOUNT.dkr.ecr.ap-south-1.amazonaws.com/jain-industries-api:latest
docker push YOUR_ACCOUNT.dkr.ecr.ap-south-1.amazonaws.com/jain-industries-api:latest
```

### ECS Task Definition

```json
{
  "family": "jain-industries-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [{
    "name": "api",
    "image": "YOUR_ACCOUNT.dkr.ecr.ap-south-1.amazonaws.com/jain-industries-api:latest",
    "portMappings": [{"containerPort": 8001, "protocol": "tcp"}],
    "environment": [
      {"name": "MONGO_URL", "value": "mongodb+srv://user:pass@cluster.mongodb.net"},
      {"name": "DB_NAME", "value": "jain_industries_prod"},
      {"name": "CORS_ORIGINS", "value": "https://yourdomain.com"},
      {"name": "EMAIL_PROVIDER", "value": "resend"},
      {"name": "EMAIL_API_KEY", "value": "re_xxx"},
      {"name": "SENDER_EMAIL", "value": "orders@yourdomain.com"},
      {"name": "STRIPE_API_KEY", "value": "sk_live_xxx"}
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/jain-industries-api",
        "awslogs-region": "ap-south-1",
        "awslogs-stream-prefix": "api"
      }
    }
  }]
}
```

> **Tip**: Use AWS Secrets Manager or SSM Parameter Store for sensitive values instead of plain environment variables.

### ECS Service + ALB

```bash
# Create ECS cluster
aws ecs create-cluster --cluster-name jain-industries

# Create service with ALB
aws ecs create-service \
  --cluster jain-industries \
  --service-name api \
  --task-definition jain-industries-api \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=api,containerPort=8001"
```

ALB configuration:
- Listener: HTTPS 443 → Target Group (port 8001)
- Health check: `GET /api/health` → 200
- Enable sticky sessions if using server-side sessions

---

## 3. Database Options

### Option A: MongoDB Atlas (RECOMMENDED)

Best fit since the app already uses MongoDB with Motor async driver.

```
Pricing: M10 (dedicated) ~$57/month for production
Free tier: M0 (512 MB) for development

Setup:
1. atlas.mongodb.com → Create cluster in ap-south-1
2. Add ECS security group IPs to Network Access
3. Create database user
4. Connection string: mongodb+srv://user:pass@cluster.mongodb.net/jain_industries_prod
```

**Migration from local MongoDB:**
```bash
# Export from local
mongodump --db test_database --out ./dump

# Import to Atlas
mongorestore --uri="mongodb+srv://user:pass@cluster.mongodb.net/jain_industries_prod" ./dump/test_database
```

### Option B: Amazon DocumentDB (MongoDB-compatible)

AWS-managed MongoDB-compatible database. 90% API compatible with MongoDB 5.0.

```
Pricing: db.t3.medium ~$56/month
Pros: VPC-native, IAM auth, automated backups
Cons: Not 100% MongoDB compatible, no free tier, runs inside VPC only
```

```bash
aws docdb create-db-cluster \
  --db-cluster-identifier jain-industries-db \
  --engine docdb \
  --master-username admin \
  --master-user-password YOUR_PASSWORD
```

Connection string: `mongodb://admin:pass@jain-industries-db.cluster-xxx.ap-south-1.docdb.amazonaws.com:27017/?tls=true&retryWrites=false`

> Note: Motor driver works with DocumentDB. Add `?retryWrites=false` to connection string.

### Option C: DynamoDB (NOT RECOMMENDED for this app)

Would require a **complete rewrite** of the data layer:
- No MongoDB queries/aggregations
- No `$push`, `$set`, `$group` operators
- Different data modeling (single-table design)
- Motor/PyMongo won't work

Only consider if you need:
- Massive scale (millions of requests/sec)
- Pay-per-request pricing
- Serverless integration (Lambda)

### Option D: Amazon RDS (MySQL/PostgreSQL)

Would require replacing Motor/PyMongo with SQLAlchemy:
- Complete schema migration (documents → tables)
- Rewrite all queries
- Loss of flexible schema (variants, nested items)

```
Pricing: db.t3.micro (free tier eligible) → db.t3.medium ~$33/month
```

Only consider if team prefers SQL or needs complex JOINs.

### Database Comparison

| Feature | MongoDB Atlas | DocumentDB | DynamoDB | RDS MySQL |
|---------|:---:|:---:|:---:|:---:|
| Migration effort | **None** | Low | **Complete rewrite** | **Complete rewrite** |
| MongoDB driver compatible | Yes | 90% | No | No |
| Free tier | Yes (M0) | No | Yes (25 GB) | Yes (1 year) |
| Auto-scaling | Yes | Manual | Yes | Manual |
| Backup | Automated | Automated | Automated | Automated |
| Best for this app | **Yes** | Good | No | No |

---

## 4. SSE / WebSocket Support

The app uses Server-Sent Events for real-time notifications. On AWS:

- **ALB**: Supports SSE/WebSocket natively (increase idle timeout to 300s)
- **CloudFront**: Route `/api/*` requests directly to ALB (bypass CloudFront caching)
- **ECS**: Ensure task has enough connections for long-lived SSE streams

```bash
# ALB: Increase idle timeout for SSE
aws elbv2 modify-load-balancer-attributes \
  --load-balancer-arn YOUR_ALB_ARN \
  --attributes Key=idle_timeout.timeout_seconds,Value=300
```

---

## 5. CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ap-south-1
      - uses: aws-actions/amazon-ecr-login@v2
      - run: |
          docker build -t jain-industries-api .
          docker tag jain-industries-api:latest ${{ secrets.ECR_URI }}:latest
          docker push ${{ secrets.ECR_URI }}:latest
      - run: |
          aws ecs update-service --cluster jain-industries --service api --force-new-deployment

  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 18 }
      - run: cd frontend && yarn install && yarn build
        env:
          REACT_APP_BACKEND_URL: https://api.yourdomain.com
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ap-south-1
      - run: |
          aws s3 sync frontend/build/ s3://jain-industries-frontend --delete
          aws cloudfront create-invalidation --distribution-id ${{ secrets.CF_DIST_ID }} --paths "/*"
```

---

## 6. Environment Variables Checklist

### Backend (.env / ECS Task Definition)
```
MONGO_URL=mongodb+srv://...          # MongoDB Atlas connection string
DB_NAME=jain_industries_prod          # Production database name
CORS_ORIGINS=https://yourdomain.com   # Frontend domain
STRIPE_API_KEY=sk_live_xxx            # Stripe live key
EMAIL_PROVIDER=resend                 # resend | sendgrid | brevo | smtp | mailgun
EMAIL_API_KEY=re_xxx                  # API key for email provider
SENDER_EMAIL=orders@yourdomain.com    # From email address
```

### Frontend (.env.production)
```
REACT_APP_BACKEND_URL=https://api.yourdomain.com
```

---

## 7. Domain & SSL Setup

```bash
# Request ACM certificate
aws acm request-certificate \
  --domain-name yourdomain.com \
  --subject-alternative-names "*.yourdomain.com" \
  --validation-method DNS

# Route 53: Create hosted zone
aws route53 create-hosted-zone --name yourdomain.com --caller-reference $(date +%s)

# Add DNS records:
# yourdomain.com     → CloudFront distribution (A record alias)
# api.yourdomain.com → ALB DNS name (A record alias)
```

---

## 8. Monitoring & Logging

```bash
# CloudWatch Logs
aws logs create-log-group --log-group-name /ecs/jain-industries-api

# CloudWatch Alarms
aws cloudwatch put-metric-alarm \
  --alarm-name "API-5xx-errors" \
  --metric-name HTTPCode_Target_5XX_Count \
  --namespace AWS/ApplicationELB \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --alarm-actions arn:aws:sns:ap-south-1:xxx:alerts
```

---

## 9. Cost Estimate (ap-south-1, Production)

| Service | Configuration | Monthly Cost |
|---------|--------------|:---:|
| S3 | Frontend hosting | ~$1 |
| CloudFront | 100 GB transfer | ~$12 |
| ECS Fargate | 2x (0.5 vCPU, 1 GB) | ~$30 |
| ALB | Application LB | ~$22 |
| MongoDB Atlas | M10 dedicated | ~$57 |
| Route 53 | Hosted zone + queries | ~$1 |
| ACM | SSL certificate | Free |
| CloudWatch | Logs + metrics | ~$5 |
| **Total** | | **~$128/month** |

> Dev/staging can run on free tiers: S3 (free), ECS with 1 task, MongoDB M0 (free), ~$25/month

---

## Quick Start Checklist

- [ ] Create AWS account & configure CLI (`aws configure`)
- [ ] Create S3 bucket for frontend
- [ ] Create ECR repository and push Docker image
- [ ] Create ECS cluster + Fargate service
- [ ] Set up ALB with HTTPS listener
- [ ] Create MongoDB Atlas cluster (or DocumentDB)
- [ ] Configure Route 53 + ACM certificate
- [ ] Set environment variables in ECS task definition
- [ ] Set up CI/CD pipeline (GitHub Actions)
- [ ] Run `mongodump` / `mongorestore` for data migration
- [ ] Test all endpoints against production URL
- [ ] Set up CloudWatch alarms
