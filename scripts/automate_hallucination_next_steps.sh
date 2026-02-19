#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"

LOCAL_ONLY="false"
BASE_BRANCH="main"
WORKFLOW_NAME="Hallucination Nightly"

for arg in "$@"; do
  case "${arg}" in
    --local-only)
      LOCAL_ONLY="true"
      ;;
    --base=*)
      BASE_BRANCH="${arg#*=}"
      ;;
    *)
      echo "Unknown argument: ${arg}" >&2
      echo "Usage: $0 [--local-only] [--base=<branch>]" >&2
      exit 2
      ;;
  esac
done

require_file() {
  local path="$1"
  if [[ ! -f "${path}" ]]; then
    echo "Missing required file: ${path}" >&2
    exit 1
  fi
}

run_local_pipeline() {
  echo "Running local hallucination evaluation + gate..."
  cd "${BACKEND_DIR}"

  uv run python scripts/evaluate_rag_hallucination.py \
    --eval-file data/hallucination_rag_eval/eval.jsonl \
    --output-dir artifacts/hallucination_eval/current \
    --scope baseline \
    --min-policy-pass-rate 1.0

  uv run python scripts/hallucination_regression_gate.py \
    --candidate-metrics artifacts/hallucination_eval/current/metrics_summary.json \
    --candidate-scope baseline \
    --baseline-metrics data/hallucination_eval/baseline_metrics_summary.json \
    --baseline-scope baseline \
    --max-hallucination-rate 0.01 \
    --min-fact-precision 0.99 \
    --min-fact-recall 0.99 \
    --min-token-f1 0.99 \
    --max-hallucination-increase 0.01 \
    --max-fact-precision-drop 0.01 \
    --max-fact-recall-drop 0.01 \
    --max-token-f1-drop 0.01 \
    --min-candidate-examples 22 \
    --min-baseline-examples 22 \
    --min-task-policy-pass-rate numeric_grounding=1.0 \
    --min-task-policy-pass-rate numeric_citation=1.0 \
    --min-task-policy-pass-rate question_mode=1.0 \
    --min-task-policy-pass-rate context_gate=1.0 \
    --min-task-policy-pass-rate trend_direct=1.0 \
    --min-task-examples numeric_grounding=4 \
    --min-task-examples numeric_citation=4 \
    --min-task-examples question_mode=4 \
    --min-task-examples context_gate=5 \
    --min-task-examples trend_direct=5 \
    --output-json artifacts/hallucination_eval/gate_report.json

  require_file "artifacts/hallucination_eval/current/metrics_summary.json"
  require_file "artifacts/hallucination_eval/current/report.md"
  require_file "artifacts/hallucination_eval/current/predictions.jsonl"
  require_file "artifacts/hallucination_eval/gate_report.json"
}

require_gh_auth() {
  if ! command -v gh >/dev/null 2>&1; then
    echo "GitHub CLI not found."
    return 1
  fi
  if ! gh auth status >/dev/null 2>&1; then
    echo "GitHub CLI is not authenticated."
    return 1
  fi
  return 0
}

set_optional_webhook_secret() {
  local repo="$1"
  if [[ -n "${HALLUCINATION_ALERT_WEBHOOK:-}" ]]; then
    if [[ "${HALLUCINATION_ALERT_WEBHOOK}" == *"..."* ]]; then
      echo "HALLUCINATION_ALERT_WEBHOOK appears to be a placeholder; skipping secret update."
      return
    fi
    echo "Setting HALLUCINATION_ALERT_WEBHOOK secret..."
    if ! printf "%s" "${HALLUCINATION_ALERT_WEBHOOK}" | gh secret set \
      HALLUCINATION_ALERT_WEBHOOK \
      --repo "${repo}"; then
      echo "Warning: failed to set HALLUCINATION_ALERT_WEBHOOK; continuing without secret update."
    fi
  else
    echo "HALLUCINATION_ALERT_WEBHOOK not set in environment; skipping secret update."
  fi
}

push_and_prepare_pr() {
  local repo="$1"
  local branch="$2"

  echo "Pushing branch '${branch}'..."
  git -C "${ROOT_DIR}" push -u origin "${branch}"

  if gh pr view "${branch}" --repo "${repo}" >/dev/null 2>&1; then
    echo "PR already exists for branch '${branch}'."
    return
  fi

  local title body
  title="chore: automate hallucination gate rollout"
  body=$(
    cat <<'EOF'
Automated rollout for hallucination guardrail workflow:

- run local RAG hallucination eval + regression gate
- enforce CI gate thresholds and task-level coverage
- provide nightly workflow execution path
EOF
  )

  echo "Creating PR..."
  gh pr create \
    --repo "${repo}" \
    --base "${BASE_BRANCH}" \
    --head "${branch}" \
    --title "${title}" \
    --body "${body}"
}

dispatch_and_verify_nightly() {
  local repo="$1"
  local branch="$2"
  local run_id download_dir

  echo "Dispatching '${WORKFLOW_NAME}' for branch '${branch}'..."
  gh workflow run "${WORKFLOW_NAME}" --repo "${repo}" --ref "${branch}"

  sleep 5
  run_id="$(gh run list \
    --repo "${repo}" \
    --workflow "${WORKFLOW_NAME}" \
    --branch "${branch}" \
    --limit 1 \
    --json databaseId \
    --jq '.[0].databaseId')"

  if [[ -z "${run_id}" || "${run_id}" == "null" ]]; then
    echo "Unable to locate dispatched workflow run id." >&2
    exit 1
  fi

  echo "Watching run ${run_id}..."
  gh run watch "${run_id}" --repo "${repo}" --exit-status --interval 10

  download_dir="${ROOT_DIR}/artifacts/hallucination_automation/nightly_run_${run_id}"
  mkdir -p "${download_dir}"
  gh run download "${run_id}" --repo "${repo}" -D "${download_dir}"

  require_file "${download_dir}/metrics_summary.json"
  require_file "${download_dir}/gate_report.json"
  require_file "${download_dir}/predictions.jsonl"
  require_file "${download_dir}/report.md"
  echo "Nightly artifacts verified at ${download_dir}"
}

run_local_pipeline

if [[ "${LOCAL_ONLY}" == "true" ]]; then
  echo "Local-only mode complete."
  exit 0
fi

if ! require_gh_auth; then
  cat <<'EOF'
GitHub automation skipped because gh is unavailable or not authenticated.
Local hallucination checks already completed successfully.
Install/authenticate gh, then rerun this script to automate push/PR/nightly.
EOF
  exit 0
fi
REPO_NAME="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
BRANCH_NAME="$(git -C "${ROOT_DIR}" rev-parse --abbrev-ref HEAD)"

if [[ "${BRANCH_NAME}" == "HEAD" ]]; then
  echo "Detached HEAD detected. Checkout a branch before running automation." >&2
  exit 1
fi

if [[ "${BRANCH_NAME}" == "${BASE_BRANCH}" ]]; then
  echo "Current branch is '${BASE_BRANCH}'. Use a feature branch for PR automation." >&2
  exit 1
fi

set_optional_webhook_secret "${REPO_NAME}"
push_and_prepare_pr "${REPO_NAME}" "${BRANCH_NAME}"
dispatch_and_verify_nightly "${REPO_NAME}" "${BRANCH_NAME}"

echo "Automation complete."
