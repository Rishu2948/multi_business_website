#!/usr/bin/env bash
# Import MongoDB Atlas database into local MongoDB.
#
# Usage:
#   cd backend
#   ATLAS_MONGO_URL='mongodb+srv://user:pass@cluster.mongodb.net/?appName=Cluster0' \
#     ./scripts/import_atlas_to_local.sh
#
# Optional env vars:
#   DB_NAME=multi_business          (default: multi_business)
#   LOCAL_MONGO_URL=mongodb://localhost:27017
#   DUMP_DIR=./mongo-dump           (temporary dump folder)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

DB_NAME="${DB_NAME:-multi_business}"
LOCAL_MONGO_URL="${LOCAL_MONGO_URL:-mongodb://localhost:27017}"
DUMP_DIR="${DUMP_DIR:-${BACKEND_DIR}/mongo-dump}"

if [[ -z "${ATLAS_MONGO_URL:-}" ]]; then
  echo "ERROR: Set ATLAS_MONGO_URL to your Atlas connection string."
  echo ""
  echo "Example:"
  echo "  ATLAS_MONGO_URL='mongodb+srv://user:pass@cluster.mongodb.net/?appName=Cluster0' \\"
  echo "    ./scripts/import_atlas_to_local.sh"
  exit 1
fi

for cmd in mongodump mongorestore; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: '$cmd' not found. Install MongoDB Database Tools:"
    echo "  brew install mongodb-database-tools"
    exit 1
  fi
done

if ! lsof -i :27017 >/dev/null 2>&1; then
  echo "ERROR: Local MongoDB is not listening on port 27017."
  echo "Start it with: brew services start mongodb-community"
  exit 1
fi

echo "==> Dropping local database '${DB_NAME}'..."
if command -v mongosh >/dev/null 2>&1; then
  mongosh "${LOCAL_MONGO_URL}/${DB_NAME}" --quiet --eval "db.dropDatabase()"
elif python3 -c "import pymongo" >/dev/null 2>&1; then
  python3 - <<PY
from pymongo import MongoClient
client = MongoClient("${LOCAL_MONGO_URL}")
client.drop_database("${DB_NAME}")
client.close()
print("Dropped database: ${DB_NAME}")
PY
else
  echo "WARNING: mongosh/pymongo not found; restore will use --drop per collection only."
fi

echo "==> Dumping '${DB_NAME}' from Atlas..."
rm -rf "${DUMP_DIR}"
mkdir -p "${DUMP_DIR}"

mongodump \
  --uri="${ATLAS_MONGO_URL}" \
  --db="${DB_NAME}" \
  --out="${DUMP_DIR}"

echo "==> Restoring '${DB_NAME}' to local MongoDB (${LOCAL_MONGO_URL})..."
mongorestore \
  --uri="${LOCAL_MONGO_URL}" \
  --db="${DB_NAME}" \
  --drop \
  "${DUMP_DIR}/${DB_NAME}"

echo ""
echo "Done. Local database '${DB_NAME}' now mirrors Atlas."
echo "Ensure backend/.env uses:"
echo "  MONGO_URL=${LOCAL_MONGO_URL}"
echo "  DB_NAME=${DB_NAME}"
echo ""
echo "Dump files kept at: ${DUMP_DIR}"
echo "Delete them when finished: rm -rf ${DUMP_DIR}"
