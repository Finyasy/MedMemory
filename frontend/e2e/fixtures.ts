import { expect, type Page } from '@playwright/test';

export const login = async (page: Page, email: string, password: string) => {
  await page.goto('/');
  await page.getByTestId('open-login').click();
  await page.getByTestId('login-email').fill(email);
  await page.getByTestId('login-password').fill(password);
  const loginResponsePromise = page.waitForResponse((response) =>
    response.url().includes('/api/v1/auth/login') && response.request().method() === 'POST',
  );
  await page.getByTestId('login-submit').click();
  const loginResponse = await loginResponsePromise;
  if (!loginResponse.ok()) {
    const body = await loginResponse.text();
    throw new Error(`Login failed: ${loginResponse.status()} ${body}`);
  }
  await expect(page.getByTestId('user-menu')).toBeVisible();
};

export const waitForPatientSelected = async (page: Page) => {
  const dashboardHeader = page.locator('.dashboard-header h1');
  await expect(dashboardHeader).toBeVisible({ timeout: 15000 });
  await expect(dashboardHeader).not.toHaveText('Your health dashboard', { timeout: 15000 });
  return await dashboardHeader.textContent();
};

export const selectFirstPatient = async (page: Page) => {
  await page.getByRole('tab', { name: /dashboard/i }).click();
  await expect(page.locator('.panel.documents h2')).toBeVisible({ timeout: 15000 });
  await waitForPatientSelected(page);
};
