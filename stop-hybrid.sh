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

if [[ -f "${PID_FILE}" ]]; then
  PID="$(cat "${PID_FILE}")"
  if kill -0 "${PID}" 2>/dev/null; then
    kill "${PID}"
    echo "Stopped local backend (PID ${PID})."
  fi
  rm -f "${PID_FILE}"
fi

docker compose -f "${COMPOSE_FILE}" down
echo "Hybrid stack stopped."
