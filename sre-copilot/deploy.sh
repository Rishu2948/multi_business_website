#!/usr/bin/env bash
# deploy.sh — SRE Copilot Agent full deployment script
#
# Deploys all 7 CloudFormation stacks in dependency order, uploads runbooks
# to S3, triggers a Bedrock Knowledge Base ingestion job, builds the React
# Chat UI, and syncs it to the UI S3 bucket.
#
# Usage:
#   ./deploy.sh [dev|prod]
#
# Environment:
#   ENV          – Target environment name; default "dev".
#                  Must correspond to a file in infra/params/${ENV}.json.
#   AWS_REGION   – AWS region to deploy into; default "us-east-1".
#   AWS_PROFILE  – (optional) Named AWS CLI profile.
#
# Prerequisites:
#   • AWS CLI v2 configured (aws configure, or roles via EC2/ECS task metadata)
#   • Python 3.12 with boto3 installed (for sync_kb.py)
#   • Node.js 20+ with npm (for chat-ui build)
#   • Lambda package already built (run `make package-lambda` first)
#
# Requirements: 5.2, 9.1

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ENV="${1:-${ENV:-dev}}"
REGION="${AWS_REGION:-us-east-1}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARAMS_FILE="${SCRIPT_DIR}/infra/params/${ENV}.json"

# ---------------------------------------------------------------------------
# Validate the params file exists
# ---------------------------------------------------------------------------
if [[ ! -f "${PARAMS_FILE}" ]]; then
    echo "ERROR: Parameter file not found: ${PARAMS_FILE}" >&2
    echo "Available environments: $(ls "${SCRIPT_DIR}/infra/params/" | sed 's/\.json//' | tr '\n' ' ')" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Helper: deploy a single CloudFormation stack
#
# Arguments:
#   $1  Stack name  (e.g., sre-iam-roles)
#   $2  Template path relative to SCRIPT_DIR (e.g., infra/01-iam-roles.yaml)
# ---------------------------------------------------------------------------
deploy_stack() {
    local stack_name="$1"
    local template_file="${SCRIPT_DIR}/$2"

    echo ""
    echo "------------------------------------------------------------"
    echo "  Deploying stack: ${stack_name}"
    echo "  Template       : $2"
    echo "  Environment    : ${ENV}"
    echo "  Region         : ${REGION}"
    echo "------------------------------------------------------------"

    aws cloudformation deploy \
        --stack-name "${stack_name}" \
        --template-file "${template_file}" \
        --parameter-overrides "file://${PARAMS_FILE}" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "${REGION}" \
        --no-fail-on-empty-changeset

    echo "  Stack ${stack_name}: DEPLOYED"
}

# ---------------------------------------------------------------------------
# Helper: retrieve a CloudFormation stack output value by key
# ---------------------------------------------------------------------------
get_stack_output() {
    local stack_name="$1"
    local output_key="$2"

    aws cloudformation describe-stacks \
        --stack-name "${stack_name}" \
        --region "${REGION}" \
        --query "Stacks[0].Outputs[?OutputKey=='${output_key}'].OutputValue" \
        --output text
}

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  SRE Copilot Agent — Full Deployment"
echo "  Environment : ${ENV}"
echo "  Region      : ${REGION}"
echo "  Params file : ${PARAMS_FILE}"
echo "============================================================"

# ---------------------------------------------------------------------------
# Step 1 — Deploy all 7 CloudFormation stacks in dependency order
# ---------------------------------------------------------------------------
echo ""
echo ">>> PHASE 1: CloudFormation stacks"

deploy_stack "sre-iam-roles"     "infra/01-iam-roles.yaml"
deploy_stack "sre-secrets"       "infra/02-secrets.yaml"
deploy_stack "sre-s3-buckets"    "infra/03-s3-buckets.yaml"
deploy_stack "sre-lambda-tools"  "infra/04-lambda-tools.yaml"
deploy_stack "sre-lambda-chat"   "infra/05-lambda-chat.yaml"
deploy_stack "sre-bedrock-kb"    "infra/06-bedrock-kb.yaml"
deploy_stack "sre-bedrock-agent" "infra/07-bedrock-agent.yaml"
deploy_stack "sre-cloudfront"    "infra/08-cloudfront.yaml"

echo ""
echo ">>> All 8 stacks deployed successfully."

# ---------------------------------------------------------------------------
# Step 2 — Retrieve stack outputs needed for post-deploy steps
# ---------------------------------------------------------------------------
echo ""
echo ">>> PHASE 2: Retrieving stack outputs"

KB_BUCKET="$(get_stack_output sre-s3-buckets KnowledgeBaseBucketName)"
UI_BUCKET="$(get_stack_output sre-s3-buckets UiBucketName)"
KB_ID="$(get_stack_output sre-bedrock-kb KnowledgeBaseId)"
DS_ID="$(get_stack_output sre-bedrock-kb DataSourceId)"
AGENT_ID="$(get_stack_output sre-bedrock-agent AgentId)"
AGENT_ALIAS_ID="$(get_stack_output sre-bedrock-agent AgentAliasId)"
CHAT_API_URL="$(get_stack_output sre-lambda-chat ChatApiUrl)"
CF_DISTRIBUTION_ID="$(get_stack_output sre-cloudfront CloudFrontDistributionId)"
UI_URL="$(get_stack_output sre-cloudfront CloudFrontUrl)"

