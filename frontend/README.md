# MedMemory Frontend

React + TypeScript + Vite clinician and patient frontend.

## Runtime

Use Node.js 22.x. The project pins the expected local version in `.nvmrc`.

```bash
nvm use
npm install
```

## Development

```bash
npm run dev -- --host 127.0.0.1
```

Default local URL:

- Frontend: `http://127.0.0.1:5173`
- Backend API: `http://localhost:8000`

## Build

```bash
npm run build
```

The build runs TypeScript first, then Vite.

## Generated API Client

MedMemory uses a generated OpenAPI client for type-safe API calls.

```bash
npm run generate-api
```

The client is generated into `frontend/src/api/generated`.

## Clinician Demo Gate

From the repo root, run:

```bash
./scripts/run_clinician_copilot_demo_check.sh
```

This checks the backend clinician copilot flow and then runs the frontend Playwright clinician copilot smoke test. The script resolves Node 22 from `frontend/.nvmrc` when possible.
