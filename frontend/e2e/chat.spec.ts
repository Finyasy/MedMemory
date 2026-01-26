import { test, expect } from '@playwright/test';
import { login } from './fixtures';

test('user can ask a question in chat', async ({ page }) => {
  const email = process.env.E2E_EMAIL || 'demo@medmemory.ai';
  const password = process.env.E2E_PASSWORD || 'demo-password';

  await login(page, email, password);

  const input = page.getByTestId('chat-input');
  await input.fill('What are the recent labs?');
  await page.getByTestId('chat-send').click();

  await expect(page.getByText(/recent labs/i)).toBeVisible();
});
