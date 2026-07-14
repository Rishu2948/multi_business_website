#!/usr/bin/env bash
# deploy.sh — AI Catalog Chatbot full deployment script
#
# Builds and pushes a Docker image for the ai-chatbot service, creates/updates
# the AWS Secrets Manager secret with LLM + service config, and deploys the
# ECS Fargate service (a second task definition alongside the existing backend).
#
# Usage:
#   ./deploy.sh [dev|prod]
#
# Environment variables (override defaults):
#   ENV                   – Target environment; default "dev"
#   AWS_REGION            – AWS region; default "us-east-1"
#   AWS_PROFILE           – (optional) Named AWS CLI profile
#   ECR_REPOSITORY_URI    – Full ECR URI, e.g. 123.dkr.ecr.us-east-1.amazonaws.com/ai-chatbot-prod
#   ECS_CLUSTER           – ECS cluster name (shared with backend)
#   ECS_SERVICE           – ECS service name for the chatbot, e.g. ai-chatbot-prod
#   CHATBOT_SECRET_ARN    – Secrets Manager ARN holding chatbot env vars
#                           (created automatically on first run if absent)
#
# Prerequisites:
#   • AWS CLI v2 configured
#   • Docker daemon running
#   • jq installed
#   • infrastructure/secrets/.env.chatbot file populated (copy from .env.example)
#
# What this script does:
#   Phase 1  – Validate prerequisites
#   Phase 2  – Sync chatbot secrets to AWS Secrets Manager
#   Phase 3  – Build & push Docker image to ECR
#   Phase 4  – Deploy / update ECS Fargate service
#   Phase 5  – Wait for service stability and print a post-deploy checklist

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ENV="${1:-${ENV:-dev}}"
REGION="${AWS_REGION:-us-east-1}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SECRETS_FILE="${PROJECT_ROOT}/infrastructure/secrets/.env.chatbot"
SECRETS_EXAMPLE="${SCRIPT_DIR}/.env.example"
SECRET_NAME="multi-business/${ENV}/chatbot"
IMAGE_TAG="${GITHUB_SHA:-$(git -C "${PROJECT_ROOT}" rev-parse --short HEAD 2>/dev/null || echo "latest")}"

ECR_REPOSITORY_URI="${ECR_REPOSITORY_URI:-}"
ECS_CLUSTER="${ECS_CLUSTER:-multi-business-${ENV}}"
ECS_SERVICE="${ECS_SERVICE:-ai-chatbot-${ENV}}"
TASK_FAMILY="${TASK_FAMILY:-ai-chatbot-${ENV}}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()  { echo ""; echo ">>> $*"; }
info() { echo "    $*"; }
ok()   { echo "    ✓  $*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

require_cmd() {
    command -v "$1" &>/dev/null || fail "'$1' is required but not installed."
}

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  AI Catalog Chatbot — Deployment"
echo "  Environment : ${ENV}"
echo "  Region      : ${REGION}"
echo "  Image tag   : ${IMAGE_TAG}"
echo "============================================================"

# ---------------------------------------------------------------------------
# Phase 1 — Validate prerequisites
# ---------------------------------------------------------------------------
log "PHASE 1: Validating prerequisites"

require_cmd aws
require_cmd docker
require_cmd jq
require_cmd python3

aws sts get-caller-identity --region "${REGION}" --output text --query Account \
    > /dev/null || fail "AWS credentials not configured (run: aws configure)"
ok "AWS credentials valid"

if [[ ! -f "${SECRETS_FILE}" ]]; then
    echo ""
    echo "  Missing secrets file: ${SECRETS_FILE}"
    echo "  Create it from the example:"
    echo "    mkdir -p ${PROJECT_ROOT}/infrastructure/secrets"
    echo "    cp ${SECRETS_EXAMPLE} ${SECRETS_FILE}"
    echo "  Then fill in all required values and re-run deploy.sh."
    fail "Secrets file not found."
fi
ok "Secrets file found: ${SECRETS_FILE}"

# ---------------------------------------------------------------------------
# Phase 2 — Sync chatbot secrets to AWS Secrets Manager
# ---------------------------------------------------------------------------
log "PHASE 2: Syncing chatbot secrets → AWS Secrets Manager (${SECRET_NAME})"

# Convert .env file to JSON, using the .env.example keys as the canonical key list
CHATBOT_SECRET_JSON=$(python3 - "${SECRETS_EXAMPLE}" "${SECRETS_FILE}" <<'PY'
import json, sys
from pathlib import Path

example_path, env_path = Path(sys.argv[1]), Path(sys.argv[2])

# Read actual values
values = {}
for line in env_path.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    values[k.strip()] = v.strip()

# Build output using example keys as canonical set
out = {}
for line in example_path.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k = line.split("=", 1)[0].strip()
    out[k] = values.get(k, "")

print(json.dumps(out))
PY
)

# Validate required keys are non-empty
# LLM_API_KEY is only required for openai/anthropic; bedrock uses IAM role auth.
LLM_PROVIDER_VAL=$(echo "${CHATBOT_SECRET_JSON}" | jq -r '.LLM_PROVIDER // "bedrock"' | tr '[:upper:]' '[:lower:]')

REQUIRED_KEYS=(MONGO_URL DB_NAME LLM_PROVIDER LLM_MODEL CORS_ORIGINS)
if [[ "${LLM_PROVIDER_VAL}" != "bedrock" ]]; then
    REQUIRED_KEYS+=(LLM_API_KEY)
fi

for KEY in "${REQUIRED_KEYS[@]}"; do
    VAL=$(echo "${CHATBOT_SECRET_JSON}" | jq -r --arg k "${KEY}" '.[$k] // empty')
    if [[ -z "${VAL}" ]]; then
        fail "Required key '${KEY}' is empty in ${SECRETS_FILE}"
    fi
done
ok "All required secret keys present (provider: ${LLM_PROVIDER_VAL})"

# Create or update the Secrets Manager secret
if aws secretsmanager describe-secret \
        --secret-id "${SECRET_NAME}" \
        --region "${REGION}" &>/dev/null; then
    aws secretsmanager put-secret-value \
        --secret-id "${SECRET_NAME}" \
        --secret-string "${CHATBOT_SECRET_JSON}" \
        --region "${REGION}" > /dev/null
    ok "Secret updated: ${SECRET_NAME}"
else
    aws secretsmanager create-secret \
        --name "${SECRET_NAME}" \
        --description "AI Catalog Chatbot config for ${ENV}" \
        --secret-string "${CHATBOT_SECRET_JSON}" \
        --region "${REGION}" > /dev/null
    ok "Secret created: ${SECRET_NAME}"
fi

CHATBOT_SECRET_ARN="${CHATBOT_SECRET_ARN:-$(
    aws secretsmanager describe-secret \
        --secret-id "${SECRET_NAME}" \
        --region "${REGION}" \
        --query ARN \
        --output text
)}"
info "Secret ARN: ${CHATBOT_SECRET_ARN}"

