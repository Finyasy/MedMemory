import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

const API_BASE = process.env.E2E_API_BASE_URL || 'http://localhost:8000';
const PATIENT_EMAIL = process.env.E2E_EMAIL || 'demo@medmemory.ai';
const PATIENT_PASSWORD = process.env.E2E_PASSWORD || 'demo-password';
const CLINICIAN_EMAIL = process.env.E2E_CLINICIAN_EMAIL || 'qa.clinician+20260218@example.com';
const CLINICIAN_PASSWORD = process.env.E2E_CLINICIAN_PASSWORD || 'DemoPass123!';
const CLINICIAN_NAME = process.env.E2E_CLINICIAN_NAME || 'Dr QA Clinician';
const CLINICIAN_REG = process.env.E2E_CLINICIAN_REG || 'REG-2026-001';

type AccessRequest = {
  grant_id: number;
  patient_id: number;
  clinician_email: string;
  status: string;
};

const jsonHeaders = { 'Content-Type': 'application/json' };

const getToken = async (
  request: APIRequestContext,
  path: string,
  payload: Record<string, string>,
): Promise<string> => {
  const res = await request.post(`${API_BASE}${path}`, {
    headers: jsonHeaders,
    data: payload,
  });
  expect(res.ok(), `${path} failed (${res.status()})`).toBeTruthy();
  const body = (await res.json()) as { access_token?: string };
  expect(body.access_token, `Missing access token from ${path}`).toBeTruthy();
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
  expect(
    signup.status() === 400 || signup.status() === 409,
    `Unexpected clinician signup status ${signup.status()}`,
  ).toBeTruthy();
};

const ensureClinicianHasActivePatient = async (request: APIRequestContext): Promise<number> => {
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
  expect(patientListRes.ok(), `List patients failed (${patientListRes.status()})`).toBeTruthy();
  const patientList = (await patientListRes.json()) as Array<{ id: number }>;
  expect(patientList.length > 0, 'No patient available for clinician smoke test').toBeTruthy();
  const patientId = patientList[0].id;

  await request.post(`${API_BASE}/api/v1/clinician/access/request`, {
    headers: { ...jsonHeaders, Authorization: `Bearer ${clinicianToken}` },
    data: { patient_id: patientId },
  });

  const requestsRes = await request.get(`${API_BASE}/api/v1/patient/access/requests`, {
    headers: { Authorization: `Bearer ${patientToken}` },
  });
  expect(requestsRes.ok(), `List patient access requests failed (${requestsRes.status()})`).toBeTruthy();
  const requests = (await requestsRes.json()) as AccessRequest[];

  const clinicianRequest = requests.find(
    (entry) => entry.patient_id === patientId && entry.clinician_email === CLINICIAN_EMAIL,
  );
  expect(clinicianRequest, 'No access request found for clinician').toBeTruthy();

  if (clinicianRequest && clinicianRequest.status === 'pending') {
    const grantRes = await request.post(`${API_BASE}/api/v1/patient/access/grant`, {
      headers: { ...jsonHeaders, Authorization: `Bearer ${patientToken}` },
      data: { grant_id: clinicianRequest.grant_id },
    });
    expect(grantRes.ok(), `Grant patient access failed (${grantRes.status()})`).toBeTruthy();
  }

  return patientId;
};

const ensureClinicianLoggedIn = async (page: Page): Promise<void> => {
  await page.goto('/clinician');
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});

  const signInButton = page.getByRole('button', { name: /^Sign in$/i });
  if ((await signInButton.count()) === 0) {
    await expect(page.getByRole('heading', { name: 'Clinician Portal' })).toBeVisible();
    return;
  }

  await page.getByRole('textbox', { name: 'Email' }).fill(CLINICIAN_EMAIL);
  await page.getByRole('textbox', { name: /Password/i }).fill(CLINICIAN_PASSWORD);
  await signInButton.click();
  await expect(page.getByRole('heading', { name: 'Clinician Portal' })).toBeVisible({ timeout: 15000 });
  await expect(page.getByRole('button', { name: /Dr QA Clinician/i })).toBeVisible({ timeout: 15000 });
};

test.describe.configure({ mode: 'serial' });

test('clinician portal smoke: stable workspace loading and key actions', async ({ page, request }) => {
  await ensureClinicianHasActivePatient(request);
  await ensureClinicianLoggedIn(page);

  const quickActions = page.getByRole('region', { name: 'Clinician quick actions' });
  await expect(quickActions).toBeVisible();
  const linkPatientButton = quickActions.getByRole('button', { name: 'Link patient' });
  const refreshQueueButton = quickActions.getByRole('button', { name: 'Refresh queue' });
  const quickOpenPatient = quickActions.getByRole('button', { name: 'Open first active patient' });
  await expect(linkPatientButton).toBeEnabled();
  await expect(refreshQueueButton).toBeEnabled();
  await expect(quickOpenPatient).toBeEnabled();

  await linkPatientButton.click();
  const patientIdInput = page.getByRole('spinbutton', { name: 'Patient ID' });
  await expect(patientIdInput).toBeFocused();

  const refreshPatients = page.waitForResponse(
    (response) => response.url().includes('/api/v1/clinician/patients') && response.request().method() === 'GET',
    { timeout: 15000 },
  );
  const refreshUploads = page.waitForResponse(
    (response) => response.url().includes('/api/v1/clinician/uploads?limit=50') && response.request().method() === 'GET',
    { timeout: 15000 },
  );
  await refreshQueueButton.click();
  expect((await refreshPatients).ok()).toBeTruthy();
  expect((await refreshUploads).ok()).toBeTruthy();

  const checklistToggle = page.getByRole('button', { name: /Show checklist|Hide checklist/i });
  await expect(checklistToggle).toBeVisible();
  await checklistToggle.click();
  await expect(page.getByLabel('Workspace setup progress')).toBeVisible();
  await checklistToggle.click();
  await expect(page.getByLabel('Workspace setup progress')).toHaveCount(0);

  const queueDetailsToggle = page.getByRole('button', { name: /Show queue details|Hide queue details/i });
  await expect(queueDetailsToggle).toBeVisible();
  await queueDetailsToggle.click();
  await expect(page.getByRole('button', { name: /Hide queue details/i })).toBeVisible();

  let docRequestCount = 0;
  let recordRequestCount = 0;
  page.on('request', (req) => {
    const url = req.url();
    if (url.includes('/api/v1/clinician/patient/') && url.includes('/documents')) {
      docRequestCount += 1;
    }
    if (url.includes('/api/v1/clinician/patient/') && url.includes('/records')) {
      recordRequestCount += 1;
    }
  });

  await quickOpenPatient.click();
  await expect(page.getByRole('button', { name: 'Change patient' })).toBeVisible({ timeout: 15000 });
  await expect(page.getByText('Loading…')).toHaveCount(0, { timeout: 15000 });

  await page.waitForTimeout(2500);
  expect(docRequestCount).toBeLessThanOrEqual(6);
  expect(recordRequestCount).toBeLessThanOrEqual(6);

  await expect(page.getByRole('heading', { name: 'Documents' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Records' })).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Message MedMemory...' })).toBeVisible();

  await page.getByRole('button', { name: 'Change patient' }).click();
  await expect(quickOpenPatient).toBeVisible();
});
