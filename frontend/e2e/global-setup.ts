import type { FullConfig } from '@playwright/test';

async function globalSetup(_config: FullConfig) {
  void _config; // Config available for future use
  const apiBaseURL = process.env.E2E_API_BASE_URL || 'http://localhost:8000';
  const email = process.env.E2E_EMAIL || 'demo@medmemory.ai';
  const password = process.env.E2E_PASSWORD || 'demo-password';
  const fullName = process.env.E2E_FULL_NAME || 'Demo User';

  console.log(`[Global Setup] Ensuring test user exists: ${email}`);
  console.log(`[Global Setup] API Base URL: ${apiBaseURL}`);

  let accessToken: string | null = null;

  try {
    const healthCheck = await fetch(`${apiBaseURL}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(5000),
    }).catch(() => null);

    if (!healthCheck || !healthCheck.ok) {
      console.warn(`[Global Setup] ⚠ Backend health check failed at ${apiBaseURL}/health`);
    }

    const signupResponse = await fetch(`${apiBaseURL}/api/v1/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, full_name: fullName }),
      signal: AbortSignal.timeout(10000),
    });

    if (signupResponse.ok) {
      console.log(`[Global Setup] ✓ Test user created: ${email}`);
      const signupData = await signupResponse.json() as { access_token: string };
      accessToken = signupData.access_token;
    } else if (signupResponse.status === 400) {
      const body = await signupResponse.text();
      if (body.includes('already registered')) {
        console.log(`[Global Setup] ✓ Test user already exists: ${email}`);
        const loginResponse = await fetch(`${apiBaseURL}/api/v1/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
          signal: AbortSignal.timeout(10000),
        });
        if (loginResponse.ok) {
          const loginData = await loginResponse.json() as { access_token: string };
          accessToken = loginData.access_token;
        }
      } else {
        console.warn(`[Global Setup] ⚠ Signup failed: ${signupResponse.status} ${body}`);
      }
    } else {
      const body = await signupResponse.text();
      console.warn(`[Global Setup] ⚠ Unexpected signup response: ${signupResponse.status} ${body}`);
    }

    if (accessToken) {
      const testPatientFirstName = process.env.E2E_PATIENT_FIRST_NAME || 'Test';
      const testPatientLastName = process.env.E2E_PATIENT_LAST_NAME || 'Patient';

      const patientsResponse = await fetch(`${apiBaseURL}/api/v1/patients/?limit=100`, {
        method: 'GET',
        headers: { 'Authorization': `Bearer ${accessToken}` },
        signal: AbortSignal.timeout(10000),
      });

      if (patientsResponse.ok) {
        const patients = await patientsResponse.json();
        if (Array.isArray(patients) && patients.length > 0) {
          console.log(`[Global Setup] ✓ Test patient already exists (${patients.length} patient(s))`);
        } else {
          const createPatientResponse = await fetch(`${apiBaseURL}/api/v1/patients/`, {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${accessToken}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              first_name: testPatientFirstName,
              last_name: testPatientLastName,
              date_of_birth: '1990-01-01',
            }),
            signal: AbortSignal.timeout(10000),
          });

          if (createPatientResponse.ok) {
            const patient = await createPatientResponse.json() as { full_name?: string };
            console.log(`[Global Setup] ✓ Test patient created: ${patient.full_name || `${testPatientFirstName} ${testPatientLastName}`}`);
          } else {
            const body = await createPatientResponse.text();
            console.warn(`[Global Setup] ⚠ Failed to create test patient: ${createPatientResponse.status} ${body}`);
          }
        }
      } else {
        console.warn(`[Global Setup] ⚠ Failed to check for existing patients: ${patientsResponse.status}`);
      }
    }
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      console.error(`[Global Setup] ✗ Timeout connecting to backend at ${apiBaseURL}`);
    } else {
      console.error(`[Global Setup] ✗ Failed to setup test user:`, error);
    }
    console.warn(`[Global Setup] ⚠ Continuing anyway - user may already exist`);
  }
}

export default globalSetup;
