import { expect, test } from '@playwright/test';

import { createPerformanceProbe } from '../support/performance-probe';

test.describe('OpenEMR patient chart smoke', () => {
  test('finds and opens a deterministic synthetic patient chart', async ({
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
    test.setTimeout(180_000);

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
      'openemr.patient-chart',
    );

    perf.mark('workflow.start');

    // ---------------------------------------------------------
    // Authenticate
    // ---------------------------------------------------------

    perf.mark('login_navigation.start');

    await page.goto(
      '/interface/login/login.php?site=default',
      {
        waitUntil: 'domcontentloaded',
        timeout: 30_000,
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
          timeout: 30_000,
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

    await expect(page).toHaveURL(
      /\/interface\/main\/tabs\/main\.php\?token_main=/,
      {
        timeout: 30_000,
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
      timeout: 30_000,
    });

    perf.mark('authenticated_shell.ready');

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
      timeout: 30_000,
    });

    await expect(firstNameField).toBeVisible();
    await expect(lastNameField).toBeVisible();

    perf.mark('patient_search_initialization.ready');

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
    await firstNameField.click();
    await firstNameField.fill(patientFirstName);

    await lastNameField.click();
    await lastNameField.fill(patientLastName);

    await expect(firstNameField).toHaveValue(
      patientFirstName,
    );

    await expect(lastNameField).toHaveValue(
      patientLastName,
    );

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
      timeout: 30_000,
    });

    perf.mark('finder_iframe.attached');

    const finderFrame = page.frameLocator(
      'iframe[src*="patient_select.php"]',
    );

    // ---------------------------------------------------------
    // Locate deterministic finder result
    // ---------------------------------------------------------

    /*
     * OpenEMR renders each patient search result as:
     *
     *   <tr class="oneresult" id="<pid>">
     *     <td class="srName">...</td>
     *     ...
     *     <td class="srID">...</td>
     *   </tr>
     *
     * OpenEMR binds its SelectPatient() click handler to the
     * complete tr.oneresult row rather than specifically to
     * the patient-name cell.
     *
     * Scope both identity values to the same result row so
     * that the patient we validate is also the patient we
     * subsequently select.
     */
    const patientResultRow = finderFrame
      .locator('tr.oneresult')
      .filter({
        has: finderFrame.locator(
          `td.srName:text-is("${patientDisplayName}")`,
        ),
      })
      .filter({
        has: finderFrame.locator(
          `td.srID:text-is("${patientMrn}")`,
        ),
      });

    /*
     * The finder iframe can be attached while its result
     * content is still loading. Therefore wait for the actual
     * deterministic result row to become visible.
     */
    await expect(
      patientResultRow,
      'Deterministic synthetic patient row was not rendered by the OpenEMR finder',
    ).toBeVisible({
      timeout: 30_000,
    });

    /*
     * Determinism requires one and only one row matching both
     * the expected patient name and MRN.
     */
    await expect(
      patientResultRow,
      'Expected exactly one OpenEMR finder row for the deterministic synthetic patient',
    ).toHaveCount(1);

    // ---------------------------------------------------------
    // Validate deterministic identity within the same row
    // ---------------------------------------------------------

    await expect(
      patientResultRow.locator('td.srName'),
      'Returned patient row did not contain the expected synthetic patient name',
    ).toHaveText(patientDisplayName);

    await expect(
      patientResultRow.locator('td.srID'),
      'Returned patient row did not contain the expected synthetic MRN',
    ).toHaveText(patientMrn);

    perf.mark('finder_result.ready');

    // ---------------------------------------------------------
    // Select deterministic patient
    // ---------------------------------------------------------

    /*
     * Register the dialog handler before selecting the
     * patient because OpenEMR may optionally display a
     * JavaScript dialog during chart selection.
     */
    page.once('dialog', async (dialog) => {
      console.log(
        `[OPENEMR DIALOG] ${dialog.message()}`,
      );

      await dialog.accept();
    });

    /*
     * OpenEMR binds patient selection to tr.oneresult:
     *
     *   $(".oneresult").click(function() {
     *     SelectPatient(this);
     *   });
     *
     * SelectPatient() obtains the patient ID from the row and
     * navigates the patient workspace to demographics.php.
     *
     * Register the response waiter before clicking so that a
     * fast navigation response cannot be missed.
     */
    const patientDashboardNavigation =
      page.waitForResponse(
        (response) =>
          response.request().isNavigationRequest() &&
          response.request().method() === 'GET' &&
          response.url().includes(
            '/interface/patient_file/summary/demographics.php',
          ) &&
          response.status() === 200,
        {
          timeout: 30_000,
        },
      );

    perf.mark('patient_selection.submit');

    await patientResultRow.click();

    const dashboardResponse =
      await patientDashboardNavigation;

    expect(dashboardResponse.status()).toBe(200);

    perf.mark('dashboard.response');

    // ---------------------------------------------------------
    // Validate selected patient chart
    // ---------------------------------------------------------

    /*
     * OpenEMR reuses its patient workspace iframe. The iframe
     * element's original src attribute is therefore not a
     * reliable indication of the document currently loaded
     * inside it.
     *
     * Find the frame by its current document URL instead.
     */
    await expect
      .poll(
        () =>
          page
            .frames()
            .some((frame) =>
              frame
                .url()
                .includes(
                  '/interface/patient_file/summary/demographics.php',
                ),
            ),
        {
          message:
            'OpenEMR patient-summary frame did not become active',
          timeout: 30_000,
        },
      )
      .toBe(true);

    const patientDashboard = page
      .frames()
      .find((frame) =>
        frame
          .url()
          .includes(
            '/interface/patient_file/summary/demographics.php',
          ),
      );

    expect(
      patientDashboard,
      'OpenEMR patient-summary frame was not available after navigation',
    ).toBeDefined();

    const dashboardTitle =
      `Medical Record Dashboard - ` +
      `${patientFirstName} ${patientMiddleName} ${patientLastName}`;

    /*
     * The dashboard heading proves that OpenEMR opened the
     * intended deterministic patient's Medical Record
     * Dashboard rather than merely retaining finder/search
     * content containing the same demographic values.
     */
    await expect(
      patientDashboard!.getByText(
        dashboardTitle,
        {
          exact: true,
        },
      ),
      'Selected synthetic patient Medical Record Dashboard did not expose the expected patient identity',
    ).toBeVisible({
      timeout: 30_000,
    });

    /*
     * The dashboard demographics expose the deterministic
     * synthetic MRN as OpenEMR's External ID. This provides
     * an independent identity assertion inside the active
     * patient chart.
     */
    await expect(
      patientDashboard!.getByText(
        patientMrn,
        {
          exact: true,
        },
      ),
      'Active patient dashboard did not expose the expected synthetic MRN',
    ).toBeVisible({
      timeout: 30_000,
    });

    perf.mark('dashboard.ready');

    // ---------------------------------------------------------
    // Define client-observed performance measurements
    // ---------------------------------------------------------

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
      'authenticated_shell_post_response',
      'authentication.response',
      'authenticated_shell.ready',
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
      'dashboard_response',
      'patient_selection.submit',
      'dashboard.response',
    );

    perf.segment(
      'dashboard_post_response',
      'dashboard.response',
      'dashboard.ready',
    );

    perf.segment(
      'patient_selection_total',
      'patient_selection.submit',
      'dashboard.ready',
    );

    perf.segment(
      'workflow_total',
      'workflow.start',
      'dashboard.ready',
    );

    perf.finish();
  });
});