#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/docker-compose.staging.yml"
BACKEND_ENV="${ROOT_DIR}/backend/.env.staging"
BACKEND_ENV_EXAMPLE="${ROOT_DIR}/backend/.env.staging.example"
RUN_SMOKE=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Bring up the local staging stack and optionally run the clinician copilot smoke gate.

Options:
  --run-smoke     Run the clinician copilot demo check against staging after startup
  -h, --help      Show this help text
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-smoke)
      RUN_SMOKE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "Missing compose file: ${COMPOSE_FILE}" >&2
  exit 1
fi

if [[ ! -f "${BACKEND_ENV}" ]]; then
  echo "Missing ${BACKEND_ENV}. Copy ${BACKEND_ENV_EXAMPLE} first." >&2
  exit 1
fi

compose_cmd=()
if docker compose version >/dev/null 2>&1; then
  compose_cmd=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  compose_cmd=(docker-compose)
else
  echo "docker compose or docker-compose is required." >&2
  exit 1
fi

if [[ -x "${ROOT_DIR}/backend/.venv/bin/python" ]]; then
  BACKEND_PYTHON="${ROOT_DIR}/backend/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  BACKEND_PYTHON="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  BACKEND_PYTHON="$(command -v python)"
else
  echo "Python is required locally to prepare the staging schema." >&2
  exit 1
fi

wait_for_url() {
  local url="$1"
  local attempts="${2:-30}"
  local sleep_seconds="${3:-2}"
  local attempt=1
  while (( attempt <= attempts )); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep "${sleep_seconds}"
    (( attempt += 1 ))
  done
  return 1
}

echo "==> Starting staging database"
"${compose_cmd[@]}" -f "${COMPOSE_FILE}" up -d db

echo "==> Running staging migrations"
(
  set -a
  source "${BACKEND_ENV}"
  set +a
  cd "${ROOT_DIR}/backend"
  "${BACKEND_PYTHON}" scripts/ensure_schema_ready.py
)

echo "==> Starting staging backend and frontend"
"${compose_cmd[@]}" -f "${COMPOSE_FILE}" up -d backend frontend

echo "==> Waiting for staging health checks"
wait_for_url "http://127.0.0.1:8001/health" 40 3
wait_for_url "http://127.0.0.1:4173/" 40 3

echo "Staging is up:"
echo "  backend:  http://127.0.0.1:8001"
echo "  frontend: http://127.0.0.1:4173"

if (( RUN_SMOKE == 1 )); then
  echo "==> Running clinician copilot smoke against staging"
  "${ROOT_DIR}/scripts/run_clinician_copilot_demo_check.sh" \
    --backend-url "http://127.0.0.1:8001" \
    --frontend-url "http://127.0.0.1:4173"
fi
