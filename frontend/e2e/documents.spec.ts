import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test, expect } from '@playwright/test';
import { login } from './fixtures';

test('user can upload a document', async ({ page }) => {
  const email = process.env.E2E_EMAIL || 'demo@medmemory.ai';
  const password = process.env.E2E_PASSWORD || 'demo-password';

  page.on('console', msg => console.log(`[Browser] ${msg.type()}: ${msg.text()}`));

  await login(page, email, password);
  await page.getByRole('tab', { name: /dashboard/i }).click();
  await expect(page.locator('.panel.documents h2')).toBeVisible({ timeout: 15000 });

  const dashboardHeader = page.locator('.dashboard-header h1');
  await expect(dashboardHeader).toBeVisible({ timeout: 10000 });
  await expect(dashboardHeader).not.toHaveText('Your health dashboard', { timeout: 15000 });
  await page.waitForTimeout(500);

  const dirname = path.dirname(fileURLToPath(import.meta.url));
  const filePath = path.resolve(dirname, 'sample-report.txt');

  const uploadInput = page.locator('#document-upload');
  await uploadInput.setInputFiles(filePath);
  await expect(page.locator('.file-pill')).toContainText('sample-report.txt', { timeout: 5000 });

  const uploadButton = page.getByRole('button', { name: /upload document/i });
  await expect(uploadButton).toBeEnabled({ timeout: 5000 });
  await uploadButton.click();

  const status = page.locator('.status-text');
  await expect(status).toBeVisible({ timeout: 15000 });
  await expect(status).toContainText(/upload complete|already uploaded/i, { timeout: 15000 });
  await expect(page.locator('.document-row').filter({ hasText: 'sample-report.txt' })).toBeVisible({ timeout: 5000 });
});
