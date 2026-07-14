#!/usr/bin/env bash
# upload_runbooks.sh
#
# Syncs the local runbooks/ directory to the Bedrock Knowledge Base S3 bucket
# so that runbook documents are available for the next KB data source sync.
#
# Usage:
#   KB_BUCKET=sre-copilot-kb-123456789012 ./scripts/upload_runbooks.sh
#
#   or export the variable before calling:
#   export KB_BUCKET=sre-copilot-kb-123456789012
#   ./scripts/upload_runbooks.sh
#
# Environment variables:
#   KB_BUCKET  (required) – Name of the S3 bucket that backs the Bedrock KB.
#                           Created by stack 03-s3-buckets; exported as
#                           KnowledgeBaseBucketName.
#
# After this script completes, run scripts/sync_kb.py to trigger a Bedrock
# data source ingestion job so the newly uploaded documents are indexed.
#
# Requirements: 5.2, 9.1

set -euo pipefail

# ---------------------------------------------------------------------------
# Validate required environment variable
# ---------------------------------------------------------------------------
if [[ -z "${KB_BUCKET:-}" ]]; then
    echo "ERROR: KB_BUCKET environment variable is not set." >&2
    echo "Set it to the Knowledge Base S3 bucket name, e.g.:" >&2
    echo "  export KB_BUCKET=sre-copilot-kb-\$(aws sts get-caller-identity --query Account --output text)" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Resolve the runbooks/ directory relative to the repo root.
# The script can be invoked from any working directory.
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUNBOOKS_DIR="${REPO_ROOT}/runbooks"

if [[ ! -d "${RUNBOOKS_DIR}" ]]; then
    echo "ERROR: runbooks/ directory not found at ${RUNBOOKS_DIR}" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Count the documents to be synced for informational output
# ---------------------------------------------------------------------------
DOC_COUNT=$(find "${RUNBOOKS_DIR}" -type f | wc -l | tr -d '[:space:]')
echo "Syncing ${DOC_COUNT} file(s) from ${RUNBOOKS_DIR} to s3://${KB_BUCKET}/runbooks/ ..."

# ---------------------------------------------------------------------------
# Sync runbooks to S3
# --delete removes objects in S3 that no longer exist locally so the KB
# index stays consistent with the local runbooks directory.
# ---------------------------------------------------------------------------
aws s3 sync "${RUNBOOKS_DIR}/" "s3://${KB_BUCKET}/runbooks/" \
    --delete \
    --exclude ".gitkeep" \
    --exclude ".DS_Store"

echo ""
echo "Sync complete. Run scripts/sync_kb.py to trigger a Bedrock KB ingestion job:"
echo "  python scripts/sync_kb.py"
