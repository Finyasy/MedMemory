# MedMemory Staging Runbook

Date: 2026-03-19

## Purpose

This runbook defines the repo-managed local staging stack used to harden MedMemory before any production rollout.

Files introduced for this stage:

- `/Users/bryan.bosire/anaconda_projects/MedMemory/docker-compose.staging.yml`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/.env.staging.example`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/scripts/ensure_schema_ready.py`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/scripts/bring_up_staging.sh`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/.github/workflows/clinician-copilot-demo-gate.yml`

## Why this exists

Local dev and production are too far apart today. The staging stack closes that gap by providing:

- a separate database and ports
- production-style backend and frontend containers
- explicit migrations before startup
- a path to run the clinician copilot gate against staging URLs

## Ports

- database: `5433`
- backend: `8001`
- frontend: `4173`
- compose project name: `medmemory-staging`

## Setup

1. Copy the backend staging env file:

```bash
cp /Users/bryan.bosire/anaconda_projects/MedMemory/backend/.env.staging.example \
   /Users/bryan.bosire/anaconda_projects/MedMemory/backend/.env.staging
```

2. Fill in real staging secrets:

- `JWT_SECRET_KEY`
- provider sync credentials
- any other non-default production-like settings required for the target environment

## Start staging

From the repo root:

```bash
./scripts/bring_up_staging.sh
```

This will:

- start the staging database
- run `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/scripts/ensure_schema_ready.py` from the local backend environment against the staging database
- start the backend and frontend containers
- wait for health endpoints

## Run the clinician copilot gate against staging

```bash
./scripts/bring_up_staging.sh --run-smoke
```

or manually:

```bash
./scripts/run_clinician_copilot_demo_check.sh \
  --backend-url http://127.0.0.1:8001 \
  --frontend-url http://127.0.0.1:4173
```

The backend smoke auto-provisions the demo patient account and first patient record if they do not already exist, so a fresh staging database does not need manual patient setup before the gate runs.

## Important staging defaults

- `STARTUP_REQUIRE_EMBEDDINGS=false`
- `PRELOAD_LLM_ON_STARTUP=0`
- the staging database intentionally does not mount `/db/init`; it is bootstrapped from MedMemory's application schema helper instead of local dev SQL

Current bootstrap note:

- the repo's historical baseline migration does not support a truly empty database cleanly, so local CI/staging currently use `ensure_schema_ready.py` to create the current schema on an empty database and stamp Alembic to head
- once a database is versioned, the same helper upgrades it with Alembic normally

These defaults keep the scaffold usable before model assets are mounted into staging. They are acceptable for staging bootstrap, not as a production excuse.

## Next staging hardening steps

1. Mount real model assets or point the runtime at managed model storage.
2. Replace placeholder provider credentials with staging DHA/KHIS/vendor credentials.
3. Add backup and restore checks for the staging database.
4. Mark `Clinician Copilot Demo Gate / clinician-copilot-demo-gate` as required in GitHub branch protection.
5. Promote the staging smoke gate into CI/CD deployment flow.
