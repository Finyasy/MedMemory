#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-dev}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="${ROOT_DIR}/.hybrid-backend.pid"

if [[ "${MODE}" == "dev" ]]; then
  COMPOSE_FILE="${ROOT_DIR}/docker-compose.local-backend.dev.yml"
elif [[ "${MODE}" == "prod" ]]; then
  COMPOSE_FILE="${ROOT_DIR}/docker-compose.local-backend.yml"
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

echo "Docker services:"
docker compose -f "${COMPOSE_FILE}" ps

echo
if [[ -f "${PID_FILE}" ]]; then
  PID="$(cat "${PID_FILE}")"
  if kill -0 "${PID}" 2>/dev/null; then
    echo "Local backend: running (PID ${PID})"
  else
    echo "Local backend: not running (stale PID ${PID})"
  fi
else
  echo "Local backend: not running"
fi

if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
  echo "Backend health: healthy (GET /health)"
else
  echo "Backend health: unreachable (GET /health failed)"
fi
