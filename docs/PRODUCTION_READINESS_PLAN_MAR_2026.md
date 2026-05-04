# MedMemory Production Readiness Plan

Date: 2026-03-14

## Purpose

This document turns MedMemory's current demo-ready state into a production rollout plan with explicit gates, sequencing, and ownership areas.

It does not assume the entire product should go live at once. The correct path is:

1. stabilize the clinician copilot v1 workflow
2. establish a real staging environment
3. harden security, observability, and deployment
4. onboard live healthcare integrations in staging first
5. release a bounded production slice only after the gates below pass

## Current State

### Working now

- clinician copilot v1 exists and is bounded
- demo gate exists:
  - `/Users/bryan.bosire/anaconda_projects/MedMemory/scripts/run_clinician_copilot_demo_check.sh`
- a dedicated CI workflow now runs that same gate:
  - `/Users/bryan.bosire/anaconda_projects/MedMemory/.github/workflows/clinician-copilot-demo-gate.yml`
- a repo-managed staging scaffold now exists:
  - `/Users/bryan.bosire/anaconda_projects/MedMemory/docker-compose.staging.yml`
  - `/Users/bryan.bosire/anaconda_projects/MedMemory/scripts/bring_up_staging.sh`
- initial audit logging and metrics now exist for clinician access and copilot paths
- clinician UI has gone through an audit and bounded polish pass
- clinician copilot state is persisted and tested

### Not yet production-ready

- no formal staging-to-production promotion path
- no production-grade secret management documented for the full stack
- observability is still local/process-level only; alerting, dashboards, and backup drills are still missing
- Kenya live integrations are not yet proven in a staging environment with real partner credentials
- the repo still contains significant unrelated in-flight work, which is a release-management risk by itself

## Production Goal

The first production target should be:

- bounded clinician copilot v1
- Kenya-focused data connections that are proven in staging
- strong auditability, explicit evidence boundaries, and no open-ended agent loop

Do not expand to phase-2 agent behavior before this baseline is stable.

## Non-Negotiable Release Gates

MedMemory should not go live until all of the following are true.

### 1. Release Discipline

- all production work merges through scoped branches, not a dirty shared branch
- migrations are versioned and tested in staging before production
- every release candidate has a rollback path
- demo/smoke gates are automated in CI, not run manually only

### 2. Security and Privacy

- secrets are managed outside local `.env` files
- production uses TLS end to end
- audit logging exists for clinician access, patient access, and copilot runs
- auth/session settings are production-hardened
- rate limits and abuse controls are enabled
- PHI/PII logging is reviewed and minimized

### 3. Staging Environment

- staging has its own database, storage, backend, frontend, and secrets
- staging uses synthetic or approved non-production data only
- staging can run migrations, smoke tests, and rollback checks independently

### 4. Observability and Recovery

- structured logs exist for backend, sync, and copilot runs
- metrics and alerting exist for auth failures, sync failures, and copilot failures
- database backups are automated
- at least one restore drill has been performed

### 5. Healthcare Integration Safety

- each live DHA/KHIS/vendor integration is verified in staging before production
- credential refresh/failure behavior is understood and documented
- idempotency and replay behavior exist for sync workflows
- FHIR version assumptions are explicit per provider

### 6. Product Safety

- clinician copilot remains suggest-only
- citations and evidence boundaries remain explicit
- missing evidence produces bounded language such as `Not in documents` or `Not in records`
- no hidden writes or autonomous actions are introduced

## Phased Delivery Plan

## Phase 0 - Branch and Release Hygiene

Objective:

- stop shipping from mixed worktrees

Tasks:

- make scoped PRs mandatory for release-facing changes
- protect `main`
- require the clinician copilot demo gate in CI
- define release tagging and rollback procedure

Implementation status:

- implemented in repo:
  - local gate script:
    - `/Users/bryan.bosire/anaconda_projects/MedMemory/scripts/run_clinician_copilot_demo_check.sh`
  - CI workflow:
    - `/Users/bryan.bosire/anaconda_projects/MedMemory/.github/workflows/clinician-copilot-demo-gate.yml`
- still required outside the repo:
  - mark the `Clinician Copilot Demo Gate / clinician-copilot-demo-gate` check as required in GitHub branch protection for `main`

Acceptance:

- a release candidate can be built from a clean branch
- a failed release can be rolled back without manual guessing

## Phase 1 - Staging Environment

Objective:

- create a real promotion target between local dev and production

Tasks:

- provision staging backend, frontend, database, and object storage
- configure managed secrets for staging
- run Alembic migrations in staging
- wire the clinician copilot demo gate to staging URLs
- document staging access and reset procedures

Implementation status:

- local staging scaffold implemented in repo:
  - `/Users/bryan.bosire/anaconda_projects/MedMemory/docker-compose.staging.yml`
  - `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/.env.staging.example`
  - `/Users/bryan.bosire/anaconda_projects/MedMemory/scripts/bring_up_staging.sh`
  - `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/STAGING_RUNBOOK_MAR_2026.md`
