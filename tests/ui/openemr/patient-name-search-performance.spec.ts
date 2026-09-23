import { expect, test } from '@playwright/test';

import { createNetworkDiagnostics } from '../support/network-diagnostics';
import { createPerformanceProbe } from '../support/performance-probe';

test.skip(
  process.env.OPENEMR_PERFORMANCE_SITE !== '1',
  'Requires the isolated 50,000-patient performance site',
);

test.describe('OpenEMR patient chart smoke', () => {
  test('returns the expected first page for a common surname', async ({
    page,
  }) => {
    /*
     * This is an integration-style browser workflow running
     * against a local containerized OpenEMR instance.
     *
     * Individual application transitions remain bounded by
     * shorter explicit timeouts below. The larger test-level
     * budget allows those legitimate transitions to occur
     * sequentially without the overall test timeout becoming
     * the limiting factor.
     */
    test.setTimeout(240_000);

    const username = process.env.OPENEMR_ADMIN_USER;
    const password = process.env.OPENEMR_ADMIN_PASSWORD;

    const patientFirstName = 'Synthetic001';
    const patientMiddleName = 'Test';
    const patientLastName = 'Patient001';
    const patientMrn = 'SYNTHMRN000001';
    const patientDisplayName = 'Patient001, Synthetic001';

    expect(
      username,
      'OPENEMR_ADMIN_USER must be defined in .env',
    ).toBeTruthy();

    expect(
      password,
      'OPENEMR_ADMIN_PASSWORD must be defined in .env',
    ).toBeTruthy();

    /*
     * Lightweight performance instrumentation is disabled by
     * default.
     *
     * Set PLAYWRIGHT_PERF=1 to collect client-observed timing
     * boundaries and derived segments for this workflow.
     *
     * These measurements describe elapsed time as observed by
     * the Playwright client. They must not be interpreted as
     * server-processing, network-only, browser-rendering, or
     * database execution time without additional correlated
     * evidence from those layers.
     */
    const perf = createPerformanceProbe(
      'openemr.performance-name-search-pilot',
    );

    const network = createNetworkDiagnostics(
      page,
      'openemr.performance-name-search-pilot',
    );

    /*
     * Controlled diagnostic condition: intercept only the
     * browser-triggered background-service request so its
     * relationship to foreground patient-chart latency can
     * be measured without changing OpenEMR configuration.
     */
    const suppressBackgroundRun =
      process.env.PLAYWRIGHT_SUPPRESS_BACKGROUND_RUN === '1';

    let suppressedBackgroundRunCount = 0;

    if (suppressBackgroundRun) {
      await page.route(
        '**/api/background_service/$run',
        async (route) => {
          suppressedBackgroundRunCount += 1;

          console.log('[BACKGROUND_RUN_INTERCEPTED]');

          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              diagnostic: 'background_run_suppressed',
            }),
          });
        },
      );
    }

    perf.mark('workflow.start');

    // ---------------------------------------------------------
    // Authenticate
    // ---------------------------------------------------------

    perf.mark('login_navigation.start');

    await page.goto(
      '/interface/login/login.php?site=performance',
      {
        waitUntil: 'domcontentloaded',
        timeout: 90_000,
      },
    );

    perf.mark('login_navigation.domcontentloaded');

    await page
      .getByRole('textbox', { name: 'Username' })
      .fill(username!);

    await page
      .getByRole('textbox', { name: 'Password' })
      .fill(password!);

    /*
     * OpenEMR authentication posts through main_screen.php and
     * then navigates to the authenticated tabs shell.
     *
     * Synchronize against that successful navigation response
     * rather than allowing Playwright's click action to wait
     * generically for navigation completion.
     */
    const authenticatedNavigation =
      page.waitForResponse(
        (response) =>
          response.request().isNavigationRequest() &&
          response.request().method() === 'GET' &&
          response.url().includes(
            '/interface/main/tabs/main.php',
          ) &&
          response.status() === 200,
        {
          timeout: 90_000,
        },
      );

    perf.mark('authentication.submit');

    await page
      .getByRole('button', { name: 'Login' })
      .click({
        noWaitAfter: true,
      });

    const authenticationResponse =
      await authenticatedNavigation;

    expect(authenticationResponse.status()).toBe(200);

    perf.mark('authentication.response');
    network.checkpoint('authentication.response');

    await expect(page).toHaveURL(
      /\/interface\/main\/tabs\/main\.php\?token_main=/,
      {
        timeout: 90_000,
      },
    );

    await expect(page).toHaveTitle(/OpenEMR/i);

    // ---------------------------------------------------------
    // Wait for authenticated OpenEMR shell
    // ---------------------------------------------------------

    const patientMenu = page.getByRole('button', {
      name: 'Patient',
      exact: true,
    });

    await expect(
      patientMenu,
      'OpenEMR authenticated shell did not expose the Patient menu',
    ).toBeVisible({
      timeout: 90_000,
    });

    perf.mark('authenticated_shell.ready');
    network.checkpoint('authenticated_shell.ready');

    /*
     * A newly installed OpenEMR environment may display its
     * optional product-registration modal asynchronously.
     * Resolve it before opening the Patient menu because its
     * appearance can close an already-open submenu.
     */
    const registrationModal = page.locator(
      '.product-registration-modal',
    );

    const registrationAppeared = await registrationModal
      .waitFor({
        state: 'visible',
        timeout: 5_000,
      })
      .then(() => true)
      .catch(() => false);

    if (registrationAppeared) {
      await registrationModal.locator('.nothanks').click();

      await expect(registrationModal).toBeHidden({
        timeout: 10_000,
      });
    }

    // ---------------------------------------------------------
    // Open Patient -> New/Search
    // ---------------------------------------------------------

    perf.mark('patient_search_initialization.start');

    await patientMenu.click();

    const newSearch = page.getByText('New/Search', {
      exact: true,
    });

    await expect(
      newSearch,
      'OpenEMR Patient menu did not expose New/Search',
    ).toBeVisible({
      timeout: 10_000,
    });

    await newSearch.click();

    // ---------------------------------------------------------
    // Locate the OpenEMR patient-search view
    // ---------------------------------------------------------

    const patientFrame = page.frameLocator(
      'iframe[name="pat"]',
    );

    const firstNameField = patientFrame.locator(
      '#form_fname',
    );

    const lastNameField = patientFrame.locator(
      '#form_lname',
    );

    const searchButton = patientFrame.locator(
      '#search',
    );

    /*
     * Waiting for #search is intentional.
     *
     * OpenEMR's large patient form can expose individual
     * demographic fields before the complete search UI has
     * finished parsing and initializing.
     */
    await expect(
      searchButton,
      'OpenEMR patient-search UI did not finish loading',
    ).toBeVisible({
      timeout: 90_000,
    });

    await expect(firstNameField).toBeVisible();
    await expect(lastNameField).toBeVisible();

    perf.mark('patient_search_initialization.ready');

    /*
     * The optional registration modal may appear after the
     * patient-search frame has loaded. Dismiss this late arrival
     * before interacting with the underlying search fields.
     */
    if (await registrationModal.isVisible()) {
      await registrationModal.locator('.nothanks').click();

      await expect(registrationModal).toBeHidden({
        timeout: 10_000,
      });
    }

    // ---------------------------------------------------------
    // Activate and populate deterministic search criteria
    // ---------------------------------------------------------

    /*
     * OpenEMR uses a click handler (toggleSearch) to mark
     * demographic fields as active patient-search criteria.
     *
     * Therefore these clicks are part of the application
     * workflow and must occur before filling the fields.
     */
    await lastNameField.click();
    await lastNameField.fill('Smith');

    await expect(lastNameField).toHaveValue('Smith');
    // ---------------------------------------------------------
    // Execute the real OpenEMR patient search
    // ---------------------------------------------------------

    perf.mark('finder_search.submit');

    await searchButton.click();

    /*
     * OpenEMR dlgopen() renders the patient finder in a
     * dialog iframe rather than navigating the main page.
     *
     * Attachment proves that the dialog iframe exists, but it
     * does not prove that OpenEMR has finished populating the
     * search-results table inside that iframe.
     */
    const finderIframe = page.locator(
      'iframe[src*="patient_select.php"]',
    );

    await expect(
      finderIframe,
      'OpenEMR did not open the patient finder dialog',
    ).toBeAttached({
      timeout: 90_000,
    });

    perf.mark('finder_iframe.attached');

    const finderFrame = page.frameLocator(
      'iframe[src*="patient_select.php"]',
    );

