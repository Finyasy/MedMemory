# MedMemory Observability Runbook

Date: 2026-03-19

## Purpose

This runbook defines the current observability baseline for MedMemory and the next operational steps needed before production.

## Current Signals in Repo

Backend metrics are exposed from:

- `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/api/health.py`

The current process-local registry is implemented in:

- `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/services/observability.py`

Best-effort access audit writes are implemented in:

- `/Users/bryan.bosire/anaconda_projects/MedMemory/backend/app/services/audit.py`

## Metrics Available Now

The `/metrics` endpoint currently exposes:

- `medmemory_uptime_seconds`
- `medmemory_http_requests_total`
- `medmemory_http_request_duration_ms_total`
- `medmemory_http_request_duration_ms_count`
- `medmemory_clinician_agent_runs_total`
- `medmemory_access_audit_events_total`
- `medmemory_guardrail_events_total`

## Starter Alert Rules

Starter Prometheus rules live in:

- `/Users/bryan.bosire/anaconda_projects/MedMemory/ops/observability/prometheus/medmemory-production-rules.yml`

Current starter alerts:

- high backend 5xx rate
- high average backend latency
- clinician copilot failures
- access audit write failures

These are intended as a baseline, not a finished paging policy.

## Example Prometheus Scrape Target

```yaml
scrape_configs:
  - job_name: medmemory-api
    metrics_path: /metrics
    static_configs:
      - targets:
          - medmemory-backend-staging:8000
```

## Operator Checks

Before a release or staging validation:

1. confirm `/health` returns `200`
2. confirm `/metrics` exposes the MedMemory metric families above
3. confirm clinician copilot smoke updates `medmemory_clinician_agent_runs_total`
4. confirm access workflows update `medmemory_access_audit_events_total`

## Gaps Still Open

- no external dashboard is configured in repo
- no Alertmanager routing/on-call mapping is configured in repo
- no provider sync failure metric exists yet
- no backup/restore monitoring exists yet
- current metrics are process-local, so multi-instance aggregation still depends on external Prometheus scraping

## Next Observability Steps

1. wire Prometheus or managed metrics scraping to the staging backend
2. load `/Users/bryan.bosire/anaconda_projects/MedMemory/ops/observability/prometheus/medmemory-production-rules.yml`
3. connect alerts to the actual operator channel
4. add provider-sync failure counters
5. add backup and restore success/failure signals
