import { expect, test } from '@playwright/test';

test.describe('OpenEMR authentication smoke', () => {
  test('redirects an unauthenticated user to the login page', async ({
    page,
  }) => {
    const response = await page.goto('/');

    expect(response).not.toBeNull();
    expect(response?.status()).toBe(200);

    await expect(page).toHaveURL(
      /\/interface\/login\/login\.php\?site=default$/,
    );

    await expect(
      page.getByRole('textbox', { name: 'Username' }),
    ).toBeVisible();

    await expect(
      page.getByRole('textbox', { name: 'Password' }),
    ).toBeVisible();

    await expect(
      page.getByRole('button', { name: 'Login' }),
    ).toBeVisible();
  });

  test('authenticates a local-lab administrator', async ({
    page,
  }) => {
    const username = process.env.OPENEMR_ADMIN_USER;
    const password = process.env.OPENEMR_ADMIN_PASSWORD;

    expect(
      username,
      'OPENEMR_ADMIN_USER must be defined in .env',
    ).toBeTruthy();

    expect(
      password,
      'OPENEMR_ADMIN_PASSWORD must be defined in .env',
    ).toBeTruthy();

    await page.goto(
      '/interface/login/login.php?site=default',
      {
        waitUntil: 'domcontentloaded',
      },
    );

    await page
      .getByRole('textbox', { name: 'Username' })
      .fill(username!);

    await page
      .getByRole('textbox', { name: 'Password' })
      .fill(password!);

    const authenticatedNavigation =
      page.waitForResponse(
        (response) =>
          response.request().isNavigationRequest() &&
          response.request().method() === 'GET' &&
          response.url().includes(
            '/interface/main/tabs/main.php',
          ) &&
          response.status() === 200,
      );

    await page
      .getByRole('button', { name: 'Login' })
      .click({
        noWaitAfter: true,
      });

    const response = await authenticatedNavigation;

    expect(response.status()).toBe(200);

    await expect(page).toHaveURL(
      /\/interface\/main\/tabs\/main\.php\?token_main=/,
    );

    await expect(page).toHaveTitle(
      /OpenEMR/i,
    );

    await expect(
      page.getByRole('textbox', { name: 'Username' }),
    ).not.toBeVisible();
  });
});
