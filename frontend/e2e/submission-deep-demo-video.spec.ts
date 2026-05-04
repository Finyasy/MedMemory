import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { login } from './fixtures';

const API_BASE = process.env.E2E_API_BASE_URL || 'http://localhost:8000';
const PATIENT_EMAIL = process.env.E2E_EMAIL || 'demo@medmemory.ai';
const PATIENT_PASSWORD = process.env.E2E_PASSWORD || 'demo-password';
const CLINICIAN_EMAIL = process.env.E2E_CLINICIAN_EMAIL || 'qa.clinician+20260218@example.com';
const CLINICIAN_PASSWORD = process.env.E2E_CLINICIAN_PASSWORD || 'DemoPass123!';
const CLINICIAN_NAME = process.env.E2E_CLINICIAN_NAME || 'Dr QA Clinician';
const CLINICIAN_REG = process.env.E2E_CLINICIAN_REG || 'REG-2026-001';

const jsonHeaders = { 'Content-Type': 'application/json' };

test.use({
  video: 'on',
  trace: 'off',
  screenshot: 'off',
  viewport: { width: 1440, height: 900 },
});

const pause = async (page: Page, ms: number) => {
  await page.waitForTimeout(ms);
};

const waitForChatResponse = async (page: Page, prompt: string, settleMs = 7000) => {
  const assistantMessages = page.locator('.message.message-assistant');
  const beforeCount = await assistantMessages.count();
  const input = page.getByTestId('chat-input');
  const send = page.getByTestId('chat-send');

  const responsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST'
      && (response.url().includes('/api/v1/chat/ask') || response.url().includes('/api/v1/chat/stream')),
    { timeout: 120_000 },
  );

  await input.fill(prompt);
  await pause(page, 800);
  await send.click();
  await responsePromise;
  await expect(assistantMessages).toHaveCount(beforeCount + 1, { timeout: 120_000 });
  const latest = assistantMessages.nth(beforeCount).locator('.message-text');
  await expect.poll(async () => (await latest.innerText()).trim().length, { timeout: 120_000 })
    .toBeGreaterThan(0);
  await expect(input).toBeEnabled({ timeout: 120_000 });
  await pause(page, settleMs);
};

const getToken = async (
  request: APIRequestContext,
  path: string,
  payload: Record<string, string>,
): Promise<string> => {
  const res = await request.post(`${API_BASE}${path}`, { headers: jsonHeaders, data: payload });
  expect(res.ok(), `${path} failed (${res.status()})`).toBeTruthy();
  const body = (await res.json()) as { access_token?: string };
  expect(body.access_token).toBeTruthy();
  return body.access_token as string;
};

const ensureClinicianAccount = async (request: APIRequestContext): Promise<void> => {
  const signup = await request.post(`${API_BASE}/api/v1/clinician/signup`, {
    headers: jsonHeaders,
    data: {
      email: CLINICIAN_EMAIL,
      password: CLINICIAN_PASSWORD,
      full_name: CLINICIAN_NAME,
      registration_number: CLINICIAN_REG,
    },
  });
  if (signup.ok()) return;
  expect([400, 409]).toContain(signup.status());
};

const ensureClinicianHasActivePatient = async (request: APIRequestContext): Promise<void> => {
  await ensureClinicianAccount(request);
  const clinicianToken = await getToken(request, '/api/v1/clinician/login', {
    email: CLINICIAN_EMAIL,
    password: CLINICIAN_PASSWORD,
  });
  const patientToken = await getToken(request, '/api/v1/auth/login', {
    email: PATIENT_EMAIL,
    password: PATIENT_PASSWORD,
  });

  const patientListRes = await request.get(`${API_BASE}/api/v1/patients/?limit=100`, {
    headers: { Authorization: `Bearer ${patientToken}` },
  });
  expect(patientListRes.ok()).toBeTruthy();
  const patientList = (await patientListRes.json()) as Array<{ id: number }>;
  expect(patientList.length).toBeGreaterThan(0);
  const patientId = patientList[0].id;

  await request.post(`${API_BASE}/api/v1/clinician/access/request`, {
    headers: { ...jsonHeaders, Authorization: `Bearer ${clinicianToken}` },
    data: { patient_id: patientId },
  });

  const requestsRes = await request.get(`${API_BASE}/api/v1/patient/access/requests`, {
    headers: { Authorization: `Bearer ${patientToken}` },
  });
  expect(requestsRes.ok()).toBeTruthy();
  const requests = (await requestsRes.json()) as Array<{
    grant_id: number;
    patient_id: number;
    clinician_email: string;
    status: string;
  }>;
  const clinicianRequest = requests.find(
    (entry) => entry.patient_id === patientId && entry.clinician_email === CLINICIAN_EMAIL,
  );
  expect(clinicianRequest).toBeTruthy();

  if (clinicianRequest?.status === 'pending') {
    const grantRes = await request.post(`${API_BASE}/api/v1/patient/access/grant`, {
      headers: { ...jsonHeaders, Authorization: `Bearer ${patientToken}` },
      data: { grant_id: clinicianRequest.grant_id },
    });
    expect(grantRes.ok()).toBeTruthy();
  }
};

