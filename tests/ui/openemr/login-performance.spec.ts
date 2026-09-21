import { expect, test } from '@playwright/test';

import { createNetworkDiagnostics } from '../support/network-diagnostics';
import { createPerformanceProbe } from '../support/performance-probe';

test.describe('OpenEMR authenticated-shell performance', () => {
  test('measures login shell and translation loading', async ({
    page,
  }) => {
    test.setTimeout(120_000);

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

    const perf = createPerformanceProbe(
      'openemr.login-performance',
    );

    const network = createNetworkDiagnostics(
      page,
      'openemr.login-performance',
    );

    perf.mark('workflow.start');
    perf.mark('login_navigation.start');

    await page.goto(
      '/interface/login/login.php?site=default',
      {
        waitUntil: 'domcontentloaded',
        timeout: 30_000,
      },
    );

    perf.mark('login_navigation.domcontentloaded');
    network.checkpoint('login_page.ready');

    await page
      .getByRole('textbox', { name: 'Username' })
      .fill(username!);

    await page
      .getByRole('textbox', { name: 'Password' })
      .fill(password!);

    /*
     * Register both response observers before submitting the
     * login form so that fast responses cannot be missed.
     */
    const authenticatedNavigation = page.waitForResponse(
      (response) =>
        response.request().isNavigationRequest() &&
        response.request().method() === 'GET' &&
        response.url().includes(
          '/interface/main/tabs/main.php',
        ) &&
        response.status() === 200,
      {
        timeout: 30_000,
      },
    );

    const translationResponse = page.waitForResponse(
      (response) =>
        response.request().method() === 'GET' &&
        response.url().includes(
          '/library/ajax/i18n_generator.php',
        ) &&
        response.status() === 200,
      {
        timeout: 60_000,
      },
    );

    perf.mark('authentication.submit');

    await page
      .getByRole('button', { name: 'Login' })
      .click({
        noWaitAfter: true,
      });

    const shellResponse = await authenticatedNavigation;

    expect(shellResponse.status()).toBe(200);

    perf.mark('authentication.response');

    await expect(page).toHaveURL(
      /\/interface\/main\/tabs\/main\.php\?token_main=/,
      {
        timeout: 30_000,
      },
    );

    await expect(page).toHaveTitle(/OpenEMR/i);

    await expect(
      page.getByRole('textbox', { name: 'Username' }),
    ).not.toBeVisible();

    perf.mark('authenticated_shell.ready');
    network.checkpoint('authenticated_shell.ready');

    const i18nResponse = await translationResponse;

    expect(i18nResponse.status()).toBe(200);

    /*
     * A response event means that the HTTP headers have arrived.
     * Wait for the complete response body before closing the
     * measurement so network diagnostics record a finished event.
     */
    await i18nResponse.finished();

    perf.mark('i18n.response');
    network.checkpoint('i18n.response');

    perf.segment(
      'login_navigation',
      'login_navigation.start',
      'login_navigation.domcontentloaded',
    );

    perf.segment(
      'authentication_response',
      'authentication.submit',
      'authentication.response',
    );

    perf.segment(
      'authentication_to_usable_shell',
      'authentication.submit',
      'authenticated_shell.ready',
    );

    perf.segment(
      'authentication_to_i18n_response',
      'authentication.submit',
      'i18n.response',
    );

    perf.segment(
      'shell_ready_to_i18n_response',
      'authenticated_shell.ready',
      'i18n.response',
    );

    perf.mark('workflow.end');

    perf.segment(
      'workflow_total',
      'workflow.start',
      'workflow.end',
    );

    network.finish();
    perf.finish();
  });
});
