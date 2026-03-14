import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

const API_BASE = process.env.E2E_API_BASE_URL || 'http://localhost:8000';
const PATIENT_EMAIL = process.env.E2E_EMAIL || 'demo@medmemory.ai';
const PATIENT_PASSWORD = process.env.E2E_PASSWORD || 'demo-password';
const CLINICIAN_EMAIL = process.env.E2E_CLINICIAN_EMAIL || 'qa.clinician+20260218@example.com';
const CLINICIAN_PASSWORD = process.env.E2E_CLINICIAN_PASSWORD || 'DemoPass123!';
const CLINICIAN_NAME = process.env.E2E_CLINICIAN_NAME || 'Dr QA Clinician';
const CLINICIAN_REG = process.env.E2E_CLINICIAN_REG || 'REG-2026-001';
const CHART_REVIEW_PROMPT = 'Review this chart and surface the most important evidence for a clinician handoff.';

type AccessRequest = {
  grant_id: number;
  patient_id: number;
  clinician_email: string;
  status: string;
};

type CopilotSuggestion = {
  action_label?: string | null;
  action_target?: string | null;
};

type CopilotRun = {
  id: number;
  suggestions: CopilotSuggestion[];
};

const seedConnectionAttentionState = async (
  request: APIRequestContext,
  clinicianToken: string,
  patientId: number,
): Promise<void> => {
  const upsertConnection = async (providerName: string, providerSlug: string, payload: Record<string, unknown>) => {
    const res = await request.post(`${API_BASE}/api/v1/dashboard/patient/${patientId}/connections`, {
      headers: { ...jsonHeaders, Authorization: `Bearer ${clinicianToken}` },
      data: {
        provider_name: providerName,
        provider_slug: providerSlug,
        ...payload,
      },
    });
    expect(res.ok(), `Upsert connection ${providerSlug} failed (${res.status()})`).toBeTruthy();
  };

  await upsertConnection('Kenya Health Information System (KHIS)', 'kenya_health_information_system_khis', {
    status: 'error',
    source_count: 2,
    last_error: 'Unauthorized bearer token for live FHIR sync',
    last_synced_at: new Date().toISOString(),
    is_active: true,
  });

  await upsertConnection('Digital Health Agency (DHA)', 'digital_health_agency_dha', {
    status: 'connected',
    source_count: 1,
    last_error: null,
    last_synced_at: new Date().toISOString(),
    is_active: true,
  });
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
    signup.status() === 400 || signup.status() === 409 || signup.status() === 429,
    `Unexpected clinician signup status ${signup.status()}`,
  ).toBeTruthy();
};

const ensureClinicianHasActivePatient = async (
  request: APIRequestContext,
): Promise<{ patientId: number; clinicianToken: string }> => {
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
  expect(patientList.length > 0, 'No patient available for clinician copilot smoke test').toBeTruthy();
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

  return { patientId, clinicianToken };
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
  await expect(page.getByRole('button', { name: /Dr QA Clinician/i })).toBeVisible({ timeout: 15000 });
};

test.describe.configure({ mode: 'serial' });

test('clinician copilot smoke: persisted run renders and CTA performs safe navigation', async ({ page, request }) => {
  const { patientId, clinicianToken } = await ensureClinicianHasActivePatient(request);
  await seedConnectionAttentionState(request, clinicianToken, patientId);

  const runRes = await request.post(`${API_BASE}/api/v1/clinician/agent/runs`, {
    headers: { ...jsonHeaders, Authorization: `Bearer ${clinicianToken}` },
    data: {
      patient_id: patientId,
      template: 'chart_review',
      prompt: CHART_REVIEW_PROMPT,
    },
  });
  expect(runRes.ok(), `Create clinician copilot run failed (${runRes.status()})`).toBeTruthy();
  const run = (await runRes.json()) as CopilotRun;
  const suggestion = run.suggestions.find((item) => item.action_label && item.action_target);
  expect(suggestion, 'No navigable suggestion returned for copilot run').toBeTruthy();

  await page.setViewportSize({ width: 1440, height: 800 });
  await ensureClinicianLoggedIn(page);

  const quickOpenPatient = page.getByRole('button', { name: 'Open first active patient' });
  await expect(quickOpenPatient).toBeVisible();
  await quickOpenPatient.click();

  await expect(page.getByText('Clinician Copilot')).toBeVisible({ timeout: 15000 });
  await expect(page.getByRole('tab', { name: 'Latest run' })).toBeVisible({ timeout: 15000 });
  await expect(page.getByRole('tab', { name: 'History' })).toBeVisible({ timeout: 15000 });
  await expect(page.getByRole('tab', { name: 'Trace' })).toBeVisible({ timeout: 15000 });

  await page.getByRole('tab', { name: 'Trace' }).click();
  await expect(page.getByText('Run trace')).toBeVisible({ timeout: 15000 });
  await page.getByRole('tab', { name: 'Latest run' }).click();

  const connectionsSection = page.locator('section').filter({
    has: page.getByRole('heading', { name: 'Connections' }),
  });
  await expect(connectionsSection.getByText(/need review/i)).toBeVisible();
  const reviewBadge = connectionsSection.getByRole('button', { name: /Open .*connection items needing review/i });
  await expect(reviewBadge).toBeVisible();
  await reviewBadge.click();
  const providerConnectionsList = connectionsSection.locator('.clinician-panel-list').first();
  await expect(connectionsSection.getByRole('button', { name: 'Show all' })).toBeVisible();
  await expect(connectionsSection.getByRole('button', { name: 'Show all' })).toHaveAttribute('aria-pressed', 'true');
  await expect(providerConnectionsList.getByText('Kenya Health Information System (KHIS)')).toBeVisible();
  await expect(providerConnectionsList.getByText('Digital Health Agency (DHA)')).toHaveCount(0);
  await connectionsSection.getByRole('button', { name: 'Show all' }).click();
  await expect(connectionsSection.getByRole('button', { name: 'Attention only' })).toHaveAttribute('aria-pressed', 'false');
  await expect(providerConnectionsList.getByText('Digital Health Agency (DHA)')).toBeVisible();

  const panel = page.locator('.clinician-customer-panel');
  await panel.evaluate((element) => {
    element.scrollTo({ top: element.scrollHeight, behavior: 'auto' });
  });
  const beforeScrollTop = await panel.evaluate((element) => element.scrollTop);

  const actionLabel = suggestion?.action_label as string;
  await expect(page.getByRole('button', { name: actionLabel })).toBeVisible();
  await page.getByRole('button', { name: actionLabel }).click();

  if (suggestion?.action_target?.endsWith(':documents')) {
    await expect(page.getByRole('heading', { name: 'Documents' })).toBeVisible();
    const afterScrollTop = await panel.evaluate((element) => element.scrollTop);
    expect(afterScrollTop).toBeLessThanOrEqual(beforeScrollTop);
  } else if (suggestion?.action_target?.endsWith(':records')) {
    await expect(page.getByRole('heading', { name: 'Records' })).toBeVisible();
  } else if (suggestion?.action_target?.endsWith(':connections')) {
    await expect(page.getByRole('heading', { name: 'Connections' })).toBeVisible();
  } else if (suggestion?.action_target?.endsWith(':panel')) {
    await expect(page.getByText(`ID: ${patientId}`)).toBeVisible();
  } else if (suggestion?.action_target?.endsWith(':workspace')) {
    await expect(page.getByRole('textbox', { name: 'Message MedMemory...' })).toBeVisible();
  }
});
