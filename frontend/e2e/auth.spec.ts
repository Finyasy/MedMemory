import { test, expect } from '@playwright/test';
import { login } from './fixtures';

test('user can log in and see the chat screen', async ({ page }) => {
  const email = process.env.E2E_EMAIL || 'demo@medmemory.ai';
  const password = process.env.E2E_PASSWORD || 'demo-password';

  await login(page, email, password);
  await expect(page.getByTestId('chat-input')).toBeVisible();
});
