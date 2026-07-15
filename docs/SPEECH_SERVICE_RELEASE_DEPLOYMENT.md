# Speech Service Release Deployment

This document is the release-facing runbook for deploying the extracted
Swahili TTS worker at `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/speech_service.py`.

Executable local release gate:

- `/Users/bryan.bosire/anaconda_projects/MedMemory/scripts/run_speech_service_release_gate.sh`

## Scope

This covers the `speech-service` runtime only:

- local model loading for `facebook/mms-tts-swh`
- HTTP boundary mode via `SPEECH_SYNTHESIS_BACKEND=http`
- worker health, rollout, rollback, and failure isolation

It does **not** cover:

- MedASR evaluation policy
- WAXAL fine-tuning
- Swahili ASR

## Runtime topology

Production uses two backend processes:

1. **Main API**
   - `app.main:app`
   - serves patient/clinician APIs
   - calls the speech boundary over HTTP
2. **Speech worker**
   - `app.speech_service:app`
   - loads the Swahili TTS model once
   - serves only internal synthesis and health endpoints

## Required configuration

### Main API

- `SPEECH_SYNTHESIS_BACKEND=http`
- `SPEECH_SYNTHESIS_SERVICE_BASE_URL=http://speech-service:8010`
- `SPEECH_SYNTHESIS_SERVICE_TIMEOUT_SECONDS=30`
- `SPEECH_SERVICE_INTERNAL_API_KEY=<shared-secret>`

### Speech worker

- `SPEECH_SYNTHESIS_MODEL_PATH=/app/models/mms-tts-swh`
- `SPEECH_SYNTHESIS_ASSETS_DIR=/app/artifacts/speech/generated`
- `SPEECH_SERVICE_INTERNAL_API_KEY=<same-shared-secret>`

## Container contract

### Image

Reuse the backend image built from `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/Dockerfile`.

### Command

```bash
uvicorn app.speech_service:app --host 0.0.0.0 --port 8010
```

### Mounts

- models volume mounted read-only
- artifacts volume mounted read-write

Required local paths in this repo:

- `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/models/mms-tts-swh`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/artifacts/speech/generated`

## Health checks

### Worker readiness

Request:

```bash
curl -sf \
  -H "X-Speech-Service-Key: ${SPEECH_SERVICE_INTERNAL_API_KEY}" \
  http://127.0.0.1:8010/internal/v1/health
```

Expected:

- HTTP `200`
- synthesis readiness is `ok=true`
- configured source points at the local TTS model path

### Main API readiness

Request:

```bash
curl -sf http://127.0.0.1:8000/health/speech
```

Expected:

- HTTP `200`
- `boundary_backend=http`
- worker-backed synthesis health is present

## Rollout sequence

1. Provision local model assets into the shared model volume.
2. Start the speech worker and wait for `/internal/v1/health`.
3. Start the main API with `SPEECH_SYNTHESIS_BACKEND=http`.
4. Verify `/health` and `/health/speech`.
5. Run the browser regression:

```bash
cd /Users/bryan.bosire/anaconda_projects/MedMemory/frontend
npm exec playwright test e2e/swahili-speech-output-smoke.spec.ts --workers=1 --reporter=line
```

6. Only then shift traffic.

## Rollback

If the speech worker is degraded:

1. stop or isolate the failing speech worker
2. switch the main API to:

```env
SPEECH_SYNTHESIS_BACKEND=in_process
```

3. restart only the main API
4. verify `/health/speech` reports `boundary_backend=in_process`

This keeps Swahili TTS available while the worker is repaired.

## Failure handling

### Worker unhealthy

- symptom: `/internal/v1/health` fails
- action: keep traffic off the worker and roll back to `in_process`

### Model path missing

- symptom: synthesis readiness reports missing model assets
- action: re-provision `mms-tts-swh`, then restart the worker

### Shared-secret mismatch

- symptom: worker health or synthesis calls return `401`
- action: verify `SPEECH_SERVICE_INTERNAL_API_KEY` matches on both processes

### Slow synthesis

- symptom: rising chat latency or timeout errors
- action:
  - check worker logs
  - verify model load path and cache directory
  - review artifact write latency
  - consider worker replication before changing the main API timeout

## Logging and artifacts

Persist these logs separately:

- main API log
- speech worker log
- browser smoke log

Persist these artifacts:

- generated speech assets
- Playwright output for `swahili-speech-output-smoke`
- `/health/speech` snapshot during rollout

## Minimum release gate

Do not promote a release unless all of the following pass:

- `/health`
- `/health/speech`
- worker `/internal/v1/health`
- `e2e/swahili-refusal-smoke.spec.ts`
- `e2e/swahili-speech-output-smoke.spec.ts`

## Local compose reference

The current local compose implementation is already codified in:

- `/Users/bryan.bosire/anaconda_projects/MedMemory/docker-compose.local-backend.dev.yml`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/docker-compose.local-backend.yml`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/start-hybrid.sh`

Those files are the reference implementation for the production split-runtime
shape. Release automation should mirror them instead of inventing a separate
runtime contract.
