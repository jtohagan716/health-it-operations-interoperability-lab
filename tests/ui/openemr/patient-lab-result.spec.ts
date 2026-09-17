import { expect, test } from '@playwright/test';

test.describe('OpenEMR clinician-visible laboratory result', () => {
  test('displays the deterministic synthetic patient glucose result', async ({
    page,
  }) => {
    /*
     * OpenEMR's authenticated shell, patient finder, dashboard, and
     * dashboard widgets load through separate application boundaries.
     * Individual waits below remain bounded; this larger test budget
     * prevents earlier legitimate application latency from consuming
     * the timeout needed by later clinical workflow assertions.
     */
    test.setTimeout(180_000);

    const username = process.env.OPENEMR_ADMIN_USER;
    const password = process.env.OPENEMR_ADMIN_PASSWORD;

    const patientFirstName = 'Synthetic001';
    const patientLastName = 'Patient001';
    const patientMrn = 'SYNTHMRN000001';
    const patientDisplayName = 'Patient001, Synthetic001';

    const labCode = '2345-7';
    const labName = 'Glucose';
    const labRange = '70-99';
    const labUnits = 'mg/dL';
    const labValue = '96';

    expect(
      username,
      'OPENEMR_ADMIN_USER must be defined in .env',
    ).toBeTruthy();

    expect(
      password,
      'OPENEMR_ADMIN_PASSWORD must be defined in .env',
    ).toBeTruthy();

    // ---------------------------------------------------------
    // Authenticate
    // ---------------------------------------------------------

    await page.goto('/interface/login/login.php?site=default', {
      waitUntil: 'domcontentloaded',
      timeout: 30_000,
    });

    await page
      .getByRole('textbox', { name: 'Username' })
      .fill(username!);

    await page
      .getByRole('textbox', { name: 'Password' })
      .fill(password!);

    const authenticatedNavigation = page.waitForResponse(
      (response) =>
        response.request().isNavigationRequest() &&
        response.request().method() === 'GET' &&
        response.url().includes('/interface/main/tabs/main.php') &&
        response.status() === 200,
      {
        timeout: 30_000,
      },
    );

    await page
      .getByRole('button', { name: 'Login' })
      .click({ noWaitAfter: true });

    const authenticationResponse =
      await authenticatedNavigation;

    expect(authenticationResponse.status()).toBe(200);

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

    // ---------------------------------------------------------
    // Open Patient -> New/Search
    // ---------------------------------------------------------

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
    // Locate patient-search view
    // ---------------------------------------------------------

    const patientFrame = page.frameLocator(
      'iframe[name="pat"]',
    );

    const firstNameField =
      patientFrame.locator('#form_fname');

    const lastNameField =
      patientFrame.locator('#form_lname');

    const searchButton = patientFrame.locator('#search');

    await expect(
      searchButton,
      'OpenEMR patient-search UI did not finish loading',
    ).toBeVisible({
      timeout: 30_000,
    });

    await expect(firstNameField).toBeVisible();
    await expect(lastNameField).toBeVisible();

    // ---------------------------------------------------------
    // Populate deterministic patient-search criteria
    // ---------------------------------------------------------

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

    await searchButton.click();

    // ---------------------------------------------------------
    // Validate deterministic finder result
    // ---------------------------------------------------------

    const finderIframe = page.locator(
      'iframe[src*="patient_select.php"]',
    );

    await expect(
      finderIframe,
      'OpenEMR did not open the patient finder dialog',
    ).toBeAttached({
      timeout: 30_000,
    });

    const finderFrame = page.frameLocator(
      'iframe[src*="patient_select.php"]',
    );

    const patientResult = finderFrame.getByText(
      patientDisplayName,
      {
        exact: true,
      },
    );

    await expect(
      patientResult,
      'Deterministic synthetic patient was not returned by OpenEMR search',
    ).toBeVisible({
      timeout: 30_000,
    });

    await expect(
      finderFrame.getByText(patientMrn, {
        exact: true,
      }),
      'Returned patient did not contain the expected synthetic MRN',
    ).toBeVisible();

    // ---------------------------------------------------------
    // Select deterministic patient
    // ---------------------------------------------------------

    page.once('dialog', async (dialog) => {
      console.log(`[OPENEMR DIALOG] ${dialog.message()}`);
      await dialog.accept();
    });

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

    await patientResult.click();

    const dashboardResponse =
      await patientDashboardNavigation;

    expect(dashboardResponse.status()).toBe(200);

    // ---------------------------------------------------------
    // Validate active deterministic patient chart
    // ---------------------------------------------------------

    await expect
      .poll(
        () =>
          page.frames().some((frame) =>
            frame.url().includes(
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
        frame.url().includes(
          '/interface/patient_file/summary/demographics.php',
        ),
      );

    expect(
      patientDashboard,
      'OpenEMR patient-summary frame was not available after navigation',
    ).toBeDefined();

    await expect(
      patientDashboard!.getByText(patientMrn, {
        exact: true,
      }),
      'Active patient dashboard did not expose the expected synthetic MRN',
    ).toBeVisible({
      timeout: 30_000,
    });

    // ---------------------------------------------------------
    // Synchronize with asynchronously populated Labs widget
    // ---------------------------------------------------------

    /*
     * Patient identity becoming visible does not mean every
     * dashboard widget is ready. OpenEMR populates the Labs
     * card asynchronously and can legitimately display
     * "Loading..." after the patient chart itself is usable.
     *
     * The clinician-facing lab-data link is therefore our
     * application-level readiness signal. No fixed sleep is
     * used.
     */
    const labDataLink = patientDashboard!.getByText(
      'Click here to view and graph all labdata.',
      {
        exact: true,
      },
    );

    await expect(
      labDataLink,
      'OpenEMR Labs dashboard widget did not finish loading',
    ).toBeVisible({
      timeout: 60_000,
    });

    // ---------------------------------------------------------
    // Enter clinician-visible Labs workflow
    // ---------------------------------------------------------

    await labDataLink.click();

    await expect
      .poll(
        () =>
          page.frames().some((frame) =>
            frame.url().toLowerCase().includes('lab'),
          ),
        {
          message:
            'OpenEMR did not expose an identifiable Labs frame after navigation',
          timeout: 30_000,
        },
      )
      .toBe(true);

    const labFrame = page
      .frames()
      .find((frame) =>
        frame.url().toLowerCase().includes('lab'),
      );

    expect(
      labFrame,
      'OpenEMR Labs frame was not available after navigation',
    ).toBeDefined();

    // ---------------------------------------------------------
    // Validate Labs selection workflow
    // ---------------------------------------------------------

    await expect(
      labFrame!.getByText('Labs', {
        exact: true,
      }),
    ).toBeVisible({
      timeout: 30_000,
    });

    await expect(
      labFrame!.getByText(labCode, {
        exact: true,
      }),
      `Labs workflow did not expose expected LOINC code ${labCode}`,
    ).toBeVisible({
      timeout: 30_000,
    });

    const glucoseCheckbox = labFrame!
      .getByRole('row', {
        name: new RegExp(labCode),
      })
      .getByRole('checkbox');

    await expect(
      glucoseCheckbox,
      `Expected LOINC ${labCode} was not selectable in the Labs workflow`,
    ).toBeVisible();

    await glucoseCheckbox.check();

    await expect(
      glucoseCheckbox,
      `Expected LOINC ${labCode} was not selected`,
    ).toBeChecked();

    await expect(
      labFrame!.getByText('Matrix', {
        exact: true,
      }),
      'Labs workflow did not expose Matrix output',
    ).toBeVisible();

    /*
     * OpenEMR prefixes the accessible name with an icon glyph,
     * so match the stable semantic suffix.
     */
    const submitButton = labFrame!.getByRole('button', {
      name: /Submit$/,
    });

    await expect(
      submitButton,
      'Labs workflow did not expose the Submit action',
    ).toBeVisible();

    await submitButton.click();

    // ---------------------------------------------------------
    // Validate one clinician-visible clinical result row
    // ---------------------------------------------------------

    /*
     * Scope all clinical assertions to the row containing
     * Glucose. This prevents unrelated content elsewhere in
     * the Labs document from independently satisfying value,
     * range, or units assertions.
     */
    const glucoseResultRow = labFrame!.getByRole('row', {
      name: /Glucose/,
    });

    await expect(
      glucoseResultRow,
      'Clinician-visible Labs matrix did not expose a Glucose result row',
    ).toBeVisible({
      timeout: 30_000,
    });

    await expect(
      glucoseResultRow.getByText(labName, {
        exact: true,
      }),
      'Clinical result row did not identify Glucose',
    ).toBeVisible();

    await expect(
      glucoseResultRow.getByText(labRange, {
        exact: true,
      }),
      'Glucose result row did not contain the expected reference range',
    ).toBeVisible();

    await expect(
      glucoseResultRow.getByText(labUnits, {
        exact: true,
      }),
      'Glucose result row did not contain the expected units',
    ).toBeVisible();

    await expect(
      glucoseResultRow.getByText(labValue, {
        exact: true,
      }),
      'Glucose result row did not contain the expected deterministic value',
    ).toBeVisible();
  });
});