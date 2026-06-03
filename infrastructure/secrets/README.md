# Secrets (AWS Secrets Manager)

Application secrets are **not** stored in git. Use local gitignored files and sync to AWS.

## Setup

1. Copy templates:

```bash
cp infrastructure/secrets/.env.backend.example infrastructure/secrets/.env.backend
cp infrastructure/secrets/.env.frontend.example infrastructure/secrets/.env.frontend
```

2. Fill values (MongoDB Atlas connection string, Google OAuth, Stripe, etc.).

3. Upload to AWS:

```bash
chmod +x infrastructure/scripts/sync-secrets-to-aws.sh
./infrastructure/scripts/sync-secrets-to-aws.sh --env prod --region us-east-1
```

4. Export the printed `BACKEND_SECRET_ARN` for CloudFormation deploy.

## Secret names

| Environment | Backend | Frontend build |
|-------------|---------|----------------|
| dev | `multi-business/dev/backend` | `multi-business/dev/frontend-build` |
| prod | `multi-business/prod/backend` | `multi-business/prod/frontend-build` |

ECS reads the backend secret at runtime. GitHub Actions reads the frontend-build secret when running `yarn build`.

## Local development

Use `backend/.env` with the same keys as `.env.backend.example`. Set `DEFAULT_NEW_USER_ROLE=super_admin` only for local testing.