# ---------------------------------------------------------------------------
# Phase 3 — Build & push Docker image to ECR
# ---------------------------------------------------------------------------
log "PHASE 3: Building & pushing Docker image"

if [[ -z "${ECR_REPOSITORY_URI}" ]]; then
    # Try to resolve from the existing ECR repository name convention
    ACCOUNT_ID=$(aws sts get-caller-identity \
        --region "${REGION}" --query Account --output text)
    ECR_REPOSITORY_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/ai-chatbot-${ENV}"
    info "ECR_REPOSITORY_URI not set — defaulting to: ${ECR_REPOSITORY_URI}"
fi

# Authenticate Docker with ECR
aws ecr get-login-password --region "${REGION}" \
    | docker login --username AWS --password-stdin "${ECR_REPOSITORY_URI%%/*}"
ok "ECR login successful"

# Ensure the ECR repository exists (idempotent)
REPO_NAME="${ECR_REPOSITORY_URI##*/}"   # strip the registry hostname
aws ecr describe-repositories \
        --repository-names "${REPO_NAME}" \
        --region "${REGION}" &>/dev/null \
    || aws ecr create-repository \
        --repository-name "${REPO_NAME}" \
        --region "${REGION}" \
        --image-scanning-configuration scanOnPush=true \
        --encryption-configuration encryptionType=AES256 \
        > /dev/null
ok "ECR repository ready: ${REPO_NAME}"

# Build image from the Dockerfile inside ai-chatbot/
info "Building image: ${ECR_REPOSITORY_URI}:${IMAGE_TAG}"
docker build \
    --file "${SCRIPT_DIR}/Dockerfile" \
    --tag "${ECR_REPOSITORY_URI}:${IMAGE_TAG}" \
    --tag "${ECR_REPOSITORY_URI}:latest" \
    "${SCRIPT_DIR}"

# Push both tags
docker push "${ECR_REPOSITORY_URI}:${IMAGE_TAG}"
docker push "${ECR_REPOSITORY_URI}:latest"
ok "Image pushed: ${ECR_REPOSITORY_URI}:${IMAGE_TAG}"

# ---------------------------------------------------------------------------
# Phase 4 — Deploy / update ECS Fargate service
# ---------------------------------------------------------------------------
log "PHASE 4: Deploying ECS Fargate service (${ECS_SERVICE})"

