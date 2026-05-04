import { test, expect, type Page } from '@playwright/test';
import { login } from './fixtures';

const normalizeText = (value: string | null | undefined) =>
  (value ?? '').replace(/\s+/g, ' ').trim();

async function switchPatientChatToSwahili(page: Page) {
  const languageSelect = page.getByTestId('chat-language-select');
  await expect(languageSelect).toBeVisible({ timeout: 15_000 });
  await page.waitForLoadState('networkidle').catch(() => {});
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await languageSelect.selectOption('sw');
    await page.waitForTimeout(500);
    if ((await languageSelect.inputValue()) === 'sw') {
      break;
    }
  }
  await expect.poll(async () => languageSelect.inputValue(), { timeout: 10_000 }).toBe('sw');
}

async function askQuestion(page: Page, question: string) {
  const assistantMessages = page.locator('.message.message-assistant .message-text');
  const beforeCount = await assistantMessages.count();
  const usesStructuredPath = /most recent document|latest document|summarize|summary|overview|findings/i.test(question);
  const expectedPath = usesStructuredPath ? '/api/v1/chat/ask' : '/api/v1/chat/stream';
  const responsePromise = page.waitForResponse(
    (response) =>
      response.url().includes(expectedPath) &&
      response.request().method() === 'POST',
    { timeout: 60_000 }
  );

  await page.getByTestId('chat-input').fill(question);
  await page.getByTestId('chat-send').click();

  const response = await responsePromise;
  expect(response.ok()).toBeTruthy();

  const reply = assistantMessages.nth(beforeCount);
  await expect(reply).toBeVisible({ timeout: 60_000 });
  await expect
    .poll(async () => normalizeText(await reply.textContent()).length, { timeout: 60_000 })
    .toBeGreaterThan(0);

  return {
    status: response.status(),
    text: normalizeText(await reply.textContent()),
  };
}

test.describe('patient chat Swahili refusal smoke', () => {
  test.beforeEach(async ({ page }) => {
    const email = process.env.E2E_EMAIL || 'demo@medmemory.ai';
    const password = process.env.E2E_PASSWORD || 'demo-password';

    await login(page, email, password);
    await switchPatientChatToSwahili(page);
  });

  test('renders Swahili record refusal text', async ({ page }) => {
    test.slow();

    const result = await askQuestion(page, 'what is my pulse rate');

    expect(result.status).toBe(200);
    await expect(page.locator('.message.message-assistant .message-text').last()).toContainText(
      /hati hairekodi mapigo yako ya moyo/i
    );
  });

  test('renders Swahili latest-document refusal text', async ({ page }) => {
    test.slow();

    const result = await askQuestion(page, 'Summarize the most recent document using only explicit values.');

    expect(result.status).toBe(200);
    await expect(page.locator('.message.message-assistant .message-text').last()).toContainText(
      /sikuweza kufupisha hati ya hivi karibuni/i
    );
    await expect(page.locator('.message.message-assistant .message-text').last()).toContainText(
      /tafadhali pakia hati au subiri uchakataji ukamilike/i
    );
  });
});
