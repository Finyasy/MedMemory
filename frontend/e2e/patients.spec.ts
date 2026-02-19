import { test } from '@playwright/test';
import { login, selectFirstPatient } from './fixtures';

test('patients list renders after login', async ({ page }) => {
  const email = process.env.E2E_EMAIL || 'demo@medmemory.ai';
  const password = process.env.E2E_PASSWORD || 'demo-password';

  await login(page, email, password);
  await selectFirstPatient(page);
});