# Build a minimal ECS task definition JSON inline.
# In production you would manage this in CloudFormation / CDK; this inline
# approach matches the self-contained style of the sre-copilot deploy.sh.
EXECUTION_ROLE_ARN="${ECS_EXECUTION_ROLE_ARN:-}"
TASK_ROLE_ARN="${ECS_TASK_ROLE_ARN:-}"

# Pull CPU / memory from env or use sensible Fargate defaults
TASK_CPU="${TASK_CPU:-512}"
TASK_MEMORY="${TASK_MEMORY:-1024}"
CONTAINER_PORT="${CONTAINER_PORT:-8001}"

# Read PORT from the secret JSON (defaults to 8001 if absent)
CHATBOT_PORT=$(echo "${CHATBOT_SECRET_JSON}" | jq -r '.PORT // "8001"')

# Build log group name
LOG_GROUP="/ecs/ai-chatbot-${ENV}"

# Ensure the CloudWatch log group exists (idempotent)
aws logs create-log-group \
    --log-group-name "${LOG_GROUP}" \
    --region "${REGION}" 2>/dev/null || true
ok "CloudWatch log group ready: ${LOG_GROUP}"

# Build the container definition JSON
# LLM_API_KEY is only injected when not using Bedrock (Bedrock uses IAM auth)
LLM_PROVIDER_FOR_TASK=$(echo "${CHATBOT_SECRET_JSON}" | jq -r '.LLM_PROVIDER // "bedrock"' | tr '[:upper:]' '[:lower:]')

CONTAINER_DEF=$(python3 - <<PY
import json

use_api_key = "${LLM_PROVIDER_FOR_TASK}" not in ("bedrock",)

secret_keys = [
    "MONGO_URL", "DB_NAME",
    "LLM_PROVIDER", "LLM_MODEL", "LLM_TIMEOUT_SECONDS",
    "CORS_ORIGINS", "PORT", "AWS_REGION",
]
if use_api_key:
    secret_keys.insert(4, "LLM_API_KEY")

defn = {
    "name": "ai-chatbot",
    "image": "${ECR_REPOSITORY_URI}:${IMAGE_TAG}",
    "essential": True,
    "portMappings": [
        {"containerPort": int("${CHATBOT_PORT}"), "protocol": "tcp"}
    ],
    "secrets": [
        {"name": k, "valueFrom": "${CHATBOT_SECRET_ARN}:{}::".format(k)}
        for k in secret_keys
    ],
    "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
            "awslogs-group":         "${LOG_GROUP}",
            "awslogs-region":        "${REGION}",
            "awslogs-stream-prefix": "ai-chatbot"
        }
    },
    "healthCheck": {
        "command":     ["CMD-SHELL", "curl -sf http://localhost:${CHATBOT_PORT}/chat/health || exit 1"],
        "interval":    30,
        "timeout":     5,
        "retries":     3,
        "startPeriod": 60
    }
}
print(json.dumps([defn]))
PY
)

# Register the new task definition revision
REGISTER_ARGS=(
    --family "${TASK_FAMILY}"
    --network-mode "awsvpc"
    --requires-compatibilities FARGATE
    --cpu "${TASK_CPU}"
    --memory "${TASK_MEMORY}"
    --container-definitions "${CONTAINER_DEF}"
    --region "${REGION}"
)
[[ -n "${EXECUTION_ROLE_ARN}" ]] && REGISTER_ARGS+=(--execution-role-arn "${EXECUTION_ROLE_ARN}")
[[ -n "${TASK_ROLE_ARN}" ]]      && REGISTER_ARGS+=(--task-role-arn "${TASK_ROLE_ARN}")

NEW_TASK_DEF_ARN=$(aws ecs register-task-definition "${REGISTER_ARGS[@]}" \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)
ok "Task definition registered: ${NEW_TASK_DEF_ARN}"

# Update the ECS service (or print instructions if the service doesn't exist yet)
if aws ecs describe-services \
        --cluster "${ECS_CLUSTER}" \
        --services "${ECS_SERVICE}" \
        --region "${REGION}" \
        --query 'services[0].status' \
        --output text 2>/dev/null | grep -q "ACTIVE"; then

    aws ecs update-service \
        --cluster "${ECS_CLUSTER}" \
        --service "${ECS_SERVICE}" \
        --task-definition "${NEW_TASK_DEF_ARN}" \
        --force-new-deployment \
        --region "${REGION}" \
        --query 'service.serviceName' \
        --output text > /dev/null
    ok "ECS service update triggered: ${ECS_SERVICE}"
