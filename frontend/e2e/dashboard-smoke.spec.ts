import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { login } from './fixtures';

const E2E_EMAIL = process.env.E2E_EMAIL || 'demo@medmemory.ai';
const E2E_PASSWORD = process.env.E2E_PASSWORD || 'demo-password';
const E2E_API_BASE_URL = process.env.E2E_API_BASE_URL || 'http://localhost:8000';
const SMOKE_RECORD_PREFIX = 'Playwright smoke record';

type RecordResponse = {
  id: number;
  title: string;
};

const loginApi = async (request: APIRequestContext): Promise<string> => {
  const response = await request.post(`${E2E_API_BASE_URL}/api/v1/auth/login`, {
    data: { email: E2E_EMAIL, password: E2E_PASSWORD },
  });
  expect(response.ok(), `API login failed: ${response.status()}`).toBeTruthy();
  const body = (await response.json()) as { access_token?: string };
  expect(body.access_token, 'Missing access token from API login').toBeTruthy();
  return body.access_token as string;
};

const deleteSmokeRecords = async (request: APIRequestContext, token: string): Promise<void> => {
  const listResponse = await request.get(`${E2E_API_BASE_URL}/api/v1/records/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(listResponse.ok(), `List records failed: ${listResponse.status()}`).toBeTruthy();
  const records = (await listResponse.json()) as RecordResponse[];
  const smokeRecordIds = records
    .filter((record) => (record.title || '').startsWith(SMOKE_RECORD_PREFIX))
    .map((record) => record.id);

  for (const recordId of smokeRecordIds) {
    const deleteResponse = await request.delete(
      `${E2E_API_BASE_URL}/api/v1/records/${recordId}`,
      {
        headers: { Authorization: `Bearer ${token}` },
      },
    );
    expect(
      deleteResponse.status() === 204 || deleteResponse.status() === 200,
      `Delete record ${recordId} failed: ${deleteResponse.status()}`,
    ).toBeTruthy();
  }
};

const ensureProviderPickerOpen = async (page: Page): Promise<void> => {
  const providerToggle = page
    .getByRole('button', { name: /Add first provider|Connect provider|Hide providers/i })
    .first();
  await expect(providerToggle).toBeVisible({ timeout: 10000 });
  const currentLabel = (await providerToggle.innerText()).trim();
  if (!/Hide providers/i.test(currentLabel)) {
    await providerToggle.click();
  }
  await expect(page.getByRole('searchbox', { name: /Search providers/i })).toBeVisible({
    timeout: 10000,
  });
};

test.describe.configure({ mode: 'serial' });

test('dashboard smoke: core actions and grounded review flow', async ({ page, request }) => {
  const smokeRecordTitle = `${SMOKE_RECORD_PREFIX} ${Date.now()}`;

  try {
    await login(page, E2E_EMAIL, E2E_PASSWORD);

    await page.getByRole('tab', { name: /dashboard/i }).click();
    await expect(page.getByRole('tab', { name: 'Overview' })).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole('heading', { name: 'Data sources' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Focus areas' })).toBeVisible();

    await ensureProviderPickerOpen(page);

    const setupStepsToggle = page.getByRole('button', { name: /Show setup steps|Hide setup steps/i });
    await expect(setupStepsToggle).toBeVisible();
    const toggleLabel = (await setupStepsToggle.innerText()).trim();
    if (/Show setup steps/i.test(toggleLabel)) {
      await setupStepsToggle.click();
    }
    await expect(page.getByRole('heading', { name: 'Upload medical documents' })).toBeVisible();
    const hideSetupSteps = page.getByRole('button', { name: /Hide setup steps/i });
    if (await hideSetupSteps.isVisible()) {
      await hideSetupSteps.click();
    }
    await expect(page.getByRole('heading', { name: 'Upload medical documents' })).toHaveCount(0);

    await page.getByRole('tab', { name: 'Monitoring' }).click();
    const evaluateAlertsResponse = page.waitForResponse(
      (response) =>
        response.url().includes('/alerts/evaluate') && response.request().method() === 'POST',
      { timeout: 15000 },
    );
    await page.getByRole('button', { name: 'Evaluate now' }).click();
    const alertsResponse = await evaluateAlertsResponse;
    expect(alertsResponse.ok(), `Evaluate alerts failed: ${alertsResponse.status()}`).toBeTruthy();

    await page.getByRole('tab', { name: 'Workspace' }).click();
    await page.getByRole('textbox', { name: 'Record title' }).fill(smokeRecordTitle);
    await page.getByRole('textbox', { name: 'Summarize the clinical entry' }).fill(
      'Blood pressure 108/70 mmHg. Heart rate 72 bpm. Patient reports no acute symptoms.',
    );
    await page.getByRole('button', { name: 'Save Record' }).click();
    await expect(page.getByText('Record saved successfully.')).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(smokeRecordTitle)).toBeVisible({ timeout: 15000 });

    await page.getByRole('tab', { name: 'Overview' }).click();
    await expect(page.getByText(smokeRecordTitle)).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: 'Review in chat' }).click();

    await expect(page.getByRole('tab', { name: 'Chat' })).toBeVisible({ timeout: 10000 });
    const lastAssistantMessage = page.locator('.message.message-assistant .message-text').last();
    await expect(lastAssistantMessage).toContainText('Record summary from explicit note text:', {
      timeout: 15000,
    });
    await expect(lastAssistantMessage).toContainText(smokeRecordTitle, { timeout: 15000 });
    await expect(lastAssistantMessage).not.toContainText('I do not know from the available records.');
  } finally {
    try {
      const apiToken = await loginApi(request);
      await deleteSmokeRecords(request, apiToken);
    } catch (error) {
      console.warn('[dashboard-smoke] cleanup failed', error);
    }
  }
});
