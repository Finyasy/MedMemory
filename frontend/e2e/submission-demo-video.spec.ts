import { expect, test, type Page } from '@playwright/test';

test.use({
  video: 'on',
  trace: 'off',
  screenshot: 'off',
  viewport: { width: 1440, height: 900 },
});

const pause = async (page: Page, ms: number) => {
  await page.waitForTimeout(ms);
};

const sendChatMessage = async (page: Page, prompt: string, waitAfterMs = 4000) => {
  const assistantMessages = page.locator('.message.message-assistant');
  const beforeCount = await assistantMessages.count();

  const input = page.getByTestId('chat-input');
  const sendButton = page.getByTestId('chat-send');

  const responsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST'
      && (
        response.url().includes('/api/v1/chat/ask')
        || response.url().includes('/api/v1/chat/stream')
      ),
    { timeout: 120_000 },
  );

  await input.click();
  await input.fill(prompt);
  await pause(page, 500);
  await sendButton.click();

  await responsePromise;
  await expect(assistantMessages).toHaveCount(beforeCount + 1, { timeout: 120_000 });
  const newMessage = assistantMessages.nth(beforeCount).locator('.message-text');
  await expect.poll(async () => (await newMessage.innerText()).trim().length, { timeout: 120_000 })
    .toBeGreaterThan(0);
  await expect(input).toBeEnabled({ timeout: 120_000 });
  await pause(page, waitAfterMs);
};

test('submission demo video: patient dashboard + chat walkthrough', async ({ page }) => {
  test.setTimeout(8 * 60_000);

  const email = process.env.E2E_EMAIL || 'demo@medmemory.ai';
  const password = process.env.E2E_PASSWORD || 'demo-password';

  await page.goto('/');
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
  await pause(page, 2500);

  await page.getByTestId('open-login').click();
  await pause(page, 1200);

  await page.getByTestId('login-email').fill(email);
  await page.getByTestId('login-password').fill(password);

  const loginResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes('/api/v1/auth/login') && response.request().method() === 'POST',
    { timeout: 45_000 },
  );
  await page.getByTestId('login-submit').click();
  const loginResponse = await loginResponsePromise;
  expect(loginResponse.ok()).toBeTruthy();

  await expect(page.getByTestId('user-menu')).toBeVisible({ timeout: 20_000 });
  await pause(page, 2500);

  await page.getByRole('tab', { name: /dashboard/i }).click();
  const dashboardHeader = page.locator('.dashboard-header h1');
  await expect(dashboardHeader).toBeVisible({ timeout: 30_000 });
  await pause(page, 3500);

  await page.mouse.wheel(0, 500);
  await pause(page, 1500);
  await page.mouse.wheel(0, -500);
  await pause(page, 1500);

  await page.getByRole('tab', { name: 'Chat' }).click();
  await pause(page, 2500);

  await sendChatMessage(page, 'What are the recent labs?', 4500);
  await pause(page, 2500);

  await sendChatMessage(page, 'Which medication is marked as discontinued?', 4500);
  await pause(page, 3000);

  await page.getByRole('tab', { name: /dashboard/i }).click();
  await pause(page, 3000);
  await pause(page, 1000);
});
