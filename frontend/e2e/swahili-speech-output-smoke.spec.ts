import { expect, test, type Page } from '@playwright/test';
import { login } from './fixtures';

const normalizeText = (value: string | null | undefined) =>
  (value ?? '').replace(/\s+/g, ' ').trim();

async function switchPatientChatToSwahili(page: Page) {
  const languageSelect = page.getByTestId('chat-language-select');
  await expect(languageSelect).toBeVisible({ timeout: 15_000 });
  await page.waitForLoadState('networkidle').catch(() => {});
  await languageSelect.selectOption('sw');
  await expect.poll(async () => languageSelect.inputValue(), { timeout: 10_000 }).toBe('sw');
}

async function enableSpeechReplies(page: Page) {
  const speechToggle = page.getByRole('checkbox', { name: /soma majibu kwa sauti/i });
  await expect(speechToggle).toBeVisible({ timeout: 15_000 });
  if (!(await speechToggle.isChecked())) {
    await speechToggle.check();
  }
  await expect(speechToggle).toBeChecked();
}

test.describe('patient chat Swahili speech-output smoke', () => {
  test('streams a Swahili refusal reply and fetches the generated speech asset', async ({
    page,
  }) => {
    test.slow();

    const email = process.env.E2E_EMAIL || 'demo@medmemory.ai';
    const password = process.env.E2E_PASSWORD || 'demo-password';

    await login(page, email, password);
    await switchPatientChatToSwahili(page);
    await enableSpeechReplies(page);

    const assistantMessages = page.locator('.message.message-assistant .message-text');
    const beforeCount = await assistantMessages.count();

    const chatResponsePromise = page.waitForResponse(
      (response) =>
        response.url().includes('/api/v1/chat/stream') &&
        response.request().method() === 'POST' &&
        response.request().url().includes('response_mode=both') &&
        response.request().url().includes('output_language=sw'),
      { timeout: 60_000 },
    );
    const speechAssetPromise = page.waitForResponse(
      (response) =>
        response.url().includes('/api/v1/speech/assets/') &&
        response.request().method() === 'GET' &&
        response.status() === 200,
      { timeout: 60_000 },
    );

    await page.getByTestId('chat-input').fill('what is my pulse rate');
    await page.getByTestId('chat-send').click();

    const chatResponse = await chatResponsePromise;
    expect(chatResponse.ok()).toBeTruthy();

    const reply = assistantMessages.nth(beforeCount);
    await expect(reply).toBeVisible({ timeout: 60_000 });
    await expect
      .poll(async () => normalizeText(await reply.textContent()), { timeout: 60_000 })
      .toMatch(/hati hairekodi mapigo yako ya moyo/i);

    await expect(page.getByTestId('message-speak-button').last()).toBeVisible({
      timeout: 15_000,
    });

    const speechAssetResponse = await speechAssetPromise;
    expect(speechAssetResponse.ok()).toBeTruthy();
  });
});
