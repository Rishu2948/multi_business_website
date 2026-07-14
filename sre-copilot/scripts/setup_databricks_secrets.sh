#!/usr/bin/env bash
# setup_databricks_secrets.sh
#
# Stores Databricks connection details in AWS Secrets Manager so the
# sre-gold-query-tools Lambda can retrieve them at runtime without any
# credentials being embedded in source code or environment variables.
#
# Usage:
#   ./scripts/setup_databricks_secrets.sh <DATABRICKS_HOST> <HTTP_PATH> <PAT>
#
# Arguments (positional):
#   $1  DATABRICKS_HOST  – Workspace hostname, e.g. dbc-xxxx.cloud.databricks.com
#   $2  HTTP_PATH        – SQL Warehouse HTTP path, e.g. /sql/1.0/warehouses/<id>
#   $3  PAT              – Personal Access Token (never logged, never echoed)
#
# Requirements: 5.2, 9.1
# The script writes the PAT to sre/databricks-pat and the non-secret config
# to sre/databricks-config so the Lambda handler can retrieve both at cold start.
#
# Prerequisites:
#   • AWS CLI v2 configured with credentials that have secretsmanager:PutSecretValue
#     permission on the sre/* prefix.
#   • The placeholder secrets must already exist (created by stack 02-secrets.yaml).

set -euo pipefail

# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------
if [[ $# -ne 3 ]]; then
    echo "ERROR: Expected 3 arguments." >&2
    echo "Usage: $0 <DATABRICKS_HOST> <HTTP_PATH> <PAT>" >&2
    exit 1
fi

DATABRICKS_HOST="${1}"
HTTP_PATH="${2}"
PAT="${3}"

if [[ -z "${DATABRICKS_HOST}" ]]; then
    echo "ERROR: DATABRICKS_HOST must not be empty." >&2
    exit 1
fi

if [[ -z "${HTTP_PATH}" ]]; then
    echo "ERROR: HTTP_PATH must not be empty." >&2
    exit 1
fi

if [[ -z "${PAT}" ]]; then
    echo "ERROR: PAT must not be empty." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Store the PAT in Secrets Manager
# The secret value is the raw token string (no JSON wrapper) so the Lambda
# handler can use it directly as the access_token argument to dbsql.connect().
# ---------------------------------------------------------------------------
echo "Storing Databricks PAT in Secrets Manager (sre/databricks-pat) ..."
aws secretsmanager put-secret-value \
    --secret-id "sre/databricks-pat" \
    --secret-string "${PAT}"

echo "PAT stored successfully."

# ---------------------------------------------------------------------------
# Store the non-secret Databricks config (host + http_path) as a JSON object
# in a separate secret. This keeps all Databricks connection state in
# Secrets Manager, avoiding environment-variable leakage even for non-secret
# values (defence in depth).
# ---------------------------------------------------------------------------
echo "Storing Databricks config in Secrets Manager (sre/databricks-config) ..."
CONFIG_JSON=$(printf '{"host":"%s","http_path":"%s"}' "${DATABRICKS_HOST}" "${HTTP_PATH}")

aws secretsmanager put-secret-value \
    --secret-id "sre/databricks-config" \
    --secret-string "${CONFIG_JSON}"

echo "Config stored successfully."

echo ""
echo "Done. The Lambda function will pick up the new credentials on its next cold start."
echo "To force an immediate refresh, update the Lambda function configuration"
echo "(e.g., change an env var) or wait for the current execution context to expire."
