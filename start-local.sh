#!/bin/bash
# start-local.sh — Start backend + frontend for local development
# Usage: ./start-local.sh

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

echo "🚀 Starting Whisked Words local development environment..."
echo ""

# ── Backend ─────────────────────────────────────────────────────────────────

echo "📦 Setting up backend..."
cd "$BACKEND"

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    echo "  Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate and install deps
source venv/bin/activate
pip install -r requirements.txt -q

echo "  ✅ Backend dependencies installed"
echo ""

# Run migrations
echo "🗃  Running migrations..."
python3 run_migrations.py
echo ""

# Start backend in background
echo "🔧 Starting backend on http://localhost:8000 ..."
uvicorn server:app --reload --port 8000 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"
echo ""

# Wait for backend to be ready
echo "⏳ Waiting for backend to start..."
for i in {1..15}; do
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
        echo "  ✅ Backend is ready!"
        break
    fi
    sleep 1
    echo "  Waiting... ($i/15)"
done

echo ""

# ── Frontend ─────────────────────────────────────────────────────────────────

echo "🎨 Setting up frontend..."
cd "$FRONTEND"

# Install if node_modules missing
if [ ! -d "node_modules" ]; then
    echo "  Installing npm dependencies (this may take a minute)..."
    npm install
fi

echo "  ✅ Frontend dependencies ready"
echo ""
echo "🌐 Starting frontend on http://localhost:3000 ..."
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Backend:   http://localhost:8000"
echo "  Frontend:  http://localhost:3000"
echo "  API Docs:  http://localhost:8000/docs"
echo "  Admin:     http://localhost:3000/admin"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Press Ctrl+C to stop all services."
echo ""

# Trap to kill backend when script exits
trap "echo ''; echo 'Shutting down...'; kill $BACKEND_PID 2>/dev/null; exit 0" INT TERM

# Start frontend (foreground)
npm start
