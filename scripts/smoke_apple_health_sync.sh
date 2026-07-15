#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000/api/v1}"
PASSWORD="${PASSWORD:-StrongPass123!}"
EMAIL="applehealth.smoke.$(date +%s)@example.com"

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required but not found."
  exit 1
fi

echo "Checking backend health..."
curl -fsS "${BASE_URL%/api/v1}/health" >/dev/null

echo "Creating smoke user..."
signup_payload=$(printf '{"email":"%s","password":"%s","full_name":"Apple Health Smoke"}' "$EMAIL" "$PASSWORD")
signup_resp=$(curl -fsS -X POST "${BASE_URL}/auth/signup" -H 'Content-Type: application/json' -d "${signup_payload}")
token=$(printf '%s' "${signup_resp}" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

echo "Creating patient..."
patient_resp=$(curl -fsS -X POST "${BASE_URL}/patients/" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer ${token}" \
  -d '{"first_name":"Apple","last_name":"Smoke","date_of_birth":"1992-03-02","gender":"female"}')
patient_id=$(printf '%s' "${patient_resp}" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

echo "Syncing sample steps..."
sync_resp=$(curl -fsS -X POST "${BASE_URL}/integrations/apple-health/patient/${patient_id}/steps/sync" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer ${token}" \
  -d '{"samples":[{"sample_date":"2026-03-01","step_count":8123,"start_at":"2026-03-01T00:00:00Z","end_at":"2026-03-01T23:59:59Z","timezone":"Africa/Nairobi","source_name":"Apple Health"},{"sample_date":"2026-03-02","step_count":9450,"start_at":"2026-03-02T00:00:00Z","end_at":"2026-03-02T23:59:59Z","timezone":"Africa/Nairobi","source_name":"Apple Health"}],"client_anchor":"smoke_anchor","sync_started_at":"2026-03-02T10:00:00Z","sync_completed_at":"2026-03-02T10:00:05Z","device_name":"Smoke iPhone","app_version":"0.1.0"}')

echo "Reading sync status and trend..."
status_resp=$(curl -fsS "${BASE_URL}/integrations/apple-health/patient/${patient_id}/status" -H "Authorization: Bearer ${token}")
trend_resp=$(curl -fsS "${BASE_URL}/integrations/apple-health/patient/${patient_id}/steps?days=14" -H "Authorization: Bearer ${token}")

printf '\nSmoke check complete.\n'
printf 'email=%s\n' "$EMAIL"
printf 'patient_id=%s\n\n' "$patient_id"
printf 'sync=%s\n\n' "$sync_resp"
printf 'status=%s\n\n' "$status_resp"
printf 'trend=%s\n' "$trend_resp"
