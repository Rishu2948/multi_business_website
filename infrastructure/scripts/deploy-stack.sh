#!/usr/bin/env bash
# Package nested templates to S3 and deploy the master CloudFormation stack.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFN_DIR="${SCRIPT_DIR}/../cloudformation"
ENV="${ENV:-dev}"
STACK_NAME="${STACK_NAME:-multi-business-${ENV}}"
REGION="${AWS_REGION:-us-east-1}"
S3_BUCKET="${CFN_TEMPLATE_BUCKET:-}"

usage() {
  cat <<EOF
Usage: $0 [--env dev|prod] [--stack-name NAME] [--region REGION]

Requires:
  - AWS CLI configured
  - CFN_TEMPLATE_BUCKET env var (S3 bucket for nested templates), or pass --bucket

Before deploy:
  1. Run sync-secrets-to-aws.sh --env \$ENV
  2. Set BackendSecretArn in parameters file or export BACKEND_SECRET_ARN

Example:
  export CFN_TEMPLATE_BUCKET=my-cfn-templates-bucket
  export BACKEND_SECRET_ARN=arn:aws:secretsmanager:...
  ./deploy-stack.sh --env prod
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env) ENV="$2"; STACK_NAME="multi-business-${ENV}"; shift 2 ;;
    --stack-name) STACK_NAME="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --bucket) S3_BUCKET="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 1 ;;
  esac
done

if [[ -z "$S3_BUCKET" ]]; then
  echo "Error: set CFN_TEMPLATE_BUCKET or pass --bucket"
  exit 1
fi

if [[ -z "${BACKEND_SECRET_ARN:-}" ]]; then
  echo "Error: export BACKEND_SECRET_ARN (from: aws secretsmanager describe-secret --secret-id multi-business/${ENV}/backend)"
  exit 1
fi

PARAMS_FILE="${CFN_DIR}/parameters-${ENV}.json"
if [[ ! -f "$PARAMS_FILE" ]]; then
  echo "Error: missing parameters file: $PARAMS_FILE"
  exit 1
fi

# Update BackendSecretArn in a temp params file
TMP_PARAMS="$(mktemp)"
python3 - <<PY "$PARAMS_FILE" "$TMP_PARAMS" "$BACKEND_SECRET_ARN"
import json, sys
src, dst, arn = sys.argv[1], sys.argv[2], sys.argv[3]
with open(src) as f:
    params = json.load(f)
for p in params:
    if p["ParameterKey"] == "BackendSecretArn":
        p["ParameterValue"] = arn
with open(dst, "w") as f:
    json.dump(params, f, indent=2)
PY

echo "Packaging templates to s3://${S3_BUCKET}/cloudformation/${ENV}/ ..."
aws cloudformation package \
  --template-file "${CFN_DIR}/master.yaml" \
  --s3-bucket "$S3_BUCKET" \
  --s3-prefix "cloudformation/${ENV}" \
  --output-template-file "${CFN_DIR}/packaged-master.yaml" \
  --region "$REGION"

echo "Deploying stack ${STACK_NAME} ..."
aws cloudformation deploy \
  --template-file "${CFN_DIR}/packaged-master.yaml" \
  --stack-name "$STACK_NAME" \
  --parameter-overrides file://"$TMP_PARAMS" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION" \
  --no-fail-on-empty-changeset

rm -f "$TMP_PARAMS"

echo ""
echo "Stack outputs:"
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs' \
  --output table