echo "  KB_BUCKET        : ${KB_BUCKET}"
echo "  UI_BUCKET        : ${UI_BUCKET}"
echo "  KB_ID            : ${KB_ID}"
echo "  DS_ID            : ${DS_ID}"
echo "  AGENT_ID         : ${AGENT_ID}"
echo "  AGENT_ALIAS_ID   : ${AGENT_ALIAS_ID}"
echo "  CHAT_API_URL     : ${CHAT_API_URL}"
echo "  CF_DISTRIBUTION  : ${CF_DISTRIBUTION_ID}"
echo "  UI_URL           : ${UI_URL}"

# ---------------------------------------------------------------------------
# Step 3 — Upload runbooks to S3
# ---------------------------------------------------------------------------
echo ""
echo ">>> PHASE 3: Uploading runbooks to s3://${KB_BUCKET}/runbooks/"

KB_BUCKET="${KB_BUCKET}" bash "${SCRIPT_DIR}/scripts/upload_runbooks.sh"

echo "  Runbooks uploaded."

# ---------------------------------------------------------------------------
# Step 4 — Trigger Bedrock Knowledge Base ingestion job
# ---------------------------------------------------------------------------
echo ""
echo ">>> PHASE 4: Triggering Bedrock KB ingestion job (sync_kb.py)"

KB_ID="${KB_ID}" DS_ID="${DS_ID}" AWS_REGION="${REGION}" \
    python3 "${SCRIPT_DIR}/scripts/sync_kb.py"

echo "  KB ingestion job started."

# ---------------------------------------------------------------------------
# Step 5 — Build the React Chat UI and deploy to S3
# ---------------------------------------------------------------------------
echo ""
echo ">>> PHASE 5: Building and deploying React Chat UI"

# Inject the API URL so the Vite build embeds the correct endpoint
export VITE_API_URL="${CHAT_API_URL}"

echo "  Building UI (VITE_API_URL=${CHAT_API_URL}) …"
cd "${SCRIPT_DIR}/chat-ui"
npm ci --silent
npm run build

echo "  Syncing dist/ to s3://${UI_BUCKET}/ …"
aws s3 sync dist/ "s3://${UI_BUCKET}/" \
    --delete \
    --region "${REGION}"

# Invalidate CloudFront cache so SREs get the new build immediately.
# Without this, CloudFront serves stale JS/CSS for up to 24 hours (default TTL).
echo "  Invalidating CloudFront cache (distribution: ${CF_DISTRIBUTION_ID}) …"
INVALIDATION_ID=$(aws cloudfront create-invalidation \
    --distribution-id "${CF_DISTRIBUTION_ID}" \
    --paths "/*" \
    --query "Invalidation.Id" \
    --output text)
echo "  Invalidation created: ${INVALIDATION_ID} (takes ~30–60s to propagate)"

cd "${SCRIPT_DIR}"
echo "  UI deployed and cache invalidated."

# ---------------------------------------------------------------------------
# Post-deploy checklist
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  POST-DEPLOY CHECKLIST"
echo "============================================================"
echo ""
echo "  1. Store Databricks credentials (if not done yet):"
echo "       ./scripts/setup_databricks_secrets.sh \\"
echo "           <DATABRICKS_HOST> <HTTP_PATH> <PAT>"
echo ""
echo "  2. Import notebooks into Databricks Community Edition:"
echo "       - notebooks/04_create_tables.py  (run once — creates all Delta tables)"
echo "       - notebooks/01_backfill.py       (run once — 30-day historical backfill)"
echo "       - notebooks/00_cw_export.py      (schedule hourly)"
echo "       - notebooks/02_bronze_to_silver.py (schedule after 00)"
echo "       - notebooks/03_silver_to_gold.py   (schedule after 02)"
echo ""
echo "  3. Run end-to-end agent test:"
echo "       AGENT_ID=${AGENT_ID} \\"
echo "       AGENT_ALIAS_ID=${AGENT_ALIAS_ID} \\"
echo "       AWS_REGION=${REGION} \\"
echo "       python scripts/test_agent.py"
echo ""
echo "  4. Open the Chat UI in your browser (HTTPS, IP-restricted):"
echo "       ${UI_URL}"
echo ""
echo "     If you see a 403, your IP is not in AllowedCidrIps."
echo "     Update it in infra/params/${ENV}.json and re-run deploy.sh."
echo "     Find your current IP: curl -s https://checkip.amazonaws.com"
echo ""
echo "  5. CloudFormation stack outputs for reference:"
echo "       AGENT_ID      : ${AGENT_ID}"
echo "       AGENT_ALIAS_ID: ${AGENT_ALIAS_ID}"
echo "       CHAT_API_URL  : ${CHAT_API_URL}"
echo "       UI_URL        : http://${UI_URL}"
echo ""
echo "============================================================"
echo "  Deployment complete!"
echo "============================================================"