const clinicianLogin = async (page: Page) => {
  await page.goto('/clinician');
  await page.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => {});

  const signInButton = page.getByRole('button', { name: /^Sign in$/i });
  if ((await signInButton.count()) > 0) {
    await page.getByRole('textbox', { name: 'Email' }).fill(CLINICIAN_EMAIL);
    await page.getByRole('textbox', { name: /Password/i }).fill(CLINICIAN_PASSWORD);
    await pause(page, 700);
    await signInButton.click();
  }

  await expect(page.getByRole('heading', { name: 'Clinician Portal' })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole('button', { name: /Dr QA Clinician/i })).toBeVisible({ timeout: 20_000 });
};

test('submission deep demo video: patient + clinician portals', async ({ page, request }) => {
  test.setTimeout(10 * 60_000);

  await ensureClinicianHasActivePatient(request);

  await page.goto('/');
  await page.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => {});
  await pause(page, 5000);

  await login(page, PATIENT_EMAIL, PATIENT_PASSWORD);
  await pause(page, 5000);

  await page.getByRole('tab', { name: /dashboard/i }).click();
  const dashboardHeader = page.locator('.dashboard-header h1');
  await expect(dashboardHeader).toBeVisible({ timeout: 30_000 });
  await expect(dashboardHeader).not.toHaveText('Your health dashboard', { timeout: 30_000 });
  await pause(page, 8000);

  await page.mouse.wheel(0, 700);
  await pause(page, 5000);
  await page.mouse.wheel(0, 700);
  await pause(page, 5000);
  await page.mouse.wheel(0, -1400);
  await pause(page, 4000);

  await page.getByRole('tab', { name: 'Chat' }).click();
  await expect(page.getByTestId('chat-input')).toBeVisible({ timeout: 20_000 });
  await pause(page, 4000);

  await waitForChatResponse(page, 'What are the recent labs in my records?', 9000);
  await waitForChatResponse(page, 'Which medication is marked as discontinued?', 9000);
  await waitForChatResponse(page, 'Do my records show conflicting TB screening results?', 9000);

  await page.getByRole('tab', { name: /dashboard/i }).click();
  await pause(page, 6000);

  await clinicianLogin(page);
  await pause(page, 6000);

  const quickActions = page.getByRole('region', { name: 'Clinician quick actions' });
  await expect(quickActions).toBeVisible({ timeout: 20_000 });
  await pause(page, 4000);

  const refreshQueueButton = quickActions.getByRole('button', { name: 'Refresh queue' });
  const refreshPatients = page.waitForResponse(
    (response) => response.url().includes('/api/v1/clinician/patients') && response.request().method() === 'GET',
    { timeout: 20_000 },
  );
  const refreshUploads = page.waitForResponse(
    (response) => response.url().includes('/api/v1/clinician/uploads?limit=50') && response.request().method() === 'GET',
    { timeout: 20_000 },
  );
  await refreshQueueButton.click();
  expect((await refreshPatients).ok()).toBeTruthy();
  expect((await refreshUploads).ok()).toBeTruthy();
  await pause(page, 5000);

  const checklistToggle = page.getByRole('button', { name: /Show checklist|Hide checklist/i });
  if (await checklistToggle.isVisible()) {
    await checklistToggle.click();
    await pause(page, 4000);
    await checklistToggle.click();
    await pause(page, 3000);
  }

  const queueDetailsToggle = page.getByRole('button', { name: /Show queue details|Hide queue details/i });
  if (await queueDetailsToggle.isVisible()) {
    await queueDetailsToggle.click();
    await pause(page, 5000);
  }

  await quickActions.getByRole('button', { name: 'Open first active patient' }).click();
  await expect(page.getByRole('button', { name: 'Change patient' })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText('Loading…')).toHaveCount(0, { timeout: 20_000 });
  await pause(page, 8000);

  await page.mouse.wheel(0, 500);
  await pause(page, 4000);
  await page.mouse.wheel(0, -500);
  await pause(page, 3000);

  const clinicianChatInput = page.getByRole('textbox', { name: 'Message MedMemory...' });
  await expect(clinicianChatInput).toBeVisible({ timeout: 20_000 });
  await waitForChatResponse(page, 'Latest hemoglobin value in documents, cite source.', 9000);

  await pause(page, 7000);
});
