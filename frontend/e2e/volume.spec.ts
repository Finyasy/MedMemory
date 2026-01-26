import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test, expect } from '@playwright/test';
import { login } from './fixtures';

test.setTimeout(180000);

test('user can upload a volume zip for analysis', async ({ page }) => {
  const email = process.env.E2E_EMAIL || 'demo@medmemory.ai';
  const password = process.env.E2E_PASSWORD || 'demo-password';

  page.on('console', msg => console.log(`[Browser] ${msg.type()}: ${msg.text()}`));

  await login(page, email, password);
  await expect(page.getByTestId('chat-input')).toBeVisible({ timeout: 15000 });
  await expect(page.getByTestId('chat-input')).toBeEnabled({ timeout: 15000 });

  const uploadButton = page.locator('button[aria-label*="Upload image"]');
  await expect(uploadButton).toBeEnabled({ timeout: 10000 });

  const dirname = path.dirname(fileURLToPath(import.meta.url));
  const zipPath = path.resolve(dirname, 'volume-slices.zip');

  const volumeResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes('/api/v1/chat/volume') &&
      response.request().method() === 'POST',
    { timeout: 120000 },
  );

  const fileChooserPromise = page.waitForEvent('filechooser');
  await uploadButton.click();
  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles(zipPath);

  const volumeResponse = await volumeResponsePromise;
  if (!volumeResponse.ok()) {
    const body = await volumeResponse.text();
    throw new Error(`Volume upload failed: ${volumeResponse.status()} ${body}`);
  }

  const lastAssistant = page.locator('.message.message-assistant .message-text').last();
  await expect.poll(async () => {
    const text = (await lastAssistant.textContent()) || '';
    return text.trim().length;
  }, { timeout: 60000 }).toBeGreaterThan(0);
});
