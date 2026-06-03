# AWS Infrastructure

Deploys the multi-business platform:

- **Backend:** ECS Fargate behind ALB (port 8001)
- **Frontend:** S3 + CloudFront
- **Database:** MongoDB Atlas M0 (manual setup)
- **Secrets:** AWS Secrets Manager (sync script, not git)

## Prerequisites

- AWS CLI, `jq`, Docker
- AWS account with permissions for CloudFormation, ECS, ECR, S3, CloudFront, Secrets Manager, IAM
- S3 bucket for packaged CloudFormation templates (e.g. `my-company-cfn-templates`)
- GitHub repo with OIDC deploy role (see below)

## 1. MongoDB Atlas M0

1. Sign up at [MongoDB Atlas](https://www.mongodb.com/cloud/atlas).
2. Create a **free M0** cluster in **AWS N. Virginia (`us-east-1`)** on Atlas (matches your AWS region).
3. **Database Access:** create a user with read/write on your database.
4. **Network Access:** allow your ECS egress IP, or `0.0.0.0/0` temporarily for first deploy (tighten later).
5. **Connect → Drivers:** copy the `mongodb+srv://...` connection string.
6. Put `MONGO_URL` and `DB_NAME` in `infrastructure/secrets/.env.backend`.

### Seed production data (once)

```bash
# Use same values as .env.backend locally
export MONGO_URL='mongodb+srv://...'
export DB_NAME='your_db_name'
cd backend && python seed_data.py
```

## 2. Secrets (no git)

See [secrets/README.md](secrets/README.md).

```bash
./infrastructure/scripts/sync-secrets-to-aws.sh --env prod
export BACKEND_SECRET_ARN='arn:aws:secretsmanager:...'  # printed by script
```

Set `CORS_ORIGINS` to your CloudFront URL (and custom domain when ready).  
Set `REACT_APP_BACKEND_URL` in `.env.frontend` to `http://<ALB_DNS>` or `https://api.yourdomain.com`.

## 3. Deploy CloudFormation

```bash
export CFN_TEMPLATE_BUCKET=your-cfn-templates-bucket
export BACKEND_SECRET_ARN=arn:aws:secretsmanager:...
chmod +x infrastructure/scripts/deploy-stack.sh
./infrastructure/scripts/deploy-stack.sh --env prod --region us-east-1
```

Note stack outputs: `EcrRepositoryUri`, `EcsClusterName`, `EcsServiceName`, `FrontendBucketName`, `CloudFrontDistributionId`, `AlbDnsName`.

## 4. First Docker image

After ECR exists:

```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ACCOUNT.dkr.ecr.us-east-1.amazonaws.com
docker build -t multi-business-api .
docker tag multi-business-api:latest ECR_URI:latest
docker push ECR_URI:latest
aws ecs update-service --cluster CLUSTER --service SERVICE --force-new-deployment
```

Or push to `main` after GitHub Actions is configured.

## 5. GitHub Actions secrets

Configure in **Settings → Secrets and variables → Actions** (no app API keys here):

| Secret | Example |
|--------|---------|
| `AWS_ROLE_ARN` | IAM role for OIDC |
| `AWS_REGION` | `us-east-1` |
| `ECR_REPOSITORY_URI` | `123.dkr.ecr.us-east-1.amazonaws.com/multi-business-prod-api` |
| `ECS_CLUSTER` | `multi-business-prod` |
| `ECS_SERVICE` | `multi-business-prod-api` |
| `S3_BUCKET` | from stack output |
| `CLOUDFRONT_DISTRIBUTION_ID` | from stack output |
| `FRONTEND_SECRET_NAME` | `multi-business/prod/frontend-build` |

### GitHub OIDC trust (summary)

1. Create IAM OIDC identity provider for `token.actions.githubusercontent.com`.
2. Create role `github-deploy-multi-business` with trust policy scoped to your repo.
3. Attach policies: ECR push, ECS update, S3 put on frontend bucket, CloudFront invalidation, `secretsmanager:GetSecretValue` on `multi-business/*/frontend-build`.

Example trust policy condition:

```json
"Condition": {
  "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
  "StringLike": { "token.actions.githubusercontent.com:sub": "repo:YOUR_ORG/multi_business_website:*" }
}
```

## 6. Verify

- `curl http://<ALB_DNS>/api/health` → `{"status":"ok"}`
- Open CloudFront URL → login with Google OAuth
- Confirm Atlas shows connections from ECS tasks

## File layout

```
infrastructure/
  cloudformation/   # network, backend-ecs, frontend-cdn, master
  scripts/          # deploy-stack.sh, sync-secrets-to-aws.sh
  secrets/          # .env.*.example (committed), .env.* (gitignored)
```
