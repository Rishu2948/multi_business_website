#!/usr/bin/env bash
# Upload gitignored local .env files to AWS Secrets Manager as JSON secrets.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRETS_DIR="${SCRIPT_DIR}/../secrets"
ENV_NAME="dev"
REGION="${AWS_REGION:-us-east-1}"
DRY_RUN=false
PROJECT_PREFIX="multi-business"

usage() {
  cat <<EOF
Usage: $0 --env dev|prod [--region REGION] [--dry-run]

Reads (gitignored):
  infrastructure/secrets/.env.backend
  infrastructure/secrets/.env.frontend

Creates/updates:
  ${PROJECT_PREFIX}/{env}/backend
  ${PROJECT_PREFIX}/{env}/frontend-build

Requires: aws CLI, jq
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env) ENV_NAME="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 1 ;;
  esac
done

if [[ "$ENV_NAME" != "dev" && "$ENV_NAME" != "prod" ]]; then
  echo "Error: --env must be dev or prod"
  exit 1
fi

BACKEND_FILE="${SECRETS_DIR}/.env.backend"
FRONTEND_FILE="${SECRETS_DIR}/.env.frontend"
BACKEND_EXAMPLE="${SECRETS_DIR}/.env.backend.example"
FRONTEND_EXAMPLE="${SECRETS_DIR}/.env.frontend.example"

for f in "$BACKEND_FILE" "$FRONTEND_FILE"; do
  if [[ ! -f "$f" ]]; then
    echo "Error: missing $f"
    echo "Copy from .env.*.example and fill values:"
    echo "  cp ${SECRETS_DIR}/.env.backend.example ${SECRETS_DIR}/.env.backend"
    echo "  cp ${SECRETS_DIR}/.env.frontend.example ${SECRETS_DIR}/.env.frontend"
    exit 1
  fi
done

env_to_json() {
  local example_file="$1"
  local env_file="$2"
  python3 - "$example_file" "$env_file" <<'PY'
import json, sys
from pathlib import Path

example, env_path = sys.argv[1], Path(sys.argv[2])
values = {}
for line in env_path.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    values[k.strip()] = v

out = {}
for line in Path(example).read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k = line.split("=", 1)[0].strip()
    out[k] = values.get(k, "")

print(json.dumps(out))
PY
}

validate_required() {
  local json="$1"
  shift
  for key in "$@"; do
    val=$(echo "$json" | jq -r --arg k "$key" '.[$k] // empty')
    if [[ -z "$val" ]]; then
      echo "Error: required key '$key' is empty in env file"
      exit 1
    fi
  done
}

echo "Building JSON from local env files..."
BACKEND_JSON=$(env_to_json "$BACKEND_EXAMPLE" "$BACKEND_FILE")
FRONTEND_JSON=$(env_to_json "$FRONTEND_EXAMPLE" "$FRONTEND_FILE")

validate_required "$BACKEND_JSON" MONGO_URL DB_NAME GOOGLE_CLIENT_ID CORS_ORIGINS
validate_required "$FRONTEND_JSON" REACT_APP_BACKEND_URL REACT_APP_GOOGLE_CLIENT_ID

BACKEND_SECRET_NAME="${PROJECT_PREFIX}/${ENV_NAME}/backend"
FRONTEND_SECRET_NAME="${PROJECT_PREFIX}/${ENV_NAME}/frontend-build"

put_secret() {
  local name="$1"
  local json="$2"
  if $DRY_RUN; then
    echo "[dry-run] Would update secret: $name ($(echo "$json" | jq 'keys | length') keys)"
    return
  fi
  if aws secretsmanager describe-secret --secret-id "$name" --region "$REGION" &>/dev/null; then
    aws secretsmanager put-secret-value \
      --secret-id "$name" \
      --secret-string "$json" \
      --region "$REGION"
    echo "Updated secret: $name"
  else
    aws secretsmanager create-secret \
      --name "$name" \
      --description "Multi-business ${name}" \
      --secret-string "$json" \
      --region "$REGION"
    echo "Created secret: $name"
  fi
}

put_secret "$BACKEND_SECRET_NAME" "$BACKEND_JSON"
put_secret "$FRONTEND_SECRET_NAME" "$FRONTEND_JSON"

if ! $DRY_RUN; then
  BACKEND_ARN=$(aws secretsmanager describe-secret \
    --secret-id "$BACKEND_SECRET_NAME" \
    --region "$REGION" \
    --query ARN --output text)
  echo ""
  echo "Backend secret ARN (use for CloudFormation BACKEND_SECRET_ARN):"
  echo "  export BACKEND_SECRET_ARN=${BACKEND_ARN}"
  echo ""
  echo "GitHub Actions FRONTEND_SECRET_NAME:"
  echo "  ${FRONTEND_SECRET_NAME}"
fi
