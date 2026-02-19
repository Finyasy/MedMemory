# MedGemma Chat Tone Evaluation Report

Date: 2026-02-18  
Status: Implemented and evaluated with Playwright A/B runs.

## Objective

Improve chat tone to be warm + concise (less robotic) without grounding, citation, or refusal regressions.

## Implemented Prompt Profiles

- `baseline_current`
- `warm_concise_v1`
- `warm_concise_v2`
- `clinician_terse_humanized`

Runtime selector (internal): `LLM_PROMPT_PROFILE` in backend environment/config.

## Eval Harness

- Fixtures: `docs/fixtures/medgemma_chat_eval/public_record_samples.json`
- Scenarios: `docs/fixtures/medgemma_chat_eval/scenarios.json`
- Playwright spec: `frontend/e2e/chat-tone-eval.spec.ts`
- Artifacts output: `artifacts/medgemma-chat-eval/`
- Cross-variant summary: `artifacts/medgemma-chat-eval/latest-summary.json`

Captured per run:
- assistant responses
- source chips
- mode metadata (`ask/stream`, `structured`, `coaching_mode`, `clinician_mode`)
- scoring JSON

## Scoring & Hard Fail Logic

- Grounding score:
  - unsupported numeric claims
  - uncited clinician numeric claims
  - refusal-policy violations
- Naturalness score:
  - robotic phrase count
  - duplicate sentence count
  - template-starter count
  - sentence variability
- UX score:
  - concise pass rate
  - first-sentence usefulness rate
  - clarity issues

Hard fail if:
- unsupported numeric claims > 0, or
- refusal-policy violations > 0, or
- grounding regression vs latest baseline artifact.

## Runbook

From project root:

1. Ensure services are up:
   - `curl http://localhost:8000/health`
   - `curl http://localhost:5173`
2. For each profile, restart backend with:
   - `LLM_PROMPT_PROFILE=<profile>`
3. Run eval:
   - `cd frontend && E2E_PROMPT_PROFILE=<profile> npm exec playwright test e2e/chat-tone-eval.spec.ts`
   - Optional strict gate: add `E2E_EVAL_ENFORCE_HARD_FAIL=true`
4. Run smoke checks:
   - `cd frontend && npm exec playwright test e2e/chat.spec.ts e2e/clinician-smoke.spec.ts`
5. Run one-time stale fixture cleanup (optional but recommended before fresh baselines):
   - `cd backend && uv run python scripts/cleanup_eval_fixtures.py`
   - `cd backend && uv run python scripts/cleanup_eval_fixtures.py --apply`

## CI Gate

- CI now runs:
  - Playwright smoke tests (`chat.spec.ts`, `clinician-smoke.spec.ts`)
  - Tone eval hard gate with `E2E_EVAL_ENFORCE_HARD_FAIL=true`
- Workflow: `.github/workflows/ci.yml`
- Tone eval artifacts are uploaded as `medgemma-chat-tone-eval`.
- Nightly 4-profile A/B loop: `.github/workflows/medgemma-tone-nightly.yml`
- Nightly run posts winner deltas to the GitHub job summary and writes:
  - `artifacts/medgemma-chat-eval/nightly-winner-deltas.md`

## Winner Selection Rule

Choose profile with best naturalness uplift and zero grounding regression vs baseline.
Tie-break (when uplift + UX are equal): prefer patient-target profile order
`warm_concise_v1` > `warm_concise_v2` > `clinician_terse_humanized`.

## Final Selection

- Latest summary artifact: `artifacts/medgemma-chat-eval/latest-summary.json`
- Generated at: `2026-02-18T17:45:41.129Z`
- Baseline (`baseline_current`): grounding `100`, naturalness `70`, UX `100`, hard_fail `false`
- `warm_concise_v1`: grounding `100`, naturalness `70`, UX `100`, hard_fail `false`
- `warm_concise_v2`: grounding `100`, naturalness `70`, UX `87`, hard_fail `false`
- `clinician_terse_humanized`: grounding `100`, naturalness `70`, UX `100`, hard_fail `false`
- Selected winner: `warm_concise_v1`
- Applied default: backend config now defaults to `LLM_PROMPT_PROFILE=warm_concise_v1`
- Runtime env (`backend/.env`) set to `LLM_PROMPT_PROFILE=warm_concise_v1`