else
    echo ""
    echo "  ⚠  ECS service '${ECS_SERVICE}' not found in cluster '${ECS_CLUSTER}'."
    echo "  Create it once with (adjust subnet/sg IDs from your VPC):"
    echo ""
    echo "    aws ecs create-service \\"
    echo "      --cluster ${ECS_CLUSTER} \\"
    echo "      --service-name ${ECS_SERVICE} \\"
    echo "      --task-definition ${NEW_TASK_DEF_ARN} \\"
    echo "      --desired-count 1 \\"
    echo "      --launch-type FARGATE \\"
    echo "      --network-configuration 'awsvpcConfiguration={subnets=[<SUBNET_ID>],securityGroups=[<SG_ID>],assignPublicIp=ENABLED}' \\"
    echo "      --region ${REGION}"
    echo ""
    echo "  Then update CHATBOT_SERVICE_URL in the backend's Secrets Manager secret to"
    echo "  point at this service's private IP or load-balancer DNS."
fi

# ---------------------------------------------------------------------------
# Phase 5 — Wait for stability
# ---------------------------------------------------------------------------
log "PHASE 5: Waiting for ECS service to stabilise (timeout: 5 min)"

if aws ecs describe-services \
        --cluster "${ECS_CLUSTER}" \
        --services "${ECS_SERVICE}" \
        --region "${REGION}" \
        --query 'services[0].status' \
        --output text 2>/dev/null | grep -q "ACTIVE"; then

    aws ecs wait services-stable \
        --cluster "${ECS_CLUSTER}" \
        --services "${ECS_SERVICE}" \
        --region "${REGION}" \
    && ok "Service is stable." \
    || echo "  ⚠  Service did not stabilise within the wait window. Check ECS console."
fi

# ---------------------------------------------------------------------------
# Post-deploy checklist
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  POST-DEPLOY CHECKLIST"
echo "============================================================"
echo ""
echo "  1. Verify the health endpoint:"
echo "       curl -s http://<ALB_OR_TASK_IP>:${CHATBOT_PORT}/chat/health"
echo "       Expected: {\"status\": \"ok\"}"
echo ""
echo "  2. If using LLM_PROVIDER=bedrock, ensure the ECS task role has:"
echo "       bedrock:InvokeModel on arn:aws:bedrock:${REGION}::foundation-model/${LLM_MODEL:-anthropic.claude-3-haiku-20240307-v1:0}"
echo "     Example IAM policy snippet:"
echo "       {"
echo "         \"Effect\": \"Allow\","
echo "         \"Action\": \"bedrock:InvokeModel\","
echo "         \"Resource\": \"arn:aws:bedrock:${REGION}::foundation-model/*\""
echo "       }"
echo "     Also verify the model is enabled in Bedrock Model Access console:"
echo "       https://console.aws.amazon.com/bedrock/home?region=${REGION}#/modelaccess"
echo ""
echo "  3. Update the backend Secrets Manager secret to point at this service:"
echo "       CHATBOT_SERVICE_URL=http://<CHATBOT_PRIVATE_IP_OR_ALB>:${CHATBOT_PORT}"
echo "       aws secretsmanager put-secret-value \\"
echo "         --secret-id multi-business/${ENV}/backend \\"
echo "         --secret-string '{...existing keys..., \"CHATBOT_SERVICE_URL\": \"http://...\"}'"
echo "       Then redeploy the backend ECS service to pick up the new env var."
echo ""
echo "  3. Ensure MongoDB Atlas Network Access allows the chatbot ECS task IP."
echo ""
echo "  4. Set REACT_APP_CHATBOT_URL in the frontend build secrets:"
echo "       aws secretsmanager put-secret-value \\"
echo "         --secret-id multi-business/${ENV}/frontend-build \\"
echo "         --secret-string '{...existing keys..., \"REACT_APP_CHATBOT_URL\": \"https://api.yourdomain.com/chatbot\"}'"
echo "       Then redeploy the frontend (run the existing deploy workflow)."
echo ""
echo "  5. Test a full chat round-trip:"
echo "       curl -s -X POST http://<CHATBOT_URL>/chat/message \\"
echo "         -H 'Content-Type: application/json' \\"
echo "         -H 'Authorization: Bearer <SESSION_TOKEN>' \\"
echo "         -d '{\"business_id\": \"<BIZ_ID>\", \"message\": \"show me cakes\"}'"
echo ""
echo "  6. ECS task definition ARN:"
echo "       ${NEW_TASK_DEF_ARN}"
echo ""
echo "  7. Secrets Manager ARN:"
echo "       ${CHATBOT_SECRET_ARN}"
echo ""
echo "============================================================"
echo "  Deployment complete! (ENV=${ENV}, image=${IMAGE_TAG})"
echo "============================================================"
