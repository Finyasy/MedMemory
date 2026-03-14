# Clinician Copilot Agent v1 for MedMemory

## Summary

- Build a clinician-first, suggest-only copilot inside the existing clinician workspace.
- Implement a MedMemory-native bounded orchestrator, not an open-ended autonomous agent loop.
- Use fixed task templates plus typed read-only tools for v1.
- Reuse ideas from OpenClaw, Google Workspace CLI, and NanoClaw selectively:
  - OpenClaw for run traces, approvals, and replayability.
  - Google Workspace CLI for strict tool schemas and predictable operator UX.
  - NanoClaw for minimal scope and hard safety boundaries.

## Rationale

MedMemory should not start with an open-ended agent loop. In a healthcare workflow, the first requirement is controlled behavior, not autonomy. The v1 copilot therefore uses deterministic orchestration, typed read-only tools, persisted step traces, and explicit evidence references.

This keeps the system aligned with MedMemory's chart-review use case:

- bounded tool execution instead of unconstrained planning
- persisted run history separate from normal chat history
- read-only data access with no silent mutations
- evidence-backed answers with clear gaps such as `Not in documents` or `Not in records`
- future approval points for side effects, without shipping unsafe side effects in v1

## Core Recommendation

- Do not adopt an OpenClaw-style open-ended agent loop in MedMemory v1.
- Start with code-driven orchestration templates and typed read-only tools.
- Add approval-gated write actions only after grounding quality, auditability, and safety behavior are proven.
- Keep agent state, traces, and suggestions separate from ordinary chat messages.

## V1 Architecture

### Runtime Model

- Execution is synchronous for v1.
- Each run is persisted as a separate clinician copilot artifact.
- The orchestrator follows a fixed template sequence and stops after the defined steps.
- Tool execution is deterministic and read-only.
- Final synthesis is produced from tool outputs, citations, and safety flags.

### Persistence

Three tables persist copilot state:

- `clinician_agent_runs`
- `clinician_agent_steps`
- `clinician_agent_suggestions`

Stored data includes:

- run metadata
- clinician and patient linkage
- prompt and template
- step order and tool name
- structured tool outputs
- citations and safety flags
- final answer
- non-side-effectful suggestion cards

### Backend Service

The bounded orchestrator lives in:

- `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/services/clinician_copilot.py`

Key behaviors:

- fixed tool routing by template
- typed tool output models
- persisted run/step/suggestion trace
- deterministic synthesis
- explicit insufficient-evidence language

## API Changes

Clinician-only endpoints:

- `POST /api/v1/clinician/agent/runs`
- `GET /api/v1/clinician/agent/runs/{run_id}`
- `GET /api/v1/clinician/agent/runs?patient_id=<id>`

Request shape for run creation:

```json
{
  "patient_id": 123,
  "prompt": "Review this chart and surface the most important evidence for a clinician handoff.",
  "template": "chart_review",
  "conversation_id": null
}
```

Response includes:

- final answer
- citations
- safety flags
- step trace
- suggestion cards
- timestamps and run status

## Tool Catalog

All v1 tools are typed and read-only.

### `patient_snapshot`

- Summarizes the patient's chart footprint.
- Returns counts for documents, records, labs, medications, and provider connections.

### `recent_documents`

- Returns the most recent patient documents.
- Emits document citations and a `missing_documents` safety flag when none exist.

### `record_search`

- Performs bounded keyword matching across patient records and documents.
- Emits `insufficient_record_context` when no relevant matches are found.

### `abnormal_labs`

- Returns recent abnormal or critical lab results.
- Emits lab-result citations for flagged tests.

### `lab_trends`

- Compares recent numeric lab values to produce bounded trend summaries.
- Prioritizes prompt-relevant metrics when possible.

### `medication_reconciliation`

- Summarizes active medications and recent inactive or completed entries.
- Supports reconciliation workflows without mutating medication state.

### `provider_sync_health`

- Reviews patient data connection status and recent sync failures.
- Emits `provider_sync_attention` when sync failures exist.

### `draft_clinician_note_outline`

- Produces a suggest-only note outline from prior tool outputs.
- Adds no side effects and does not write notes back into the chart.

## Fixed Templates

### `chart_review`

Sequence:

1. `patient_snapshot`
2. `recent_documents`
3. `abnormal_labs`
4. `draft_clinician_note_outline`

### `trend_review`

Sequence:

1. `patient_snapshot`
2. `lab_trends`
3. `abnormal_labs`

### `med_reconciliation`

Sequence:

1. `patient_snapshot`
2. `medication_reconciliation`
3. `record_search`

### `data_quality`

Sequence:

1. `provider_sync_health`
2. `recent_documents`
3. `record_search`

## Frontend Changes

The clinician workspace now includes a dedicated copilot panel:

- preset task entry points for the four templates
- prompt box scoped to the selected template
- run history
- step trace
- citations
- suggestion cards without direct side effects

Relevant files:

- `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/components/clinician/ClinicianCopilotPanel.tsx`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/pages/ClinicianDashboardPage.tsx`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/types.ts`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/src/api.ts`

## Safety Boundaries

- clinician-only access
- requires existing patient access grant checks
- no external web access in v1
- no arbitrary execution or open-ended tool loops
- no patient-facing behavior in this phase
- no direct writes, sync triggers, medication changes, orders, or prescriptions
- suggestions are informative and navigational only

## Test Plan

### Backend

- unit test template routing
- unit test insufficient-evidence synthesis
- unit test suggestion generation from abnormal labs and sync issues
- integration-style endpoint tests for run creation, retrieval, and listing

### Frontend

- component test for copilot panel rendering
- preset task execution test
- run trace rendering test
- suggestion card rendering test

### Acceptance Rule

The clinician receives evidence-grounded output and suggestions without the copilot mutating patient state.

### Pre-Demo Verification

Run this from the repo root before a clinician copilot demo:

```bash
./scripts/run_clinician_copilot_demo_check.sh
```

This must pass both:

- backend live smoke via `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/scripts/run_clinician_copilot_smoke.py`
- frontend browser smoke via `/Users/bryan.bosire/anaconda_projects/MedMemory/frontend/e2e/clinician-copilot.spec.ts`

Useful variants:

- `./scripts/run_clinician_copilot_demo_check.sh --template data_quality`
- `./scripts/run_clinician_copilot_demo_check.sh --skip-browser`
- `./scripts/run_clinician_copilot_demo_check.sh --skip-backend`

Operational references:

- `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/DEMO_CHECKLIST.md`
- `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/LESSONS_LEARNED.md`

## Assumptions

- the first shipped copilot is clinician-facing
- autonomy is suggest-only
- agent history is separate from normal chat history
- MCP or OpenClaw plugin compatibility is explicitly out of scope for v1

## Deferred Phase 2 Items

- approval-gated write tools
- async run execution and streaming traces
- reusable skill packs by role
- separate patient-facing copilot surfaces
- richer replay and operator audit tooling
- plugin compatibility or external tool packaging once safety and usefulness are demonstrated