- still required outside the repo:
  - managed staging secrets
  - staging object storage
  - real hosted staging environment and access control

Acceptance:

- the full clinician copilot gate passes in staging
- staging can be rebuilt from scratch

## Phase 2 - Security and Privacy Hardening

Objective:

- close obvious production risk before real traffic

Tasks:

- move secrets into a secret manager
- audit all production env vars and defaults
- enforce production CORS/origin policy
- add auth/session expiry review
- add explicit audit events for:
  - clinician login
  - patient access grant usage
  - copilot run creation
  - provider sync failures
- review logs for PHI leakage

Acceptance:

- no production secret lives only in repo-local files
- critical auth and copilot actions are auditable

## Phase 3 - Observability, Reliability, and Backup

Objective:

- make failures visible and recoverable

Tasks:

- add structured logging fields for request ID, patient ID, clinician ID, and run ID where appropriate
- add metrics for:
  - backend latency
  - 5xx rate
  - copilot run failure rate
  - provider sync failure rate
  - queue depth / long-running syncs
- define alert thresholds
- add database backup schedule
- perform restore test

Implementation status:

- initial observability implemented in repo:
  - request counters and latency metrics
  - clinician copilot run metrics
  - access audit event metrics
  - `/metrics` endpoint now exposes these counters
  - starter Prometheus alert rules:
    - `/Users/bryan.bosire/anaconda_projects/MedMemory/ops/observability/prometheus/medmemory-production-rules.yml`
  - runbook:
    - `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/OBSERVABILITY_RUNBOOK_MAR_2026.md`
- still required outside the repo:
  - dashboards
  - alert rules
  - backup automation
  - restore drill

Acceptance:

- operator can answer “what failed, for whom, and since when?”
- restore drill is documented and successful

## Phase 4 - Kenya Integration Hardening

Objective:

- replace placeholder sync confidence with validated external behavior

Tasks:

- onboard staging credentials for DHA/KHIS/approved vendors
- verify actual FHIR base URLs and auth model per provider
- document provider-specific behavior:
  - token refresh
  - timeouts
  - pagination
  - retry/backoff
  - partial failure handling
- add replay-safe sync behavior
- add staging smoke checks for at least one real integration path

Acceptance:

- staging can prove at least one real end-to-end provider sync
- operator can distinguish provider outage, auth failure, and data-empty success

## Phase 5 - CI/CD and Deploy Automation

Objective:

- make releases repeatable

Tasks:

- add CI jobs for:
  - backend tests
  - frontend build
  - clinician copilot demo gate
  - migration check
  - security/static checks
- add deploy pipeline for staging
- add manual approval step for production
- document rollback command path

Acceptance:

- no production deploy depends on manual shell history
- staging deploys are repeatable and auditable

## Phase 6 - Production Readiness Review

Objective:

- explicitly approve the bounded initial release

Tasks:

- run final checklist against staging
- review open P0/P1 issues
- review legal/privacy/compliance obligations
- confirm on-call ownership
- confirm support runbook for sync failures and access issues

Acceptance:

- leadership and engineering can answer:
  - what is launching
  - who operates it
  - how it is monitored
  - how it is rolled back

## Suggested 6-Week Sequence

### Week 1

- Phase 0
- start Phase 1

### Week 2

- finish Phase 1
- start Phase 2

### Week 3

- finish Phase 2
- start Phase 3

### Week 4

- finish Phase 3
- start Phase 4

### Week 5

- finish Phase 4
- implement Phase 5

### Week 6

- Phase 6 review
- production go/no-go decision

## Immediate Next Actions

These are the next concrete actions with the best value-to-risk ratio:

1. Make `/Users/bryan.bosire/anaconda_projects/MedMemory/scripts/run_clinician_copilot_demo_check.sh` a required CI check.
2. Stand up staging with separate secrets and database.
3. Add audit logging for clinician access and copilot runs.
4. Add production metrics, alerts, and backup/restore testing.
5. Validate one real Kenya integration in staging before any production onboarding.

## Operational References

- Demo gate:
  - `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/DEMO_CHECKLIST.md`
- GitHub branch protection:
  - `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/GITHUB_BRANCH_PROTECTION_RUNBOOK_MAR_2026.md`
- Observability:
  - `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/OBSERVABILITY_RUNBOOK_MAR_2026.md`
- Copilot plan:
  - `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/CLINICIAN_COPILOT_AGENT_V1_PLAN.md`
- Clinician UI polish:
  - `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/CLINICIAN_PORTAL_V1_POLISH_SPEC_MAR_2026.md`
- Lessons learned:
  - `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/LESSONS_LEARNED.md`

## External Reference Baselines

Use these as the baseline references while hardening the product:

- OWASP Application Security Verification Standard:
  - https://owasp.org/www-project-application-security-verification-standard/
- NIST Secure Software Development Framework:
  - https://csrc.nist.gov/Projects/ssdf
- HL7 FHIR specification:
  - https://hl7.org/fhir/
