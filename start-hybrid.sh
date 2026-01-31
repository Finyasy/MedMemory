#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-dev}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ROOT_DIR}/backend/.env"
LOG_FILE="${ROOT_DIR}/backend-dev.log"
PID_FILE="${ROOT_DIR}/.hybrid-backend.pid"

if [[ "${MODE}" == "dev" ]]; then
  COMPOSE_FILE="${ROOT_DIR}/docker-compose.local-backend.dev.yml"
elif [[ "${MODE}" == "prod" ]]; then
  COMPOSE_FILE="${ROOT_DIR}/docker-compose.local-backend.yml"
  LOG_FILE="${ROOT_DIR}/backend-prod.log"
else
  echo "Usage: $0 [dev|prod]"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required but was not found in PATH."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not running. Start Docker Desktop and try again."
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing env file: ${ENV_FILE}"
  exit 1
fi

if lsof -n -P -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port 8000 is already in use. Stop the existing process before starting the local backend."
  echo "Details:"
  lsof -n -P -iTCP:8000 -sTCP:LISTEN || true
  exit 1
fi

if docker ps --format '{{.Names}}' | rg -q '^medmemory-backend(-dev)?$'; then
  echo "A backend container is running on port 8000. Stop it before starting the local backend."
  echo "Tip: docker stop medmemory-backend-dev medmemory-backend"
  exit 1
fi

docker compose -f "${COMPOSE_FILE}" up -d

if [[ -f "${PID_FILE}" ]]; then
  EXISTING_PID="$(cat "${PID_FILE}")"
  if kill -0 "${EXISTING_PID}" 2>/dev/null; then
    echo "Local backend already running (PID ${EXISTING_PID})."
    exit 0
  fi
fi

UVICORN_BIN="${ROOT_DIR}/backend/.venv/bin/uvicorn"
if [[ ! -x "${UVICORN_BIN}" ]]; then
  echo "Missing backend virtualenv at ${UVICORN_BIN}."
  echo "Run: cd backend && uv sync"
  exit 1
fi

(
  cd "${ROOT_DIR}/backend"
  set -a
  source "${ENV_FILE}"
  set +a
  nohup "${UVICORN_BIN}" app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir "${ROOT_DIR}/backend" > "${LOG_FILE}" 2>&1 &
  echo $! > "${PID_FILE}"
)

echo "Hybrid stack running."
echo "Frontend: http://localhost:5173"
echo "Backend:  http://localhost:8000"
echo "Logs:     ${LOG_FILE}"
