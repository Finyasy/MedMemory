# Demo Checklist

## Clinician Copilot v1

Run this before any clinician copilot demo.

### Required gate

From the repo root:

```bash
./scripts/run_clinician_copilot_demo_check.sh
```

This must pass:

- backend clinician copilot live smoke
- frontend clinician copilot Playwright smoke

### Environment checks

- backend is running on `http://localhost:8000`, or pass `--backend-url`
- if `localhost` resolves incorrectly on this machine, use `--backend-url http://127.0.0.1:8000`
- frontend is running on `http://localhost:5173`, or pass `--frontend-url`
- if the UI is stale or not serving the MedMemory shell on `:5173`, rerun the gate with `--restart-frontend`
- database is reachable by the backend
- clinician test account can log in
- if the patient test account or first patient record is missing, the backend smoke auto-provisions them before the browser step

### Expected outcome

- a copilot run is created successfully
- the run is retrievable from list and single-run endpoints
- the clinician workspace renders the copilot panel
- at least one suggestion CTA is clickable
- the CTA performs safe navigation only

### Useful variants

```bash
./scripts/run_clinician_copilot_demo_check.sh --template data_quality
./scripts/run_clinician_copilot_demo_check.sh --skip-browser
./scripts/run_clinician_copilot_demo_check.sh --skip-backend
./scripts/run_clinician_copilot_demo_check.sh --restart-frontend
```

### Artifacts

- backend smoke output:
  - `backend/artifacts/clinician_copilot/live_smoke.json`

### Related docs

- production rollout plan:
  - `/Users/bryan.bosire/anaconda_projects/MedMemory/docs/PRODUCTION_READINESS_PLAN_MAR_2026.md`
- CI workflow mirror of this local gate:
  - `/Users/bryan.bosire/anaconda_projects/MedMemory/.github/workflows/clinician-copilot-demo-gate.yml`
