#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"
COMPOSE_FILE="${ROOT_DIR}/docker-compose.local-backend.dev.yml"
ARTIFACT_DIR="${ROOT_DIR}/artifacts/speech_release_gate"
BACKEND_LOG="${ARTIFACT_DIR}/backend.log"
BACKEND_PID_FILE="${ARTIFACT_DIR}/backend.pid"

BACKEND_URL="${MEDMEMORY_BASE_URL:-http://127.0.0.1:8000}"
FRONTEND_URL="${PLAYWRIGHT_BASE_URL:-http://127.0.0.1:5173}"
SPEECH_URL="${SPEECH_SERVICE_BASE_URL:-http://127.0.0.1:8010}"
START_STACK=1
RUN_BROWSER=1
RUN_BACKEND_SMOKE=1
SHUTDOWN_ON_EXIT=0
SPEECH_API_KEY=""

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Run the split speech-service release gate locally:
  1. start db/frontend/speech-service
  2. start backend with SPEECH_SYNTHESIS_BACKEND=http
  3. verify /health and /health/speech
  4. run speech/chat smoke
  5. run Swahili refusal + speech-output browser smokes

Options:
  --compose-file <path>   Compose file to use (default: ${COMPOSE_FILE})
  --artifact-dir <path>   Artifact directory (default: ${ARTIFACT_DIR})
  --backend-url <url>     Backend URL (default: ${BACKEND_URL})
  --frontend-url <url>    Frontend URL (default: ${FRONTEND_URL})
  --speech-url <url>      Speech worker URL (default: ${SPEECH_URL})
  --skip-start            Reuse already-running services
  --skip-browser          Skip Playwright browser smoke tests
  --skip-backend-smoke    Skip backend speech/chat smoke
  --shutdown              Stop compose services on exit
  -h, --help              Show this help text
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --compose-file)
      COMPOSE_FILE="${2:?missing value for --compose-file}"
      shift 2
      ;;
    --artifact-dir)
      ARTIFACT_DIR="${2:?missing value for --artifact-dir}"
      BACKEND_LOG="${ARTIFACT_DIR}/backend.log"
      BACKEND_PID_FILE="${ARTIFACT_DIR}/backend.pid"
      shift 2
      ;;
    --backend-url)
      BACKEND_URL="${2:?missing value for --backend-url}"
      shift 2
      ;;
    --frontend-url)
      FRONTEND_URL="${2:?missing value for --frontend-url}"
      shift 2
      ;;
    --speech-url)
      SPEECH_URL="${2:?missing value for --speech-url}"
      shift 2
      ;;
    --skip-start)
      START_STACK=0
      shift
      ;;
    --skip-browser)
      RUN_BROWSER=0
      shift
      ;;
    --skip-backend-smoke)
      RUN_BACKEND_SMOKE=0
      shift
      ;;
    --shutdown)
      SHUTDOWN_ON_EXIT=1
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

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command not found: $1" >&2
    exit 1
  fi
}

require_cmd docker
require_cmd curl
require_cmd npx

if [[ ! -x "${BACKEND_DIR}/.venv/bin/python" ]]; then
  echo "Missing backend Python at ${BACKEND_DIR}/.venv/bin/python" >&2
  exit 1
fi

if [[ ! -f "${BACKEND_DIR}/.env" ]]; then
  echo "Missing backend env file: ${BACKEND_DIR}/.env" >&2
  exit 1
fi

mkdir -p "${ARTIFACT_DIR}"

set -a
source "${BACKEND_DIR}/.env"
set +a
SPEECH_API_KEY="${SPEECH_SERVICE_INTERNAL_API_KEY:-}"

if [[ -z "${SPEECH_API_KEY}" ]]; then
  echo "SPEECH_SERVICE_INTERNAL_API_KEY must be set in ${BACKEND_DIR}/.env" >&2
  exit 1
fi

backend_pid=""

cleanup() {
  if [[ -n "${backend_pid}" ]] && kill -0 "${backend_pid}" >/dev/null 2>&1; then
    kill "${backend_pid}" >/dev/null 2>&1 || true
    wait "${backend_pid}" 2>/dev/null || true
  fi
  if (( SHUTDOWN_ON_EXIT == 1 )); then
    docker compose -f "${COMPOSE_FILE}" down >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

wait_for_http() {
  local url="$1"
  local label="$2"
  local header="${3:-}"
  for i in {1..45}; do
    if [[ -n "${header}" ]]; then
      if curl -sf -H "${header}" "${url}" >/dev/null; then
        echo "${label} is ready"
        return 0
      fi
    else
      if curl -sf "${url}" >/dev/null; then
        echo "${label} is ready"
        return 0
      fi
    fi
    sleep 2
  done
  echo "${label} did not become ready: ${url}" >&2
  return 1
}

if (( START_STACK == 1 )); then
  if ! docker info >/dev/null 2>&1; then
    echo "Docker daemon is not running." >&2
    exit 1
  fi
  docker compose -f "${COMPOSE_FILE}" up -d db frontend speech-service
fi

wait_for_http "${SPEECH_URL%/}/internal/v1/health" "speech-service" "X-Speech-Service-Key: ${SPEECH_API_KEY}"
wait_for_http "${FRONTEND_URL%/}/" "frontend"

if lsof -n -P -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port 8000 is already in use. Stop the running backend or rerun with --skip-start and a different --backend-url." >&2
  exit 1
fi

(
  cd "${BACKEND_DIR}"
  env \
    SPEECH_SYNTHESIS_BACKEND="http" \
    SPEECH_SYNTHESIS_SERVICE_BASE_URL="${SPEECH_URL}" \
    uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 \
      > "${BACKEND_LOG}" 2>&1 &
  echo $! > "${BACKEND_PID_FILE}"
)
backend_pid="$(cat "${BACKEND_PID_FILE}")"

wait_for_http "${BACKEND_URL%/}/health" "backend"
wait_for_http "${BACKEND_URL%/}/health/speech" "backend speech health"

if (( RUN_BACKEND_SMOKE == 1 )); then
  (
    cd "${BACKEND_DIR}"
    uv run python scripts/run_speech_chat_smoke.py \
      --base-url "${BACKEND_URL}" \
      --audio models/medasr/test_audio.wav \
      --skip-chat \
      --output-json "${ARTIFACT_DIR}/backend_live_smoke.json"
  )
fi

if (( RUN_BROWSER == 1 )); then
  (
    cd "${FRONTEND_DIR}"
    PLAYWRIGHT_BASE_URL="${FRONTEND_URL}" \
    E2E_API_BASE_URL="${BACKEND_URL}" \
    npx playwright test \
      e2e/swahili-refusal-smoke.spec.ts \
      e2e/swahili-speech-output-smoke.spec.ts \
      --workers=1 \
      --reporter=line \
      --output="${ARTIFACT_DIR}/playwright"
  )
fi

echo "Speech-service release gate passed."
echo "Artifacts: ${ARTIFACT_DIR}"
