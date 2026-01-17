#!/bin/bash
# Script to start MedMemory services

set -e

echo "🚀 Starting MedMemory services..."

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop and try again."
    exit 1
fi

# Start the database
echo "📦 Starting PostgreSQL database..."
cd "$(dirname "$0")"
docker compose -f docker-compose.dev.yml up -d db

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
sleep 5

# Check if database is ready
until docker compose -f docker-compose.dev.yml exec -T db pg_isready -U medmemory -d medmemory > /dev/null 2>&1; do
    echo "   Waiting for database..."
    sleep 2
done

echo "✅ Database is ready!"

# Set environment variables for backend
export DATABASE_URL="postgresql+asyncpg://medmemory:medmemory_dev@localhost:5432/medmemory"
export DEBUG="true"
export JWT_SECRET_KEY="dev-secret-change-me"

echo "🔧 Starting backend..."
cd backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "   Backend PID: $BACKEND_PID"

# Wait a moment for backend to start
sleep 3

# Check if backend is responding
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend is running on http://localhost:8000"
else
    echo "⚠️  Backend may still be starting up..."
fi

echo ""
echo "✅ Services started!"
echo "   - Database: localhost:5432"
echo "   - Backend: http://localhost:8000"
echo "   - Frontend: http://localhost:5174 (should already be running)"
echo ""
echo "To stop services, run: docker compose -f docker-compose.dev.yml down"
