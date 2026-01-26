# E2E Tests

Playwright end-to-end tests for MedMemory frontend.

## Prerequisites

1. **Backend must be running** on `http://localhost:8000` (or set `E2E_API_BASE_URL`)
2. **Frontend must be running** on `http://localhost:5173` (or set `PLAYWRIGHT_BASE_URL`)
3. **Database must be accessible** - the backend needs to connect to the test database

## Running Tests

```bash
# From frontend directory
npm exec playwright test

# With UI mode (interactive)
npm exec playwright test --ui

# Run specific test file
npm exec playwright test e2e/auth.spec.ts

# Run in headed mode (see browser)
npm exec playwright test --headed
```

## Environment Variables

You can customize test behavior with environment variables:

- `E2E_EMAIL` - Test user email (default: `demo@medmemory.ai`)
- `E2E_PASSWORD` - Test user password (default: `demo-password`)
- `E2E_FULL_NAME` - Test user full name (default: `Demo User`)
- `E2E_API_BASE_URL` - Backend API URL (default: `http://localhost:8000`)
- `PLAYWRIGHT_BASE_URL` - Frontend URL (default: `http://localhost:5173`)

Example:
```bash
E2E_EMAIL=test@example.com E2E_PASSWORD=testpass123 npm exec playwright test
```

## Test User Setup

The global setup (`global-setup.ts`) automatically creates the test user before tests run. If the user already exists, it will skip creation.

## Troubleshooting

### "Login failed: 401"
- Ensure the backend is running and accessible
- Check that the test user was created (check backend logs or database)
- Verify `E2E_API_BASE_URL` points to the correct backend URL

### "Connection refused"
- Ensure both frontend and backend are running
- Check that ports 5173 (frontend) and 8000 (backend) are available

### Tests timeout
- Increase timeout in `playwright.config.ts`
- Check that the backend is responding (try `curl http://localhost:8000/health`)

### "Upload failed" in document tests
- Ensure a test patient exists (global setup creates one automatically)
- Check backend logs for specific error messages
- Verify the backend has write permissions for the upload directory
- Check that the file being uploaded meets validation requirements (size, type)
- Ensure the patient is actually selected in the UI before upload

### Patient selection issues
- The global setup creates a test patient automatically
- If tests fail to select a patient, check that patients are loading in the UI
- Verify the patient search is working (try searching for "Test" or "Patient")

## Visual Regression Tests

Visual tests compare screenshots against baseline images.

```bash
# Run visual tests (compare against baseline)
npx playwright test e2e/visual.spec.ts

# Update all snapshots
npx playwright test e2e/visual.spec.ts -u

# Update only missing snapshots
npx playwright test e2e/visual.spec.ts --update-snapshots=missing

# Update only changed snapshots
npx playwright test e2e/visual.spec.ts --update-snapshots=changed
```

Baseline snapshots are stored in `e2e/visual.spec.ts-snapshots/`.
