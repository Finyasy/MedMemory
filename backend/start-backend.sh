#!/bin/bash
# Backend startup script with auto-restart

cd "$(dirname "$0")"

# Kill any existing backend on port 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null
sleep 2

# Start backend with auto-reload
echo "Starting backend on http://localhost:8000"
echo "Press Ctrl+C to stop"
echo ""

uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
