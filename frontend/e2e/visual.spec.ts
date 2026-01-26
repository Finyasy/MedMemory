import { test, expect } from '@playwright/test';
import { login } from './fixtures';

test('landing login modal matches baseline', async ({ page }) => {
  await page.goto('/');
  await page.addStyleTag({
    content: `*, *::before, *::after { animation: none !important; transition: none !important; }`,
  });
  await page.getByTestId('open-login').click();
  const modal = page.getByRole('dialog', { name: /log in/i });
  await expect(modal).toBeVisible();
  await expect(modal).toHaveScreenshot('login-modal.png');
});

test('dashboard header matches baseline', async ({ page }) => {
  const email = process.env.E2E_EMAIL || 'demo@medmemory.ai';
  const password = process.env.E2E_PASSWORD || 'demo-password';

  await page.addStyleTag({
    content: `*, *::before, *::after { animation: none !important; transition: none !important; }`,
  });
  await login(page, email, password);
  await page.getByRole('tab', { name: /dashboard/i }).click();
  const header = page.locator('.dashboard-header');
  await expect(header).toBeVisible();
  await expect(header).toHaveScreenshot('dashboard-header.png');
});

test('chat composer matches baseline', async ({ page }) => {
  const email = process.env.E2E_EMAIL || 'demo@medmemory.ai';
  const password = process.env.E2E_PASSWORD || 'demo-password';

  await page.addStyleTag({
    content: `*, *::before, *::after { animation: none !important; transition: none !important; }`,
  });
  await login(page, email, password);
  const composer = page.locator('.chat-input-container');
  await expect(composer).toBeVisible();
  await expect(composer).toHaveScreenshot('chat-composer.png');
});

test('documents panel matches baseline', async ({ page }) => {
  const email = process.env.E2E_EMAIL || 'demo@medmemory.ai';
  const password = process.env.E2E_PASSWORD || 'demo-password';

  await page.addStyleTag({
    content: `*, *::before, *::after { animation: none !important; transition: none !important; }`,
  });
  await login(page, email, password);
  await page.getByRole('tab', { name: /dashboard/i }).click();
  const documentsPanel = page.locator('.panel.documents');
  await expect(documentsPanel).toBeVisible();
  await expect(documentsPanel).toHaveScreenshot('documents-panel.png');
});