// ---------------------------------------------------------
    // Qualify the common-surname first page
    // ---------------------------------------------------------

    const resultRows = finderFrame.locator('tr.oneresult');

    await expect(
      resultRows.first(),
      'OpenEMR did not render the first Smith search result',
    ).toBeVisible({
      timeout: 90_000,
    });

    await expect(
      resultRows,
      'Smith prefix search did not render the expected 100-row first page',
    ).toHaveCount(100, {
      timeout: 90_000,
    });

    const displayedNames = await resultRows
      .locator('td.srName')
      .allTextContents();

    expect(displayedNames).toHaveLength(100);

    for (const displayedName of displayedNames) {
      expect(displayedName.trim()).toMatch(/^Smith,/);
    }

    perf.mark('finder_result.ready');
    network.checkpoint('finder_result.ready');

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
      'patient_search_initialization',
      'patient_search_initialization.start',
      'patient_search_initialization.ready',
    );

    perf.segment(
      'finder_iframe_attachment',
      'finder_search.submit',
      'finder_iframe.attached',
    );

    perf.segment(
      'finder_result_post_attachment',
      'finder_iframe.attached',
      'finder_result.ready',
    );

    perf.segment(
      'finder_total',
      'finder_search.submit',
      'finder_result.ready',
    );

    perf.segment(
      'workflow_to_finder_result',
      'workflow.start',
      'finder_result.ready',
    );

    console.log(
      `[NAME_SEARCH_PILOT] ${JSON.stringify({
        site: 'performance',
        lastNamePrefix: 'Smith',
        expectedDatabaseRows: 50000,
        expectedPrefixMatches: 473,
        renderedFirstPageRows: displayedNames.length,
        allRenderedNamesMatchPrefix: displayedNames.every(
          (name) => /^Smith,/.test(name.trim()),
        ),
      })}`,
    );

    console.log(
      `[BACKGROUND_RUN_CONTROL] ${JSON.stringify({
        suppressed: suppressBackgroundRun,
        intercepted: suppressedBackgroundRunCount,
      })}`,
    );

    network.finish();
    perf.finish();
  });
});
