#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-dev}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ROOT_DIR}/backend/.env"
LOG_FILE="${ROOT_DIR}/backend-dev.log"
PID_FILE="${ROOT_DIR}/.hybrid-backend.pid"
BACKEND_RELOAD="${HYBRID_BACKEND_RELOAD:-0}"
DB_READY_TIMEOUT_SECONDS="${HYBRID_DB_READY_TIMEOUT_SECONDS:-180}"
BACKEND_READY_TIMEOUT_SECONDS="${HYBRID_BACKEND_READY_TIMEOUT_SECONDS:-180}"
BACKEND_START_ATTEMPTS="${HYBRID_BACKEND_START_ATTEMPTS:-3}"

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

is_truthy() {
  local value="$1"
  value="$(printf '%s' "${value}" | tr '[:upper:]' '[:lower:]')"
  case "${value}" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

has_running_backend_container() {
  local pattern='^medmemory-backend(-dev)?$'
  if command -v rg >/dev/null 2>&1; then
    docker ps --format '{{.Names}}' | rg -q "${pattern}"
  else
    docker ps --format '{{.Names}}' | grep -Eq "${pattern}"
  fi
}

wait_for_service_ready() {
  local service="$1"
  local timeout_seconds="$2"
  local container_id
  local elapsed=0

  container_id="$(docker compose -f "${COMPOSE_FILE}" ps -q "${service}" 2>/dev/null || true)"
  if [[ -z "${container_id}" ]]; then
    echo "Service '${service}' was not found in compose stack."
    return 1
  fi

  while (( elapsed < timeout_seconds )); do
    local state
    state="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${container_id}" 2>/dev/null || true)"
    if [[ "${state}" == "healthy" || "${state}" == "running" ]]; then
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done

  return 1
}

if lsof -n -P -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port 8000 is already in use. Stop the existing process before starting the local backend."
  echo "Details:"
  lsof -n -P -iTCP:8000 -sTCP:LISTEN || true
  exit 1
fi

if has_running_backend_container; then
  echo "A backend container is running on port 8000. Stop it before starting the local backend."
  echo "Tip: docker stop medmemory-backend-dev medmemory-backend"
  exit 1
fi

docker compose -f "${COMPOSE_FILE}" up -d
if ! wait_for_service_ready "db" "${DB_READY_TIMEOUT_SECONDS}"; then
  echo "Database service did not become ready within ${DB_READY_TIMEOUT_SECONDS}s."
  echo "Check: docker compose -f ${COMPOSE_FILE} ps"
  exit 1
fi

if [[ -f "${PID_FILE}" ]]; then
  EXISTING_PID="$(cat "${PID_FILE}")"
  if ! kill -0 "${EXISTING_PID}" 2>/dev/null; then
    rm -f "${PID_FILE}"
  fi
fi

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

start_backend() {
  local mode="$1"
  (
    cd "${ROOT_DIR}/backend"
    set -a
    source "${ENV_FILE}"
    set +a
    if [[ "${mode}" == "reload" ]]; then
      nohup "${UVICORN_BIN}" app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir "${ROOT_DIR}/backend" > "${LOG_FILE}" 2>&1 &
    else
      nohup "${UVICORN_BIN}" app.main:app --host 0.0.0.0 --port 8000 > "${LOG_FILE}" 2>&1 &
    fi
    echo $! > "${PID_FILE}"
  )
}

wait_for_backend_ready() {
  local elapsed=0
  while (( elapsed < BACKEND_READY_TIMEOUT_SECONDS )); do
    if [[ ! -f "${PID_FILE}" ]]; then
      return 1
    fi
    local pid
    pid="$(cat "${PID_FILE}")"
    if ! kill -0 "${pid}" 2>/dev/null; then
      return 1
    fi
    if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  return 1
}

BACKEND_MODE="no-reload"
if [[ "${MODE}" == "dev" ]] && is_truthy "${BACKEND_RELOAD}"; then
  BACKEND_MODE="reload"
fi

echo "Starting local backend in ${BACKEND_MODE} mode..."

attempt=1
started=0
while (( attempt <= BACKEND_START_ATTEMPTS )); do
  start_backend "${BACKEND_MODE}"
  if wait_for_backend_ready; then
    started=1
    break
  fi

  if [[ -f "${PID_FILE}" ]]; then
    BACKEND_PID="$(cat "${PID_FILE}")"
    kill "${BACKEND_PID}" 2>/dev/null || true
  fi
  rm -f "${PID_FILE}"

  echo "Backend start attempt ${attempt}/${BACKEND_START_ATTEMPTS} failed."
  if [[ "${BACKEND_MODE}" == "reload" ]]; then
    echo "Falling back to no-reload mode for stability."
    BACKEND_MODE="no-reload"
  fi
  attempt=$((attempt + 1))
  sleep 2
done

if (( started == 0 )); then
  echo "Local backend failed to start."
  echo "Check logs: ${LOG_FILE}"
  exit 1
fi

echo "Hybrid stack running."
echo "Frontend: http://localhost:5173"
echo "Backend:  http://localhost:8000"
echo "Logs:     ${LOG_FILE}"
