#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"
FRONTEND_COMPOSE_FILE="${ROOT_DIR}/docker-compose.local-backend.dev.yml"

BACKEND_BASE_URL="${MEDMEMORY_BASE_URL:-http://localhost:8000}"
FRONTEND_BASE_URL="${PLAYWRIGHT_BASE_URL:-http://localhost:5173}"
TEMPLATE="chart_review"
OUTPUT_JSON="${BACKEND_DIR}/artifacts/clinician_copilot/live_smoke.json"
SKIP_BACKEND=0
SKIP_BROWSER=0
RESTART_FRONTEND=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Run the full clinician copilot demo verification:
  1. backend live smoke
  2. frontend Playwright clinician copilot smoke

Options:
  --template <name>         Copilot template to run (default: ${TEMPLATE})
  --backend-url <url>       Backend base URL (default: ${BACKEND_BASE_URL})
  --frontend-url <url>      Frontend base URL for Playwright (default: ${FRONTEND_BASE_URL})
  --output-json <path>      Backend smoke JSON output path
  --restart-frontend        Restart the local frontend dev service before Playwright
  --skip-backend            Skip backend smoke script
  --skip-browser            Skip Playwright browser smoke
  -h, --help                Show this help text
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --template)
      TEMPLATE="${2:?missing value for --template}"
      shift 2
      ;;
    --backend-url)
      BACKEND_BASE_URL="${2:?missing value for --backend-url}"
      shift 2
      ;;
    --frontend-url)
      FRONTEND_BASE_URL="${2:?missing value for --frontend-url}"
      shift 2
      ;;
    --output-json)
      OUTPUT_JSON="${2:?missing value for --output-json}"
      shift 2
      ;;
    --restart-frontend)
      RESTART_FRONTEND=1
      shift
      ;;
    --skip-backend)
      SKIP_BACKEND=1
      shift
      ;;
    --skip-browser)
      SKIP_BROWSER=1
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

if [[ ! -d "${BACKEND_DIR}" ]]; then
  echo "Backend directory not found: ${BACKEND_DIR}" >&2
  exit 1
fi

if [[ ! -d "${FRONTEND_DIR}" ]]; then
  echo "Frontend directory not found: ${FRONTEND_DIR}" >&2
  exit 1
fi

if [[ -x "${BACKEND_DIR}/.venv/bin/python" ]]; then
  PYTHON_BIN="${BACKEND_DIR}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python)"
else
  echo "Python is required but was not found in PATH." >&2
  exit 1
fi

if ! command -v npx >/dev/null 2>&1; then
  echo "npx is required but was not found in PATH." >&2
  exit 1
fi

if command -v curl >/dev/null 2>&1; then
  maybe_resolve_ipv4_url() {
    local current_url="$1"
    local probe_path="${2:-/}"
    local label="${3:-service}"
    if [[ "${current_url}" != *"localhost"* ]]; then
      printf '%s' "${current_url}"
      return
    fi
    local fallback_url="${current_url/localhost/127.0.0.1}"
    if curl -fsS "${fallback_url%/}${probe_path}" >/dev/null 2>&1; then
      echo "Using IPv4 loopback ${label} URL: ${fallback_url}" >&2
      printf '%s' "${fallback_url}"
      return
    fi
    printf '%s' "${current_url}"
  }

  validate_frontend_url() {
    local current_url="$1"
    local body
    body="$(curl -fsS --max-time 5 "${current_url%/}/")" || return 1
    [[ "${body}" == *'id="root"'* ]]
  }

  wait_for_frontend_url() {
    local current_url="$1"
    local attempts="${2:-20}"
    local sleep_seconds="${3:-2}"
    local attempt=1
    while (( attempt <= attempts )); do
      if validate_frontend_url "${current_url}"; then
        return 0
      fi
      sleep "${sleep_seconds}"
      ((attempt += 1))
    done
    return 1
  }

  BACKEND_BASE_URL="$(maybe_resolve_ipv4_url "${BACKEND_BASE_URL}" "/health" "backend")"
  FRONTEND_BASE_URL="$(maybe_resolve_ipv4_url "${FRONTEND_BASE_URL}" "/" "frontend")"
fi

restart_frontend_service() {
  if [[ "${FRONTEND_BASE_URL}" != "http://localhost:5173" && "${FRONTEND_BASE_URL}" != "http://127.0.0.1:5173" ]]; then
    echo "--restart-frontend only supports the local frontend at http://localhost:5173 or http://127.0.0.1:5173." >&2
    exit 1
  fi
  if [[ ! -f "${FRONTEND_COMPOSE_FILE}" ]]; then
    echo "Frontend compose file not found: ${FRONTEND_COMPOSE_FILE}" >&2
    exit 1
  fi

  local compose_cmd=()
  if docker compose version >/dev/null 2>&1; then
    compose_cmd=(docker compose)
  elif command -v docker-compose >/dev/null 2>&1; then
    compose_cmd=(docker-compose)
  else
    echo "--restart-frontend requires docker compose or docker-compose." >&2
    exit 1
  fi

  echo "==> Restarting frontend dev service"
  "${compose_cmd[@]}" -f "${FRONTEND_COMPOSE_FILE}" up -d frontend
}

if (( SKIP_BACKEND == 0 )); then
  mkdir -p "$(dirname "${OUTPUT_JSON}")"
  echo "==> Running backend clinician copilot smoke"
  "${PYTHON_BIN}" "${BACKEND_DIR}/scripts/run_clinician_copilot_smoke.py" \
    --base-url "${BACKEND_BASE_URL}" \
    --template "${TEMPLATE}" \
    --output-json "${OUTPUT_JSON}"
  echo "Backend smoke artifact: ${OUTPUT_JSON}"
fi

if (( SKIP_BROWSER == 0 )); then
  if (( RESTART_FRONTEND == 1 )); then
    restart_frontend_service
  fi
  if command -v curl >/dev/null 2>&1; then
    if ! wait_for_frontend_url "${FRONTEND_BASE_URL}" 30 2; then
      echo "Frontend check failed at ${FRONTEND_BASE_URL}." >&2
      if (( RESTART_FRONTEND == 0 )); then
        echo "Retry with --restart-frontend or point --frontend-url at the active UI." >&2
      fi
      exit 1
    fi
  else
    echo "curl not found; skipping frontend URL validation before Playwright." >&2
  fi
  echo "==> Running frontend Playwright clinician copilot smoke"
  (
    cd "${FRONTEND_DIR}"
    PLAYWRIGHT_BASE_URL="${FRONTEND_BASE_URL}" \
    E2E_API_BASE_URL="${BACKEND_BASE_URL}" \
    npx playwright test e2e/clinician-copilot.spec.ts --reporter=line
  )
fi

echo "Clinician copilot demo check complete."
