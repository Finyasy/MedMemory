import { expect, type Page } from '@playwright/test';

export const login = async (page: Page, email: string, password: string, retries = 3) => {
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      await page.goto('/');
      await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
      
      await page.getByTestId('open-login').click();
      await page.getByTestId('login-email').fill(email);
      await page.getByTestId('login-password').fill(password);
      
      const loginResponsePromise = page.waitForResponse(
        (response) =>
          response.url().includes('/api/v1/auth/login') && response.request().method() === 'POST',
        { timeout: 30000 }
      );
      await page.getByTestId('login-submit').click();
      const loginResponse = await loginResponsePromise;
      
      if (!loginResponse.ok()) {
        const body = await loginResponse.text();
        if (loginResponse.status() === 429 && attempt < retries) {
          console.log(`Rate limited, retrying ${attempt + 1}/${retries}...`);
          await page.waitForTimeout(5000);
          continue;
        }
        throw new Error(`Login failed: ${loginResponse.status()} ${body}`);
      }
      
      await expect(page.getByTestId('user-menu')).toBeVisible({ timeout: 10000 });
      return;
    } catch (error) {
      if (attempt === retries) throw error;
      console.log(`Login attempt ${attempt} failed, retrying...`);
      await page.waitForTimeout(2000);
    }
  }
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
