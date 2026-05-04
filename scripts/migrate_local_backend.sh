#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
COMPOSE_FILE="${ROOT_DIR}/docker-compose.local-backend.dev.yml"
DB_CONTAINER_NAME="medmemory-db-local-dev"
DB_WAIT_SECONDS="${DB_WAIT_SECONDS:-180}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required but not found in PATH."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not running. Start Docker Desktop and re-run."
  exit 1
fi

if [[ ! -x "${BACKEND_DIR}/.venv/bin/alembic" ]]; then
  echo "Missing backend virtualenv Alembic binary at ${BACKEND_DIR}/.venv/bin/alembic."
  echo "Run: cd ${BACKEND_DIR} && uv sync"
  exit 1
fi

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "Compose file not found: ${COMPOSE_FILE}"
  exit 1
fi

echo "Starting local PostgreSQL (dev compose)..."
docker compose -f "${COMPOSE_FILE}" up -d db >/dev/null

echo "Waiting for PostgreSQL health..."
elapsed=0
while (( elapsed < DB_WAIT_SECONDS )); do
  health="$(docker inspect -f '{{.State.Health.Status}}' "${DB_CONTAINER_NAME}" 2>/dev/null || true)"
  if [[ "${health}" == "healthy" ]]; then
    break
  fi
  sleep 2
  elapsed=$((elapsed + 2))
done

if [[ "${health:-}" != "healthy" ]]; then
  echo "PostgreSQL did not become healthy within ${DB_WAIT_SECONDS}s."
  docker compose -f "${COMPOSE_FILE}" ps
  exit 1
fi

echo "Running Alembic migrations..."
(
  cd "${BACKEND_DIR}"
  PYTHONPATH=. ./.venv/bin/alembic upgrade head
)

echo "Current migration revision:"
(
  cd "${BACKEND_DIR}"
  PYTHONPATH=. ./.venv/bin/alembic current
)

echo "Migration workflow complete."
